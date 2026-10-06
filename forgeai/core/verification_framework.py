from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol

from .completion_gate import (
    CompletionEvidence,
    CompletionEvidenceCategory,
    CompletionEvidenceMode,
    CompletionEvidenceStatus,
)


class VerificationStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"
    ERROR = "error"


@dataclass(frozen=True)
class VerificationContext:
    """Fresh execution context handed to a registered verifier."""

    task_id: str
    execution_round: int
    project_path: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def project_root(self) -> Path | None:
        return Path(self.project_path) if self.project_path else None


@dataclass(frozen=True)
class VerificationCheck:
    """One provider-backed check inside a verification profile."""

    check_id: str
    provider_id: str
    category: CompletionEvidenceCategory
    required: bool = True
    description: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.check_id.strip():
            raise ValueError("check_id darf nicht leer sein.")
        if not self.provider_id.strip():
            raise ValueError("provider_id darf nicht leer sein.")
        if not isinstance(self.category, CompletionEvidenceCategory):
            object.__setattr__(self, "category", CompletionEvidenceCategory(self.category))


@dataclass(frozen=True)
class VerificationProfile:
    """Named, capability-neutral collection of verification checks."""

    profile_id: str
    checks: tuple[VerificationCheck, ...]
    description: str = ""

    def __post_init__(self) -> None:
        if not self.profile_id.strip():
            raise ValueError("profile_id darf nicht leer sein.")
        if not self.checks:
            raise ValueError("Ein VerificationProfile benötigt mindestens einen Check.")

        ids = [check.check_id for check in self.checks]
        if len(ids) != len(set(ids)):
            raise ValueError("check_id muss innerhalb eines Profiles eindeutig sein.")

    @property
    def required_categories(self) -> tuple[CompletionEvidenceCategory, ...]:
        categories: list[CompletionEvidenceCategory] = []
        for check in self.checks:
            if check.required and check.category not in categories:
                categories.append(check.category)
        return tuple(categories)


@dataclass(frozen=True)
class VerificationProfileRequirement:
    """Persistable requirement derived from a profile before execution."""

    profile_id: str
    required_check_ids: tuple[str, ...]
    required_categories: tuple[CompletionEvidenceCategory, ...]

    @classmethod
    def from_profile(cls, profile: VerificationProfile) -> "VerificationProfileRequirement":
        return cls(
            profile_id=profile.profile_id,
            required_check_ids=tuple(
                check.check_id for check in profile.checks if check.required
            ),
            required_categories=profile.required_categories,
        )


@dataclass(frozen=True)
class VerificationResult:
    """Structured result returned by exactly one registered verifier."""

    check_id: str
    provider_id: str
    category: CompletionEvidenceCategory
    status: VerificationStatus
    summary: str
    source: str
    mode: CompletionEvidenceMode = CompletionEvidenceMode.FACT
    observed_value: str | None = None
    supporting_evidence_ids: tuple[str, ...] = ()
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.category, CompletionEvidenceCategory):
            object.__setattr__(self, "category", CompletionEvidenceCategory(self.category))
        if not isinstance(self.status, VerificationStatus):
            object.__setattr__(self, "status", VerificationStatus(self.status))
        if not isinstance(self.mode, CompletionEvidenceMode):
            object.__setattr__(self, "mode", CompletionEvidenceMode(self.mode))


@dataclass(frozen=True)
class VerificationReport:
    """Immutable report for one profile execution and one execution round."""

    profile_id: str
    task_id: str
    execution_round: int
    required_check_ids: tuple[str, ...]
    required_categories: tuple[CompletionEvidenceCategory, ...]
    results: tuple[VerificationResult, ...]

    @property
    def failed_required_check_ids(self) -> tuple[str, ...]:
        required = set(self.required_check_ids)
        return tuple(
            result.check_id
            for result in self.results
            if result.check_id in required and result.status == VerificationStatus.FAIL
        )

    @property
    def pending_required_check_ids(self) -> tuple[str, ...]:
        required = set(self.required_check_ids)
        return tuple(
            result.check_id
            for result in self.results
            if result.check_id in required
            and result.status in {VerificationStatus.UNKNOWN, VerificationStatus.ERROR}
        )

    @property
    def passed(self) -> bool:
        required = set(self.required_check_ids)
        passed = {
            result.check_id
            for result in self.results
            if result.status == VerificationStatus.PASS
        }
        return required.issubset(passed)

    def to_completion_evidence(self) -> tuple[CompletionEvidence, ...]:
        evidence: list[CompletionEvidence] = []
        for result in self.results:
            status = {
                VerificationStatus.PASS: CompletionEvidenceStatus.PASS,
                VerificationStatus.FAIL: CompletionEvidenceStatus.FAIL,
                VerificationStatus.UNKNOWN: CompletionEvidenceStatus.UNKNOWN,
                VerificationStatus.ERROR: CompletionEvidenceStatus.UNKNOWN,
            }[result.status]
            evidence.append(
                CompletionEvidence(
                    evidence_id=(
                        f"verification:{self.profile_id}:{result.check_id}:"
                        f"round-{self.execution_round}"
                    ),
                    category=result.category,
                    status=status,
                    summary=result.summary,
                    source=result.source,
                    mode=result.mode,
                    supporting_evidence_ids=result.supporting_evidence_ids,
                    observed_value=result.observed_value,
                    execution_round=self.execution_round,
                )
            )
        return tuple(evidence)


