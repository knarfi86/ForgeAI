from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ReviewDecision(str, Enum):
    APPROVE = "approve"
    REVISE = "revise"
    REJECT = "reject"


@dataclass
class AgentTask:
    task_id: str
    user_request: str
    project_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.task_id.strip():
            raise ValueError("task_id darf nicht leer sein.")

        if not self.user_request.strip():
            raise ValueError("user_request darf nicht leer sein.")


@dataclass
class AgentPlan:
    summary: str
    proposed_changes: list[dict[str, Any]] = field(default_factory=list)
    rationale: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.summary.strip():
            raise ValueError("summary darf nicht leer sein.")


@dataclass
class ReviewResult:
    decision: ReviewDecision
    findings: list[str] = field(default_factory=list)
    required_changes: list[str] = field(default_factory=list)
    rationale: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.decision, ReviewDecision):
            raise ValueError(
                f"Ungültige Review-Entscheidung: {self.decision!r}"
            )
