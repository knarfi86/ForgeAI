from __future__ import annotations

import json
from typing import Any

from .agent_contracts import AgentPlan, AgentTask
from .external_planner import ExternalPlanner
from .model_router import ModelRouter


class AgentPlanner:
    """Erzeugt aus einer Aufgabe einen strukturierten AgentPlan.

    Der Planner verändert niemals selbst Dateien.
    Ein optionaler ExternalPlanner kann zusätzliche Planungshinweise liefern.
    """

    def __init__(
        self,
        model_router: ModelRouter,
        *,
        external_planner: ExternalPlanner | None = None,
    ) -> None:
        self.model_router = model_router
        self.external_planner = external_planner

    def plan(
        self,
        task: AgentTask,
        project_context: str = "",
        revision_context: list[dict[str, Any]] | None = None,
    ) -> AgentPlan:
        external_context = ""

        if self.external_planner is not None:
            external_context = self.external_planner.plan(
                task,
                project_context,
            )

        prompt = self._build_prompt(
            task=task,
            project_context=project_context,
            external_context=external_context,
            revision_context=revision_context or [],
        )

        response = self.model_router.generate(
            "planner",
            prompt,
        )

        return self._parse_response(response)

    @staticmethod
    def _build_prompt(
        *,
        task: AgentTask,
        project_context: str,
        external_context: str,
        revision_context: list[dict[str, Any]],
    ) -> str:
        sections = [
            "Du bist der Planungsagent von ForgeAI.",
            "",
            "Erstelle einen konkreten, strukturierten Plan für die folgende Aufgabe.",
            "Du darfst keine Dateien selbst verändern.",
            "",
            f"TASK_ID: {task.task_id}",
            f"USER_REQUEST:\n{task.user_request}",
            "",
            f"PROJECT_CONTEXT:\n{project_context}",
        ]

        if external_context:
            sections.extend(
                [
                    "",
                    "EXTERNAL_PLANNER_INPUT:",
                    external_context,
                    "",
                    "Nutze den externen Planungsvorschlag kritisch.",
                    "Übernimm ihn nicht automatisch.",
                ]
            )

        if revision_context:
            sections.extend(
                [
                    "",
                    "REVISION_CONTEXT:",
                    json.dumps(
                        revision_context,
                        ensure_ascii=False,
                        indent=2,
                    ),
                    "",
                    "Überarbeite den Plan anhand der bisherigen Review-Ergebnisse.",
                    "Berücksichtige insbesondere alle findings und required_changes.",
                    "Ignoriere keine als notwendig markierte Änderung.",
                ]
            )

        sections.extend(
            [
                "",
                "Antworte ausschließlich als gültiges JSON.",
                "Das JSON muss exakt diese Struktur besitzen:",
                "{",
                '  "summary": "Kurze Zusammenfassung des Plans",',
                '  "proposed_changes": [',
                '    {',
                '      "action": "replace",',
                '      "path": "relative/path.py",',
                '      "description": "Beschreibung der geplanten Änderung"',
                "    }",
                "  ],",
                '  "rationale": "Begründung des gewählten Ansatzes"',
                "}",
            ]
        )

        return "\n".join(sections)

    @staticmethod
    def _parse_response(response: str) -> AgentPlan:
        if not isinstance(response, str) or not response.strip():
            raise ValueError("Planner hat keine gültige Antwort geliefert.")

        try:
            data: Any = json.loads(response)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "Planner-Antwort enthält kein gültiges JSON."
            ) from exc

        if not isinstance(data, dict):
            raise ValueError("Planner-Antwort muss ein JSON-Objekt sein.")

        summary = data.get("summary")
        proposed_changes = data.get("proposed_changes", [])
        rationale = data.get("rationale", "")

        if not isinstance(summary, str) or not summary.strip():
            raise ValueError("Planner-Antwort benötigt ein gültiges 'summary'.")

        if not isinstance(proposed_changes, list):
            raise ValueError(
                "'proposed_changes' muss eine Liste sein."
            )

        for change in proposed_changes:
            allowed_actions = {"create", "create_directory", "replace", "insert_before", "insert_after"}
            if change.get("action") not in allowed_actions:
                raise ValueError("Planner benötigt ein gültiges 'action'-Feld mit einer unterstützten Dateioperation.")

            if not isinstance(change, dict):
                raise ValueError(
                    "Jede geplante Änderung muss ein JSON-Objekt sein."
                )

            for field in ("action", "path", "description"):
                value = change.get(field)
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(
                        f"Jede geplante Änderung benötigt '{field}'."
                    )

        if not isinstance(rationale, str):
            raise ValueError("'rationale' muss ein String sein.")

        return AgentPlan(
            summary=summary,
            proposed_changes=proposed_changes,
            rationale=rationale,
            metadata={
                "source": "agent_planner",
            },
        )
