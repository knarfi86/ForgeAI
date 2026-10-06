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
    plugin_actions: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.summary.strip():
            raise ValueError("summary darf nicht leer sein.")
        if not isinstance(self.plugin_actions, list):
            raise ValueError("plugin_actions muss eine Liste sein.")

        seen_plugins: set[str] = set()
        for action in self.plugin_actions:
            if not isinstance(action, dict):
                raise ValueError("Jede Plugin-Aktion muss ein Objekt sein.")
            plugin_id = action.get("plugin_id")
            action_id = action.get("action")
            parameters = action.get("parameters", {})
            if not isinstance(plugin_id, str) or not plugin_id.strip():
                raise ValueError("Jede Plugin-Aktion benötigt plugin_id.")
            if not isinstance(action_id, str) or not action_id.strip():
                raise ValueError("Jede Plugin-Aktion benötigt action.")
            if not isinstance(parameters, dict):
                raise ValueError("Plugin-Aktionsparameter müssen ein Objekt sein.")
            plugin_id = plugin_id.strip()
            if plugin_id in seen_plugins:
                raise ValueError(
                    f"Plugin {plugin_id!r} darf pro AgentPlan nur eine Aktion besitzen."
                )
            seen_plugins.add(plugin_id)


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
