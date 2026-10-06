from __future__ import annotations

import logging

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from forgeai.core.failure_fingerprint import FailureFingerprint
from forgeai.core.stagnation_detector import StagnationStatus
from forgeai.core.recovery_escalation import RecoveryEscalationDecision
from forgeai.core.completion_gate import (
    CompletionDecision,
    CompletionEvidence,
)
from forgeai.core.verification_framework import (
    VerificationProfileRequirement,
    VerificationReport,
)
from forgeai.core.fact_evidence_provider import FactRecord
from forgeai.core.plugin_manager import CapabilityExecutionPlan


logger = logging.getLogger(__name__)


class AgentState(str, Enum):
    IDLE = "idle"
    PLANNING = "planning"
    REVIEWING = "reviewing"
    APPROVAL_REQUIRED = "approval_required"
    EXECUTING = "executing"
    TESTING = "testing"
    ANALYZING = "analyzing"
    REPAIRING = "repairing"
    COMPLETION_CHECKING = "completion_checking"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    FAILED = "failed"
    ABORTED = "aborted"


@dataclass(frozen=True)
class VerificationRecord:
    """One observed result, with plan targets kept separate from actual writes."""

    execution_round: int
    repair_attempt: int
    success: bool
    test_output: str
    failure_fingerprint: str | None
    normalized_output: str
    planned_paths: tuple[str, ...] = ()




@dataclass(frozen=True)
class RepairRecord:
    """One completed repair attempt and its observed verification outcome."""

    repair_attempt: int
    execution_round: int
    failure_before: str | None
    failure_after: str | None
    success: bool
    analysis_summary: str
    root_cause: str
    repair_requirements: tuple[str, ...]
    plan_summary: str
    planned_paths: tuple[str, ...]
    changed_failure: bool


