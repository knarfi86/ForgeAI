from __future__ import annotations

import json
from typing import Any

from .agent_contracts import AgentPlan, ReviewDecision, ReviewResult
from .model_router import ModelRouter
from .prompt_core import compose_routed_prompt
from .prompt_roles import load_role_prompt


class AgentReviewer:
    """Prüft einen AgentPlan kritisch, ohne selbst Änderungen auszuführen."""

    def __init__(self, model_router: ModelRouter) -> None:
        self.model_router = model_router

    def review(
        self,
        plan: AgentPlan,
        project_context: str = "",
        capability_context: dict[str, Any] | None = None,
    ) -> ReviewResult:
        prompt = self._build_prompt(
            plan=plan,
            project_context=project_context,
            capability_context=capability_context or {},
        )

        response = self.model_router.generate(
            "reviewer",
            prompt,
            response_format={
                "type": "object",
                "properties": {
                    "decision": {
                        "type": "string",
                        "enum": ["approve", "revise", "reject"],
                    },
                    "findings": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "required_changes": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "rationale": {
                        "type": "string",
                    },
                },
                "required": [
                    "decision",
                    "findings",
                    "required_changes",
                    "rationale",
                ],
            },
        )

        return self._parse_response(response)

    @staticmethod
    def _build_prompt(
        *,
        plan: AgentPlan,
        project_context: str,
        capability_context: dict[str, Any] | None = None,
    ) -> str:
        role_prompt = load_role_prompt("plan_reviewer")
        capability_context = capability_context or {}
        plan_json = json.dumps(
            {
                "summary": plan.summary,
                "proposed_changes": plan.proposed_changes,
                "plugin_actions": plan.plugin_actions,
                "rationale": plan.rationale,
            },
            ensure_ascii=False,
            indent=2,
        )

        capability_json = (
            json.dumps(capability_context, ensure_ascii=False, indent=2)
            if capability_context
            else "Kein Capability-Kontext bereitgestellt."
        )

        review_input = "\n".join(
            [
                "## Current Review Input",
                "",
                f"PROJECT_CONTEXT:\n{project_context}",
                "",
                f"CAPABILITY_CONTEXT:\n{capability_json}",
                "",
                (
                    "Der Capability-Kontext beschreibt optionale Plugin-/Tool-"
                    "Fähigkeiten und schränkt normale Core-Dateiplanung nicht ein."
                ),
                (
                    "Beanstande nur eine konkrete Abhängigkeit von einem nicht "
                    "autonom nutzbaren Plugin, wenn der Plan die nötige "
                    "Benutzerfreigabe ignoriert; nicht gewöhnliche Dateiänderungen."
                ),
                (
                    "Prüfe plugin_actions gegen die deklarierten action_id-Werte "
                    "im CAPABILITY_CONTEXT. manual_only ist zulässig, wenn die "
                    "Aktion sichtbar im Plan steht und vom Benutzer freigegeben wird."
                ),
                (
                    "disabled, planned oder unavailable dürfen nicht als ausführbare "
                    "Plugin-Aktionen genehmigt werden."
                ),
                "",
                f"AGENT_PLAN:\n{plan_json}",
                "",
                "## Review Contract",
                "",
                "Antworte ausschließlich als gültiges JSON.",
                "Das JSON muss exakt diese Struktur besitzen:",
                "{",
                '  "decision": "approve",',
                '  "findings": ["Feststellung 1"],',
                '  "required_changes": ["Notwendige Änderung 1"],',
                '  "rationale": "Begründung der Entscheidung"',
                "}",
                "",
                'decision darf ausschließlich "approve", "revise" oder "reject" sein.',
                "Gib keine zusätzlichen Felder und keinen Text außerhalb des JSON-Objekts aus.",
            ]
        )

        user_input, separator, contract = review_input.partition("\n## Review Contract\n")
        if not separator:
            raise RuntimeError("Review Contract fehlt im Reviewer-Prompt.")
        return compose_routed_prompt(
            role_prompt,
            "## Review Contract\n" + contract,
            user_content=user_input,
        )

    @staticmethod
    def _parse_response(response: str) -> ReviewResult:
        if not isinstance(response, str) or not response.strip():
            raise ValueError("Reviewer hat keine gültige Antwort geliefert.")

        try:
            data: Any = json.loads(response)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "Reviewer-Antwort enthält kein gültiges JSON."
            ) from exc

        if not isinstance(data, dict):
            raise ValueError("Reviewer-Antwort muss ein JSON-Objekt sein.")

        decision = data.get("decision")
        findings = data.get("findings", [])
        required_changes = data.get("required_changes", [])
        rationale = data.get("rationale", "")

        try:
            decision = ReviewDecision(decision)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "Reviewer-Antwort enthält eine ungültige Entscheidung."
            ) from exc

        if not isinstance(findings, list) or not all(
            isinstance(item, str) for item in findings
        ):
            raise ValueError(
                "'findings' muss eine Liste aus Strings sein."
            )

        if not isinstance(required_changes, list) or not all(
            isinstance(item, str) for item in required_changes
        ):
            raise ValueError(
                "'required_changes' muss eine Liste aus Strings sein."
            )

        if not isinstance(rationale, str):
            raise ValueError("'rationale' muss ein String sein.")

        return ReviewResult(
            decision=decision,
            findings=findings,
            required_changes=required_changes,
            rationale=rationale,
            metadata={
                "source": "agent_reviewer",
            },
        )