class VerificationProvider(Protocol):
    provider_id: str
    category: CompletionEvidenceCategory
    mode: CompletionEvidenceMode

    def verify(
        self,
        context: VerificationContext,
        check: VerificationCheck,
    ) -> VerificationResult:
        ...


@dataclass
class FunctionVerificationProvider:
    """Small adapter for plugins that expose a Python callable as verifier."""

    provider_id: str
    category: CompletionEvidenceCategory
    callback: Callable[[VerificationContext, VerificationCheck], VerificationResult]
    mode: CompletionEvidenceMode = CompletionEvidenceMode.FACT

    def verify(
        self,
        context: VerificationContext,
        check: VerificationCheck,
    ) -> VerificationResult:
        return self.callback(context, check)


class VerificationRegistry:
    """Central registry for verifier providers and named profiles."""

    def __init__(self) -> None:
        self._providers: dict[str, VerificationProvider] = {}
        self._profiles: dict[str, VerificationProfile] = {}

    def register_provider(
        self,
        provider: VerificationProvider,
        *,
        replace: bool = False,
    ) -> None:
        provider_id = str(getattr(provider, "provider_id", "")).strip()
        if not provider_id:
            raise ValueError("VerificationProvider benötigt provider_id.")

        category = CompletionEvidenceCategory(getattr(provider, "category"))
        mode = CompletionEvidenceMode(getattr(provider, "mode"))
        if category in {
            CompletionEvidenceCategory.TECHNICAL,
            CompletionEvidenceCategory.RUNTIME,
            CompletionEvidenceCategory.VISUAL,
        } and mode != CompletionEvidenceMode.FACT:
            raise ValueError(
                "Objektive VerificationProvider müssen beobachtete FACT-Evidence liefern."
            )

        if provider_id in self._providers and not replace:
            raise ValueError(f"VerificationProvider bereits registriert: {provider_id}")
        self._providers[provider_id] = provider

    def register_profile(
        self,
        profile: VerificationProfile,
        *,
        replace: bool = False,
    ) -> None:
        if profile.profile_id in self._profiles and not replace:
            raise ValueError(f"VerificationProfile bereits registriert: {profile.profile_id}")
        self._profiles[profile.profile_id] = profile

    def get_provider(self, provider_id: str) -> VerificationProvider:
        try:
            return self._providers[provider_id]
        except KeyError as exc:
            raise KeyError(f"VerificationProvider nicht registriert: {provider_id}") from exc

    def get_profile(self, profile_id: str) -> VerificationProfile:
        try:
            return self._profiles[profile_id]
        except KeyError as exc:
            raise KeyError(f"VerificationProfile nicht registriert: {profile_id}") from exc

    def list_provider_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._providers))

    def list_profile_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._profiles))


class VerificationEngine:
    """Executes registered profiles without containing capability-specific logic."""

    def __init__(self, registry: VerificationRegistry) -> None:
        self.registry = registry

    def run(
        self,
        profile_id: str,
        context: VerificationContext,
    ) -> VerificationReport:
        profile = self.registry.get_profile(profile_id)
        results: list[VerificationResult] = []

        for check in profile.checks:
            provider = self.registry.get_provider(check.provider_id)
            provider_category = CompletionEvidenceCategory(provider.category)
            provider_mode = CompletionEvidenceMode(provider.mode)

            if provider_category != check.category:
                raise ValueError(
                    f"Provider {check.provider_id!r} gehört zu {provider_category.value!r}, "
                    f"Check {check.check_id!r} erwartet aber {check.category.value!r}."
                )

            try:
                result = provider.verify(context, check)
                self._validate_result(check, provider_id=check.provider_id, mode=provider_mode, result=result)
            except Exception as error:
                result = VerificationResult(
                    check_id=check.check_id,
                    provider_id=check.provider_id,
                    category=check.category,
                    status=VerificationStatus.ERROR,
                    summary="Verifier konnte keine belastbare Evidence liefern.",
                    source=check.provider_id,
                    mode=provider_mode,
                    observed_value=f"{type(error).__name__}: {error}",
                    details={"error_type": type(error).__name__},
                )
            results.append(result)

        return VerificationReport(
            profile_id=profile.profile_id,
            task_id=context.task_id,
            execution_round=context.execution_round,
            required_check_ids=tuple(
                check.check_id for check in profile.checks if check.required
            ),
            required_categories=profile.required_categories,
            results=tuple(results),
        )

    @staticmethod
    def _validate_result(
        check: VerificationCheck,
        *,
        provider_id: str,
        mode: CompletionEvidenceMode,
        result: VerificationResult,
    ) -> None:
        if not isinstance(result, VerificationResult):
            raise TypeError("VerificationProvider muss VerificationResult zurückgeben.")
        if result.check_id != check.check_id:
            raise ValueError("VerificationResult.check_id passt nicht zum ausgeführten Check.")
        if result.provider_id != provider_id:
            raise ValueError("VerificationResult.provider_id passt nicht zum Provider.")
        if result.category != check.category:
            raise ValueError("VerificationResult.category passt nicht zum Check.")
        if result.mode != mode:
            raise ValueError("VerificationResult.mode passt nicht zur Provider-Deklaration.")
