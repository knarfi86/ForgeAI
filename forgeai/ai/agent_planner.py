from __future__ import annotations

import json
from typing import Any

from .agent_contracts import AgentPlan, AgentTask
from .external_planner import ExternalPlanner
from .model_router import ModelRouter
from .prompt_roles import load_role_prompt
from .prompt_core import compose_system_prompt


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
        capability_context: dict[str, Any] | None = None,
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
            capability_context=capability_context or {},
        )

        response = self.model_router.generate(
            "planner",
            prompt,
            response_format={
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                    },
                    "proposed_changes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "action": {
                                    "type": "string",
                                    "enum": [
                                        "create",
                                        "create_directory",
                                        "replace",
                                        "insert_before",
                                        "insert_after",
                                    ],
                                },
                                "path": {
                                    "type": "string",
                                },
                                "description": {
                                    "type": "string",
                                },
                            },
                            "required": [
                                "action",
                                "path",
                                "description",
                            ],
                        },
                    },
                    "plugin_actions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "plugin_id": {"type": "string"},
                                "action": {"type": "string"},
                                "parameters": {"type": "object"},
                            },
                            "required": ["plugin_id", "action", "parameters"],
                        },
                    },
                    "rationale": {
                        "type": "string",
                    },
                },
                "required": [
                    "summary",
                    "proposed_changes",
                    "plugin_actions",
                    "rationale",
                ],
            },
        )

        return self._parse_response(response)

    @staticmethod
    def _build_prompt(
        *,
        task: AgentTask,
        project_context: str,
        external_context: str,
        revision_context: list[dict[str, Any]],
        capability_context: dict[str, Any] | None = None,
    ) -> str:
        role_prompt = load_role_prompt("project_planner")
        capability_context = capability_context or {}

        sections = [
            "## Current Planning Input",
            "",
            f"TASK_ID: {task.task_id}",
            f"USER_REQUEST:\n{task.user_request}",
            "",
            f"PROJECT_CONTEXT:\n{project_context}",
        ]

        if capability_context:
            sections.extend(
                [
                    "",
                    "CAPABILITY_CONTEXT:",
                    json.dumps(
                        capability_context,
                        ensure_ascii=False,
                        indent=2,
                    ),
                    "",
                    (
                        "Der Capability-Kontext beschreibt optionale Plugin-/Tool-"
                        "Fähigkeiten. Er schränkt normale Core-Dateiplanung nicht ein."
                    ),
                    (
                        "Behandle planned/unavailable oder nicht autorisierte Plugins "
                        "nicht als autonom ausführbare Werkzeuge."
                    ),
                    (
                        "runtime_availability=not_checked ist kein Beweis für reale "
                        "Laufzeitverfügbarkeit."
                    ),
                    (
                        "Nutze plugin_actions nur für konkrete, deklarierte Aktionen "
                        "aus CAPABILITY_CONTEXT. Normale Dateiänderungen benötigen "
                        "keine Plugin-Aktion."
                    ),
                    (
                        "manual_only darf als sichtbare Plugin-Aktion geplant werden; "
                        "die spätere Benutzerfreigabe gilt nur einmal für diesen Plan."
                    ),
                ]
            )

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
                    "Berücksichtige insbesondere alle evidenzbasierten findings und required_changes.",
                    "Ignoriere keine als notwendig markierte Änderung ohne nachvollziehbare Begründung.",
                ]
            )

        sections.extend(
            [
                "",
                "## Planning Contract",
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
                '  "plugin_actions": [',
                "    {",
                '      "plugin_id": "python",',
                '      "action": "test",',
                '      "parameters": {}',
                "    }",
                "  ],",
                '  "rationale": "Begründung des gewählten Ansatzes"',
                "}",
                "",
                "Gib keine zusätzlichen Felder und keinen Text außerhalb des JSON-Objekts aus.",
            ]
        )

        return compose_system_prompt(role_prompt, "\n".join(sections))

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
        plugin_actions = data.get("plugin_actions", [])
        rationale = data.get("rationale", "")

        if not isinstance(summary, str) or not summary.strip():
            raise ValueError("Planner-Antwort benötigt ein gültiges 'summary'.")

        if not isinstance(proposed_changes, list):
            raise ValueError(
                "'proposed_changes' muss eine Liste sein."
            )

        for change in proposed_changes:
            if not isinstance(change, dict):
                raise ValueError(
                    "Jede geplante Änderung muss ein JSON-Objekt sein."
                )

            allowed_actions = {
                "create",
                "create_directory",
                "replace",
                "insert_before",
                "insert_after",
            }

            if change.get("action") not in allowed_actions:
                raise ValueError(
                    "Planner benötigt ein gültiges 'action'-Feld "
                    "mit einer unterstützten Dateioperation."
                )
            for field in ("action", "path", "description"):
                value = change.get(field)
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(
                        f"Jede geplante Änderung benötigt '{field}'."
                    )

        if not isinstance(plugin_actions, list):
            raise ValueError("'plugin_actions' muss eine Liste sein.")

        if not isinstance(rationale, str):
            raise ValueError("'rationale' muss ein String sein.")

        return AgentPlan(
            summary=summary,
            proposed_changes=proposed_changes,
            rationale=rationale,
            metadata={
                "source": "agent_planner",
            },
            plugin_actions=plugin_actions,
        )
