from __future__ import annotations

import logging

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


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
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


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

    def fail(self) -> None:
        self.transition(AgentState.FAILED)

    def abort(self) -> None:
        self.transition(AgentState.ABORTED)