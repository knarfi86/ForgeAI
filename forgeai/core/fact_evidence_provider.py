from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol
from uuid import uuid4


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class FactStatus(str, Enum):
    """Result state of an objective fact observation."""

    OBSERVED = "observed"
    ABSENT = "absent"
    UNKNOWN = "unknown"
    ERROR = "error"


class FactSourceType(str, Enum):
    """Machine-observable source classes accepted by the Forge fact layer."""

    SCRIPT = "script"
    API = "api"
    FILESYSTEM = "filesystem"
    REPOSITORY = "repository"
    DATABASE = "database"
    RUNTIME = "runtime"
    TOOL = "tool"


@dataclass(frozen=True)
class FactContext:
    """Fresh execution context handed to a fact provider."""

    task_id: str
    execution_round: int
    project_path: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def project_root(self) -> Path | None:
        return Path(self.project_path) if self.project_path else None


@dataclass(frozen=True)
class FactQuery:
    """Request for one objective fact.

    max_age_seconds == 0 means: always observe again. A positive value allows a
    same-context observation to be reused while it remains fresh.
    """

    fact_key: str
    parameters: Mapping[str, Any] = field(default_factory=dict)
    provider_id: str | None = None
    max_age_seconds: float = 0.0

    def __post_init__(self) -> None:
        if not self.fact_key.strip():
            raise ValueError("fact_key darf nicht leer sein.")
        if self.provider_id is not None and not self.provider_id.strip():
            raise ValueError("provider_id darf nicht leer sein.")
        if self.max_age_seconds < 0:
            raise ValueError("max_age_seconds darf nicht negativ sein.")


@dataclass(frozen=True)
class FactObservation:
    """Raw provider result before Forge stamps provenance and freshness."""

    status: FactStatus
    value: Any = None
    summary: str = ""
    source_detail: str = ""
    tool: str | None = None
    command: str | None = None
    exit_code: int | None = None
    raw_reference: str | None = None
    authoritative_absence: bool = False
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.status, FactStatus):
            object.__setattr__(self, "status", FactStatus(self.status))


@dataclass(frozen=True)
class FactRecord:
    """Stamped, persistable fact/evidence record.

    OBSERVED and authoritative ABSENT records are objective facts. UNKNOWN and
    ERROR are still valuable evidence about the failed observation, but they do
    not establish the requested fact.
    """

    fact_id: str
    fact_key: str
    provider_id: str
    source_type: FactSourceType
    status: FactStatus
    value: Any
    summary: str
    source_detail: str
    observed_at: datetime
    expires_at: datetime | None
    task_id: str
    execution_round: int
    project_path: str | None
    parameters: Mapping[str, Any] = field(default_factory=dict)
    tool: str | None = None
    command: str | None = None
    exit_code: int | None = None
    raw_reference: str | None = None
    details: Mapping[str, Any] = field(default_factory=dict)

    @property
    def authoritative(self) -> bool:
        return self.status in {FactStatus.OBSERVED, FactStatus.ABSENT}

    def is_fresh(self, now: datetime | None = None) -> bool:
        if self.expires_at is None:
            return False
        current = now or utc_now()
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        return current <= self.expires_at


@dataclass(frozen=True)
class FactResolution:
    """Result of resolving a FactQuery through the central truth layer."""

    record: FactRecord
    used_cache: bool = False
    replaced_fact_id: str | None = None
    reason_codes: tuple[str, ...] = ()


class FactProvider(Protocol):
    provider_id: str
    source_type: FactSourceType
    fact_keys: tuple[str, ...]

    def observe(self, context: FactContext, query: FactQuery) -> FactObservation:
        ...


@dataclass
class FunctionFactProvider:
    """Adapter for capability plugins exposing a deterministic Python callable."""

    provider_id: str
    source_type: FactSourceType
    fact_keys: tuple[str, ...]
    callback: Callable[[FactContext, FactQuery], FactObservation]

    def observe(self, context: FactContext, query: FactQuery) -> FactObservation:
        return self.callback(context, query)


class FactRegistry:
    """Registry of objective fact providers.

    Providers are selected by exact fact_key. If multiple providers can answer
    the same key, callers must explicitly select provider_id instead of Forge
    guessing which truth source to prefer.
    """

    def __init__(self) -> None:
        self._providers: dict[str, FactProvider] = {}

    def register_provider(self, provider: FactProvider, *, replace: bool = False) -> None:
        provider_id = str(getattr(provider, "provider_id", "")).strip()
        if not provider_id:
            raise ValueError("FactProvider benötigt provider_id.")

        source_type = FactSourceType(getattr(provider, "source_type"))
        fact_keys = tuple(str(key).strip() for key in getattr(provider, "fact_keys", ()))
        if not fact_keys or any(not key for key in fact_keys):
            raise ValueError("FactProvider benötigt mindestens einen gültigen fact_key.")
        if len(fact_keys) != len(set(fact_keys)):
            raise ValueError("FactProvider.fact_keys müssen eindeutig sein.")

        # Converting above is deliberate: only explicit machine-observable source
        # classes exist in FactSourceType. There is no LLM or memory source type.
        _ = source_type

        if provider_id in self._providers and not replace:
            raise ValueError(f"FactProvider bereits registriert: {provider_id}")
        self._providers[provider_id] = provider

    def get_provider(self, provider_id: str) -> FactProvider:
        try:
            return self._providers[provider_id]
        except KeyError as exc:
            raise KeyError(f"FactProvider nicht registriert: {provider_id}") from exc

    def providers_for(self, fact_key: str) -> tuple[FactProvider, ...]:
        return tuple(
            provider
            for provider in self._providers.values()
            if fact_key in tuple(getattr(provider, "fact_keys", ()))
        )

    def resolve_provider(self, query: FactQuery) -> FactProvider:
        if query.provider_id:
            provider = self.get_provider(query.provider_id)
            if query.fact_key not in tuple(getattr(provider, "fact_keys", ())):
                raise ValueError(
                    f"FactProvider {query.provider_id!r} unterstützt {query.fact_key!r} nicht."
                )
            return provider

        providers = self.providers_for(query.fact_key)
        if not providers:
            raise KeyError(f"Kein FactProvider für {query.fact_key!r} registriert.")
        if len(providers) > 1:
            ids = ", ".join(sorted(str(provider.provider_id) for provider in providers))
            raise ValueError(
                f"Mehrere FactProvider für {query.fact_key!r}: {ids}. "
                "provider_id muss explizit gewählt werden."
            )
        return providers[0]

    def list_provider_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._providers))