@dataclass
class AgentRun:
    task_id: str
    state: AgentState = AgentState.IDLE

    review_round: int = 0
    execution_round: int = 0
    repair_attempt: int = 0

    max_review_rounds: int = 3
    max_repair_attempts: int = 3

    history: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    revision_context: list[dict[str, Any]] = field(default_factory=list)
    verification_history: list[VerificationRecord] = field(default_factory=list)
    repair_history: list[RepairRecord] = field(default_factory=list)
    stagnation_status: StagnationStatus = field(default_factory=StagnationStatus)
    recovery_escalation: RecoveryEscalationDecision = field(default_factory=RecoveryEscalationDecision)
    recovery_escalation_history: list[RecoveryEscalationDecision] = field(default_factory=list)
    completion_evidence: list[CompletionEvidence] = field(default_factory=list)
    completion_decision: CompletionDecision = field(default_factory=CompletionDecision)
    completion_history: list[CompletionDecision] = field(default_factory=list)
    required_verification_profiles: list[VerificationProfileRequirement] = field(default_factory=list)
    verification_reports: list[VerificationReport] = field(default_factory=list)
    fact_history: list[FactRecord] = field(default_factory=list)
    capability_plans: list[CapabilityExecutionPlan] = field(default_factory=list)

    def record_verification(
        self,
        success: bool,
        test_output: str,
        planned_paths: tuple[str, ...] = (),
    ) -> VerificationRecord:
        if self.state != AgentState.TESTING:
            raise RuntimeError("Verifikation kann nur im Zustand 'testing' erfasst werden.")

        fingerprint = None if success else FailureFingerprint.from_output(test_output)
        record = VerificationRecord(
            execution_round=self.execution_round,
            repair_attempt=self.repair_attempt,
            success=success,
            test_output=test_output,
            failure_fingerprint=fingerprint.signature if fingerprint else None,
            normalized_output=fingerprint.normalized_output if fingerprint else "",
            planned_paths=tuple(planned_paths),
        )
        self.verification_history.append(record)
        return record


    def record_repair_outcome(
        self,
        *,
        failure_before: str | None,
        verification: VerificationRecord,
        analysis_summary: str,
        root_cause: str,
        repair_requirements: tuple[str, ...],
        plan_summary: str,
        planned_paths: tuple[str, ...],
    ) -> RepairRecord:
        """Record exactly one completed outcome for the current repair attempt."""
        if self.repair_attempt <= 0:
            raise RuntimeError("RepairHistory benötigt einen aktiven Reparaturversuch.")

        if any(
            entry.repair_attempt == self.repair_attempt
            for entry in self.repair_history
        ):
            raise RuntimeError("Dieser Reparaturversuch wurde bereits erfasst.")

        failure_after = verification.failure_fingerprint
        record = RepairRecord(
            repair_attempt=self.repair_attempt,
            execution_round=verification.execution_round,
            failure_before=failure_before,
            failure_after=failure_after,
            success=verification.success,
            analysis_summary=analysis_summary,
            root_cause=root_cause,
            repair_requirements=tuple(repair_requirements),
            plan_summary=plan_summary,
            planned_paths=tuple(sorted(set(planned_paths))),
            changed_failure=(
                not verification.success
                and bool(failure_before)
                and bool(failure_after)
                and failure_before != failure_after
            ),
        )
        self.repair_history.append(record)
        return record


    def record_recovery_escalation(
        self,
        decision: RecoveryEscalationDecision,
    ) -> RecoveryEscalationDecision:
        """Record an active deterministic recovery escalation decision once."""
        if not isinstance(decision, RecoveryEscalationDecision):
            raise TypeError("decision muss eine RecoveryEscalationDecision sein.")

        self.recovery_escalation = decision
        if decision.active:
            self.recovery_escalation_history.append(decision)
        return decision

    def add_completion_evidence(
        self,
        evidence: CompletionEvidence,
    ) -> CompletionEvidence:
        """Upsert one completion evidence item by its stable evidence ID."""
        if not isinstance(evidence, CompletionEvidence):
            raise TypeError("evidence muss CompletionEvidence sein.")
        self.completion_evidence = [
            item for item in self.completion_evidence
            if item.evidence_id != evidence.evidence_id
        ]
        self.completion_evidence.append(evidence)
        return evidence

    def record_completion_decision(
        self,
        decision: CompletionDecision,
    ) -> CompletionDecision:
        if not isinstance(decision, CompletionDecision):
            raise TypeError("decision muss CompletionDecision sein.")
        self.completion_decision = decision
        self.completion_history.append(decision)
        return decision

    def require_verification_profile(
        self,
        requirement: VerificationProfileRequirement,
    ) -> VerificationProfileRequirement:
        if not isinstance(requirement, VerificationProfileRequirement):
            raise TypeError("requirement muss VerificationProfileRequirement sein.")
        self.required_verification_profiles = [
            item for item in self.required_verification_profiles
            if item.profile_id != requirement.profile_id
        ]
        self.required_verification_profiles.append(requirement)
        return requirement

    def record_verification_report(
        self,
        report: VerificationReport,
    ) -> VerificationReport:
        if not isinstance(report, VerificationReport):
            raise TypeError("report muss VerificationReport sein.")
        self.verification_reports.append(report)
        return report

    def record_fact(self, record: FactRecord) -> FactRecord:
        """Persist one objective fact observation for audit and Reality projection."""
        if not isinstance(record, FactRecord):
            raise TypeError("record muss FactRecord sein.")
        if record.task_id != self.task_id:
            raise ValueError("FactRecord.task_id passt nicht zum AgentRun.")
        self.fact_history.append(record)
        return record

    def record_capability_plan(
        self,
        plan: CapabilityExecutionPlan,
    ) -> CapabilityExecutionPlan:
        """Persist the deterministic plugin/capability selection for this run."""
        if not isinstance(plan, CapabilityExecutionPlan):
            raise TypeError("plan muss CapabilityExecutionPlan sein.")
        self.capability_plans.append(plan)
        return plan

    def transition(self, new_state: AgentState) -> None:
        if not isinstance(new_state, AgentState):
            raise ValueError(f"Ungültiger AgentState: {new_state!r}")

        previous_state = self.state.value
        self.state = new_state

        event = {
            "state": new_state.value,
            "review_round": self.review_round,
            "execution_round": self.execution_round,
            "repair_attempt": self.repair_attempt,
        }
        self.history.append(event)

        logger.info(
            "Agent state transition: task=%s %s -> %s "
            "review=%s execution=%s repair=%s",
            self.task_id,
            previous_state,
            new_state.value,
            self.review_round,
            self.execution_round,
            self.repair_attempt,
        )

    def start_review(self) -> int:
        if self.review_round >= self.max_review_rounds:
            raise RuntimeError("Maximale Anzahl der Review-Runden erreicht.")

        self.review_round += 1
        self.transition(AgentState.REVIEWING)
        return self.review_round

    def start_execution(self) -> int:
        self.execution_round += 1
        self.transition(AgentState.EXECUTING)
        return self.execution_round

    def start_repair(self) -> int:
        if self.repair_attempt >= self.max_repair_attempts:
            raise RuntimeError("Maximale Anzahl der Reparaturversuche erreicht.")

        self.repair_attempt += 1
        self.transition(AgentState.REPAIRING)
        return self.repair_attempt

    def complete(self) -> None:
        self.transition(AgentState.COMPLETED)

    def partial_complete(self) -> None:
        self.transition(AgentState.PARTIALLY_COMPLETED)

    def fail(self) -> None:
        self.transition(AgentState.FAILED)

    def abort(self) -> None:
        self.transition(AgentState.ABORTED)
