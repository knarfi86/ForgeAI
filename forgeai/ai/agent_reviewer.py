from __future__ import annotations

import json
from typing import Any

from .agent_contracts import AgentPlan, ReviewDecision, ReviewResult
from .model_router import ModelRouter


class AgentReviewer:
    """Prüft einen AgentPlan kritisch, ohne selbst Änderungen auszuführen."""

    def __init__(self, model_router: ModelRouter) -> None:
        self.model_router = model_router

    def review(
        self,
        plan: AgentPlan,
        project_context: str = "",
    ) -> ReviewResult:
        prompt = self._build_prompt(
            plan=plan,
            project_context=project_context,
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
    ) -> str:
        plan_json = json.dumps(
            {
                "summary": plan.summary,
                "proposed_changes": plan.proposed_changes,
                "rationale": plan.rationale,
            },
            ensure_ascii=False,
            indent=2,
        )

        return "\n".join(
            [
                "Du bist der kritische Review-Agent von ForgeAI.",
                "",
                "Prüfe den folgenden Agentenplan.",
                "Du darfst keine Dateien verändern und keine Änderungen ausführen.",
                "",
                "Bewerte insbesondere:",
                "- fachliche Korrektheit",
                "- technische Plausibilität",
                "- Architekturverträglichkeit",
                "- mögliche Seiteneffekte",
                "- Vollständigkeit",
                "- Sicherheit",
                "- Testbarkeit",
                "",
                f"PROJECT_CONTEXT:\n{project_context}",
                "",
                f"AGENT_PLAN:\n{plan_json}",
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
            ]
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
