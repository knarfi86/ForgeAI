from __future__ import annotations

import json
from typing import Any

from .agent_analyzer import RepairAnalysis
from .agent_contracts import AgentPlan, AgentTask
from .model_router import ModelRouter
from .prompt_core import compose_system_prompt
from .prompt_roles import load_role_prompt
from forgeai.core.recovery_escalation import RecoveryEscalationDecision


class AgentRepairer:
    """Erzeugt aus einer Fehleranalyse einen neuen ausführbaren AgentPlan."""

    ALLOWED_ACTIONS = {
        "create",
        "create_directory",
        "replace",
        "insert_before",
        "insert_after",
    }

    def __init__(self, model_router: ModelRouter) -> None:
        self.model_router = model_router

    def repair(
        self,
        task: AgentTask,
        analysis: RepairAnalysis,
        project_context: str = "",
        revision_context: list[dict[str, Any]] | None = None,
        recovery_escalation: RecoveryEscalationDecision | None = None,
    ) -> AgentPlan:
        prompt = self._build_prompt(
            task=task,
            analysis=analysis,
            project_context=project_context,
            revision_context=revision_context,
            recovery_escalation=recovery_escalation,
        )

        response = self.model_router.generate(
            "repairer",
            prompt,
        )

        return self._parse_response(response)

    @staticmethod
    def _build_prompt(
        *,
        task: AgentTask,
        analysis: RepairAnalysis,
        project_context: str,
        revision_context: list[dict[str, Any]] | None = None,
        recovery_escalation: RecoveryEscalationDecision | None = None,
    ) -> str:
        role_prompt = load_role_prompt("repair_planner")
        analysis_json = json.dumps(
            {
                "summary": analysis.summary,
                "findings": analysis.findings,
                "root_cause": analysis.root_cause,
                "repair_requirements": analysis.repair_requirements,
            },
            ensure_ascii=False,
            indent=2,
        )

        revision_json = json.dumps(
            revision_context or [],
            ensure_ascii=False,
            indent=2,
        )

        escalation_text = "Keine aktive Recovery-Eskalation."
        if recovery_escalation is not None and recovery_escalation.active:
            escalation_text = json.dumps(
                recovery_escalation.as_prompt_context(),
                ensure_ascii=False,
                indent=2,
            )

        repair_input = "\n".join(
            [
                "## Current Repair Planning Input",
                "",
                f"TASK_ID: {task.task_id}",
                f"USER_REQUEST:\n{task.user_request}",
                "",
                f"PROJECT_CONTEXT:\n{project_context}",
                "",
                f"FAILURE_ANALYSIS:\n{analysis_json}",
                "",
                f"PREVIOUS_REVIEW_FEEDBACK:\n{revision_json}",
                "",
                f"RECOVERY_ESCALATION:\n{escalation_text}",
                "",
                "## Repair Planning Contract",
                "",
                "Jede geplante Änderung muss eine unterstützte Dateioperation verwenden.",
                "Erlaubte action-Werte: create, create_directory, replace, insert_before, insert_after.",
                "",
                "Antworte ausschließlich als gültiges JSON.",
                "Verwende exakt diese Struktur:",
                "{",
                '  "summary": "Zusammenfassung der Reparatur",',
                '  "proposed_changes": [',
                "    {",
                '      "action": "replace",',
                '      "path": "relative/path.py",',
                '      "description": "Beschreibung der Reparatur"',
                "    }",
                "  ],",
                '  "rationale": "Begründung"',
                "}",
                "",
                "Gib keine zusätzlichen Felder und keinen Text außerhalb des JSON-Objekts aus.",
            ]
        )

        return compose_system_prompt(role_prompt, repair_input)

    @classmethod
    def _parse_response(cls, response: str) -> AgentPlan:
        if not isinstance(response, str) or not response.strip():
            raise ValueError("Repairer hat keine gültige Antwort geliefert.")

        try:
            data: Any = json.loads(response)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "Repairer-Antwort enthält kein gültiges JSON."
            ) from exc

        if not isinstance(data, dict):
            raise ValueError("Repairer-Antwort muss ein JSON-Objekt sein.")

        summary = data.get("summary")
        proposed_changes = data.get("proposed_changes", [])
        rationale = data.get("rationale", "")

        if not isinstance(summary, str) or not summary.strip():
            raise ValueError("Repairer-Antwort benötigt ein gültiges 'summary'.")

        if not isinstance(proposed_changes, list):
            raise ValueError("'proposed_changes' muss eine Liste sein.")

        for change in proposed_changes:
            if not isinstance(change, dict):
                raise ValueError(
                    "Jede geplante Reparatur muss ein JSON-Objekt sein."
                )

            action = change.get("action")
            if action not in cls.ALLOWED_ACTIONS:
                raise ValueError(
                    "Repairer benötigt ein gültiges 'action'-Feld "
                    "mit einer unterstützten Dateioperation."
                )

            for field in ("action", "path", "description"):
                value = change.get(field)
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(
                        f"Jede geplante Reparatur benötigt '{field}'."
                    )

        if not isinstance(rationale, str):
            raise ValueError("'rationale' muss ein String sein.")

        return AgentPlan(
            summary=summary,
            proposed_changes=proposed_changes,
            rationale=rationale,
            metadata={"source": "agent_repairer"},
        )
