from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from forgeai.ai.agent_state import AgentRun, AgentState


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RealitySource(str, Enum):
    MODEL = "model"
    ORCHESTRATOR = "orchestrator"
    TOOL = "tool"
    FILESYSTEM = "filesystem"
    WORKSPACE = "workspace"
    VERIFIER = "verifier"
    DATABASE = "database"
    USER = "user"
    SYSTEM = "system"


class RealityConfidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class EvidenceRelation(str, Enum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    NEUTRAL = "neutral"


class UncertaintyStatus(str, Enum):
    OPEN = "open"
    REDUCED = "reduced"
    RESOLVED = "resolved"
    BLOCKED = "blocked"


class CapabilityStatus(str, Enum):
    DECLARED = "declared"
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    TESTED = "tested"
    FAILED = "failed"


class AuthorityLevel(str, Enum):
    DENY = "deny"
    PROPOSE_ONLY = "propose_only"
    CONFIRM_REQUIRED = "confirm_required"
    AUTO = "auto"


class DecisionStatus(str, Enum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class ActionStatus(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    BLOCKED = "blocked"
    EXECUTING = "executing"
    EXECUTED = "executed"
    FAILED = "failed"
    VERIFIED = "verified"


class VerificationOutcome(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


class EventType(str, Enum):
    TASK_CREATED = "task_created"
    RUN_STARTED = "run_started"
    STATE_CHANGED = "state_changed"
    CONTEXT_BUILT = "context_built"
    OBSERVATION_RECORDED = "observation_recorded"
    EVIDENCE_RECORDED = "evidence_recorded"
    PLAN_CREATED = "plan_created"
    REVIEW_COMPLETED = "review_completed"
    APPROVAL_REQUESTED = "approval_requested"
    ACTION_PROPOSED = "action_proposed"
    ACTION_EXECUTED = "action_executed"
    VERIFICATION_STARTED = "verification_started"
    VERIFICATION_COMPLETED = "verification_completed"
    UNCERTAINTY_CREATED = "uncertainty_created"
    UNCERTAINTY_UPDATED = "uncertainty_updated"
    REPAIR_STARTED = "repair_started"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"
    RUN_ABORTED = "run_aborted"


@dataclass
class AgentIdentity:
    agent_id: str
    provider: str
    model: str
    role: str
    created_at: datetime = field(default_factory=utc_now)
    source: RealitySource = RealitySource.SYSTEM


@dataclass
class TaskReality:
    task_id: str
    user_request: str
    project_path: str
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None


@dataclass
class RunReality:
    run_id: str
    state: AgentState
    review_round: int = 0
    execution_round: int = 0
    repair_attempt: int = 0
    max_review_rounds: int = 3
    max_repair_attempts: int = 3
    started_at: datetime | None = None
    finished_at: datetime | None = None
    history: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    revision_context: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_agent_run(
        cls,
        run: AgentRun,
        *,
        run_id: str,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> RunReality:
        """Creates a Reality projection from the authoritative AgentRun."""
        if not isinstance(run, AgentRun):
            raise TypeError("run must be an AgentRun instance.")

        return cls(
            run_id=run_id,
            state=run.state,
            review_round=run.review_round,
            execution_round=run.execution_round,
            repair_attempt=run.repair_attempt,
            max_review_rounds=run.max_review_rounds,
            max_repair_attempts=run.max_repair_attempts,
            started_at=started_at,
            finished_at=finished_at,
            history=[dict(entry) for entry in run.history],
            metadata=dict(run.metadata),
            revision_context=[dict(entry) for entry in run.revision_context],
        )


@dataclass
class ContextResource:
    resource_id: str
    resource_type: str
    path: str | None = None
    included: bool = False
    reason: str | None = None
    source: RealitySource = RealitySource.WORKSPACE


@dataclass
class ContextReality:
    context_id: str
    max_tokens: int
    estimated_tokens: int
    resources: list[ContextResource] = field(default_factory=list)
    included_files: list[str] = field(default_factory=list)
    excluded_files: list[str] = field(default_factory=list)
    created_at: datetime | None = None


@dataclass
class KnowledgeReference:
    knowledge_id: str
    source: str
    title: str | None = None
    content_reference: str | None = None
    confidence: RealityConfidence = RealityConfidence.MEDIUM


@dataclass
class KnowledgeReality:
    references: list[KnowledgeReference] = field(default_factory=list)


@dataclass
class MemoryEntry:
    memory_id: str
    key: str
    value: Any
    source: RealitySource
    created_at: datetime = field(default_factory=utc_now)
    confidence: RealityConfidence = RealityConfidence.MEDIUM


@dataclass
class MemoryReality:
    entries: list[MemoryEntry] = field(default_factory=list)


@dataclass
class Capability:
    capability_id: str
    name: str
    status: CapabilityStatus
    description: str | None = None
    limitations: list[str] = field(default_factory=list)
    declared_by: RealitySource = RealitySource.MODEL
    tested_by: RealitySource | None = None
    last_tested_at: datetime | None = None


@dataclass
class AuthorityRule:
    authority_id: str
    resource: str
    action: str
    level: AuthorityLevel
    source: RealitySource
    reason: str | None = None
    requires_confirmation: bool = False


@dataclass
class Observation:
    observation_id: str
    type: str
    source: RealitySource
    summary: str
    value: Any = None
    timestamp: datetime = field(default_factory=utc_now)
    scope: str | None = None
    success: bool | None = None


@dataclass
class Evidence:
    evidence_id: str
    relation: EvidenceRelation
    statement: str
    source: RealitySource
    observation_ids: list[str] = field(default_factory=list)
    confidence: RealityConfidence = RealityConfidence.MEDIUM
    timestamp: datetime = field(default_factory=utc_now)


@dataclass
class Uncertainty:
    uncertainty_id: str
    question: str
    reason: str
    status: UncertaintyStatus = UncertaintyStatus.OPEN
    related_observation_ids: list[str] = field(default_factory=list)
    related_evidence_ids: list[str] = field(default_factory=list)
    impact: str | None = None
    resolution_action: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    resolved_at: datetime | None = None


@dataclass
class Decision:
    decision_id: str
    title: str
    selected_option: str
    alternatives: list[str] = field(default_factory=list)
    rationale: str | None = None
    evidence_ids: list[str] = field(default_factory=list)
    uncertainty_ids: list[str] = field(default_factory=list)
    status: DecisionStatus = DecisionStatus.PROPOSED
    created_at: datetime = field(default_factory=utc_now)


@dataclass
class Action:
    action_id: str
    action_type: str
    target: str
    status: ActionStatus = ActionStatus.PROPOSED
    preview_id: str | None = None
    authority_id: str | None = None
    result: Any = None
    created_at: datetime = field(default_factory=utc_now)
    executed_at: datetime | None = None


@dataclass
class Verification:
    verification_id: str
    target: str
    expected: str
    outcome: VerificationOutcome
    observed: str | None = None
    evidence_ids: list[str] = field(default_factory=list)
    observation_ids: list[str] = field(default_factory=list)
    verifier: RealitySource = RealitySource.VERIFIER
    started_at: datetime | None = None
    completed_at: datetime | None = None


@dataclass
class AgentEvent:
    event_id: str
    event_type: EventType
    task_id: str
    run_id: str
    actor: RealitySource
    phase: str
    timestamp: datetime = field(default_factory=utc_now)
    payload: dict[str, Any] = field(default_factory=dict)
    state_before: str | None = None
    state_after: str | None = None


@dataclass
class AgentReality:
    """
    Structured runtime view of the current agent reality.

    AgentReality is an integration layer and snapshot.
    Existing domain components remain authoritative for their own state.
    """

    identity: AgentIdentity
    task: TaskReality
    run: RunReality
    context: ContextReality | None = None
    knowledge: KnowledgeReality = field(default_factory=KnowledgeReality)
    memory: MemoryReality = field(default_factory=MemoryReality)
    capabilities: list[Capability] = field(default_factory=list)
    authority: list[AuthorityRule] = field(default_factory=list)
    observations: list[Observation] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    uncertainties: list[Uncertainty] = field(default_factory=list)
    decision: Decision | None = None
    action: Action | None = None
    verification: Verification | None = None
    events: list[AgentEvent] = field(default_factory=list)
