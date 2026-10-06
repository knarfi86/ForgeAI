from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable


class CompletionEvidenceCategory(str, Enum):
    """Evidence classes understood by the generic Forge completion gate."""

    TECHNICAL = "technical"
    RUNTIME = "runtime"
    VISUAL = "visual"
    SEMANTIC = "semantic"


class CompletionEvidenceMode(str, Enum):
    """Whether an evidence item is an observed fact or an interpretation."""

    FACT = "fact"
    INFERENCE = "inference"


class CompletionEvidenceStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"


class CompletionOutcome(str, Enum):
    """PENDING is transient; the other three are final completion outcomes."""

    PENDING = "pending"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    FAILED = "failed"


@dataclass(frozen=True)
class CompletionEvidence:
    """One completion-relevant observation or evidence-backed inference.

    Objective categories (technical/runtime/visual) only count as positive proof
    when they are FACTs. Semantic inference is allowed, but only when it cites
    concrete supporting evidence IDs. This prevents an LLM from promoting an
    unsupported interpretation to completion truth.
    """

    evidence_id: str
    category: CompletionEvidenceCategory
    status: CompletionEvidenceStatus
    summary: str
    source: str
    mode: CompletionEvidenceMode = CompletionEvidenceMode.FACT
    supporting_evidence_ids: tuple[str, ...] = ()
    observed_value: str | None = None
    execution_round: int | None = None


@dataclass(frozen=True)
class CompletionDecision:
    outcome: CompletionOutcome = CompletionOutcome.PENDING
    required_categories: tuple[CompletionEvidenceCategory, ...] = (
        CompletionEvidenceCategory.TECHNICAL,
    )
    satisfied_categories: tuple[CompletionEvidenceCategory, ...] = ()
    failed_categories: tuple[CompletionEvidenceCategory, ...] = ()
    pending_categories: tuple[CompletionEvidenceCategory, ...] = ()
    reason_codes: tuple[str, ...] = ()
    considered_evidence_ids: tuple[str, ...] = ()
    ignored_evidence_ids: tuple[str, ...] = ()

    @property
    def final(self) -> bool:
        return self.outcome != CompletionOutcome.PENDING


class CompletionGate:
    """Deterministic completion policy.

    The gate does not inspect source code, images or runtime state itself. It only
    evaluates explicit evidence supplied by trusted verifiers or evidence-backed
    semantic interpretation. Tools establish facts; models may interpret facts.
    """

    def evaluate(
        self,
        evidence: Iterable[CompletionEvidence],
        *,
        required_categories: Iterable[CompletionEvidenceCategory] = (
            CompletionEvidenceCategory.TECHNICAL,
        ),
        current_execution_round: int | None = None,
    ) -> CompletionDecision:
        required = self._normalize_required_categories(required_categories)
        usable: list[CompletionEvidence] = []
        ignored_ids: list[str] = []
        reason_codes: list[str] = []

        for item in evidence:
            if not isinstance(item, CompletionEvidence):
                raise TypeError("CompletionGate akzeptiert nur CompletionEvidence.")

            if (
                current_execution_round is not None
                and item.execution_round != current_execution_round
            ):
                ignored_ids.append(item.evidence_id)
                reason_codes.append("stale_evidence_ignored")
                continue

            if not self._is_truth_eligible(item):
                ignored_ids.append(item.evidence_id)
                reason_codes.append(self._invalid_reason(item))
                continue

            usable.append(item)

        factual_ids = {
            item.evidence_id for item in usable
            if item.mode == CompletionEvidenceMode.FACT
        }
        anchored: list[CompletionEvidence] = []
        for item in usable:
            if (
                item.category == CompletionEvidenceCategory.SEMANTIC
                and item.mode == CompletionEvidenceMode.INFERENCE
                and (
                    not item.supporting_evidence_ids
                    or not all(
                        evidence_id in factual_ids
                        for evidence_id in item.supporting_evidence_ids
                    )
                )
            ):
                ignored_ids.append(item.evidence_id)
                reason_codes.append("semantic_inference_missing_support")
                continue
            anchored.append(item)
        usable = anchored

        satisfied: list[CompletionEvidenceCategory] = []
        failed: list[CompletionEvidenceCategory] = []
        pending: list[CompletionEvidenceCategory] = []

        for category in required:
            category_items = [item for item in usable if item.category == category]
            statuses = {item.status for item in category_items}

            if CompletionEvidenceStatus.FAIL in statuses:
                failed.append(category)
            elif CompletionEvidenceStatus.PASS in statuses:
                satisfied.append(category)
            else:
                pending.append(category)

        if CompletionEvidenceCategory.TECHNICAL in failed:
            outcome = CompletionOutcome.FAILED
            reason_codes.append("technical_verification_failed")
        elif failed:
            outcome = CompletionOutcome.PARTIALLY_COMPLETED
            reason_codes.append("required_nontechnical_evidence_failed")
        elif pending:
            outcome = CompletionOutcome.PENDING
            reason_codes.append("required_evidence_pending")
        else:
            outcome = CompletionOutcome.COMPLETED
            reason_codes.append("all_required_evidence_satisfied")

        return CompletionDecision(
            outcome=outcome,
            required_categories=required,
            satisfied_categories=tuple(satisfied),
            failed_categories=tuple(failed),
            pending_categories=tuple(pending),
            reason_codes=tuple(dict.fromkeys(reason_codes)),
            considered_evidence_ids=tuple(item.evidence_id for item in usable),
            ignored_evidence_ids=tuple(dict.fromkeys(ignored_ids)),
        )

    @staticmethod
    def _normalize_required_categories(
        categories: Iterable[CompletionEvidenceCategory],
    ) -> tuple[CompletionEvidenceCategory, ...]:
        normalized: list[CompletionEvidenceCategory] = [
            CompletionEvidenceCategory.TECHNICAL
        ]
        for category in categories:
            if not isinstance(category, CompletionEvidenceCategory):
                category = CompletionEvidenceCategory(category)
            if category not in normalized:
                normalized.append(category)
        return tuple(normalized)

    @staticmethod
    def _is_truth_eligible(item: CompletionEvidence) -> bool:
        if item.category in {
            CompletionEvidenceCategory.TECHNICAL,
            CompletionEvidenceCategory.RUNTIME,
            CompletionEvidenceCategory.VISUAL,
        }:
            return item.mode == CompletionEvidenceMode.FACT

        if item.category == CompletionEvidenceCategory.SEMANTIC:
            if item.mode == CompletionEvidenceMode.FACT:
                return True
            if item.status == CompletionEvidenceStatus.UNKNOWN:
                return True
            return bool(item.supporting_evidence_ids)

        return False

    @staticmethod
    def _invalid_reason(item: CompletionEvidence) -> str:
        if item.category == CompletionEvidenceCategory.SEMANTIC:
            return "semantic_inference_without_evidence"
        return "objective_claim_not_observed_fact"
