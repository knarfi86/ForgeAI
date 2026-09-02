from __future__ import annotations

from typing import Protocol

from .agent_contracts import AgentTask


class ExternalPlanner(Protocol):
    """Optionaler externer Planungsdienst.

    Ein ExternalPlanner liefert ausschließlich zusätzliche Planungshinweise.
    Er besitzt keine Schreib- oder Ausführungsrechte für das Projekt.
    """

    def plan(
        self,
        task: AgentTask,
        project_context: str,
    ) -> str:
        """Erzeugt einen externen Planungsvorschlag."""
        ...