class FactService:
    """Central script/API-first truth service.

    The service owns freshness and provenance. Providers only observe. Forge
    decides whether an observation is fresh enough to be reused and refuses to
    treat non-authoritative absence as proof of non-existence.
    """

    def __init__(
        self,
        registry: FactRegistry,
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self.registry = registry
        self._clock = clock
        self._cache: dict[str, FactRecord] = {}

    def resolve(
        self,
        query: FactQuery,
        context: FactContext,
        *,
        force_refresh: bool = False,
    ) -> FactResolution:
        if not isinstance(query, FactQuery):
            raise TypeError("query muss FactQuery sein.")
        if not isinstance(context, FactContext):
            raise TypeError("context muss FactContext sein.")

        provider = self.registry.resolve_provider(query)
        cache_key = self._cache_key(query, context, provider.provider_id)
        now = self._normalized_now()
        previous = self._cache.get(cache_key)

        if (
            not force_refresh
            and query.max_age_seconds > 0
            and previous is not None
            and previous.authoritative
            and previous.is_fresh(now)
        ):
            return FactResolution(
                record=previous,
                used_cache=True,
                reason_codes=("fresh_fact_reused",),
            )

        reason_codes: list[str] = []
        if previous is not None:
            reason_codes.append("fact_refreshed")

        try:
            observation = provider.observe(context, query)
            if not isinstance(observation, FactObservation):
                raise TypeError("FactProvider muss FactObservation zurückgeben.")
        except Exception as error:
            observation = FactObservation(
                status=FactStatus.ERROR,
                summary="FactProvider konnte keine belastbare Beobachtung liefern.",
                source_detail=str(provider.provider_id),
                details={"error_type": type(error).__name__, "error": str(error)},
            )
            reason_codes.append("provider_error")

        if (
            observation.status == FactStatus.ABSENT
            and not observation.authoritative_absence
        ):
            observation = FactObservation(
                status=FactStatus.UNKNOWN,
                value=None,
                summary=(
                    observation.summary
                    or "Nicht gefunden, aber die Prüfung belegt keine vollständige Abwesenheit."
                ),
                source_detail=observation.source_detail,
                tool=observation.tool,
                command=observation.command,
                exit_code=observation.exit_code,
                raw_reference=observation.raw_reference,
                details={
                    **dict(observation.details),
                    "downgraded_from": FactStatus.ABSENT.value,
                },
            )
            reason_codes.append("non_authoritative_absence_downgraded")

        expires_at = (
            now + timedelta(seconds=query.max_age_seconds)
            if query.max_age_seconds > 0
            else None
        )
        record = FactRecord(
            fact_id=f"fact:{uuid4().hex}",
            fact_key=query.fact_key,
            provider_id=str(provider.provider_id),
            source_type=FactSourceType(provider.source_type),
            status=observation.status,
            value=observation.value,
            summary=observation.summary,
            source_detail=observation.source_detail or str(provider.provider_id),
            observed_at=now,
            expires_at=expires_at,
            task_id=context.task_id,
            execution_round=context.execution_round,
            project_path=context.project_path,
            parameters=dict(query.parameters),
            tool=observation.tool,
            command=observation.command,
            exit_code=observation.exit_code,
            raw_reference=observation.raw_reference,
            details=dict(observation.details),
        )
        self._cache[cache_key] = record
        return FactResolution(
            record=record,
            used_cache=False,
            replaced_fact_id=previous.fact_id if previous else None,
            reason_codes=tuple(dict.fromkeys(reason_codes)),
        )

    def invalidate(self, *, fact_key: str | None = None) -> int:
        """Invalidate cached facts. Returns number of removed entries."""
        keys = list(self._cache)
        removed = 0
        for key in keys:
            record = self._cache[key]
            if fact_key is not None and record.fact_key != fact_key:
                continue
            del self._cache[key]
            removed += 1
        return removed

    def _normalized_now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None:
            return now.replace(tzinfo=timezone.utc)
        return now.astimezone(timezone.utc)

    @staticmethod
    def _cache_key(query: FactQuery, context: FactContext, provider_id: str) -> str:
        payload = {
            "provider_id": provider_id,
            "fact_key": query.fact_key,
            "parameters": dict(query.parameters),
            "task_id": context.task_id,
            "execution_round": context.execution_round,
            "project_path": context.project_path,
        }
        return json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
