from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .agent_contracts import AgentPlan, AgentTask
from .model_router import ModelRouter


@dataclass
class RepairAnalysis:
    """Strukturierte Analyse eines fehlgeschlagenen Verifikationslaufs."""

    summary: str
    findings: list[str] = field(default_factory=list)
    root_cause: str = ""
    repair_requirements: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.summary.strip():
            raise ValueError("summary darf nicht leer sein.")


class AgentAnalyzer:
    """Analysiert fehlgeschlagene Tests, ohne selbst Dateien zu verändern."""

    def __init__(self, model_router: ModelRouter) -> None:
        self.model_router = model_router

    def analyze(
        self,
        task: AgentTask,
        test_output: str,
        project_context: str = "",
        *,
        current_plan: AgentPlan | None = None,
    ) -> RepairAnalysis:
        prompt = self._build_prompt(
            task=task,
            test_output=test_output,
            project_context=project_context,
            current_plan=current_plan,
        )

        response = self.model_router.generate(
            "advisor",
            prompt,
        )

        return self._parse_response(response)

    @staticmethod
    def _build_prompt(
        *,
        task: AgentTask,
        test_output: str,
        project_context: str,
        current_plan: AgentPlan | None,
    ) -> str:
        plan_text = "Kein aktueller Agentenplan vorhanden."

        if current_plan is not None:
            plan_text = (
                f"Zusammenfassung: {current_plan.summary}\n"
                f"Vorgeschlagene Änderungen: {current_plan.proposed_changes}\n"
                f"Begründung: {current_plan.rationale}"
            )

        return "\n".join(
            [
                "Du bist der Analyse-Agent von ForgeAI.",
                "",
                "Analysiere einen fehlgeschlagenen Verifikationslauf.",
                "Du darfst keine Dateien verändern und keine Änderungen ausführen.",
                "",
                f"TASK_ID: {task.task_id}",
                f"USER_REQUEST:\n{task.user_request}",
                "",
                f"CURRENT_PLAN:\n{plan_text}",
                "",
                f"PROJECT_CONTEXT:\n{project_context}",
                "",
                f"TEST_OUTPUT:\n{test_output}",
                "",
                "Ermittle:",
                "- die wichtigsten tatsächlichen Fehler",
                "- die wahrscheinlichste Ursache",
                "- konkrete Anforderungen für die Reparatur",
                "- welche Informationen noch fehlen, falls die Ursache nicht sicher bestimmbar ist",
                "",
                "Antworte ausschließlich als gültiges JSON.",
                "Verwende exakt diese Struktur:",
                "{",
                '  "summary": "Kurze Zusammenfassung des Problems",',
                '  "findings": ["Konkreter Befund"],',
                '  "root_cause": "Wahrscheinliche Ursache",',
                '  "repair_requirements": ["Konkrete Reparaturanforderung"]',
                "}",
            ]
        )

    @staticmethod
    def _parse_response(response: str) -> RepairAnalysis:
        if not isinstance(response, str) or not response.strip():
            raise ValueError("Analyzer hat keine gültige Antwort geliefert.")

        try:
            data: Any = json.loads(response)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "Analyzer-Antwort enthält kein gültiges JSON."
            ) from exc

        if not isinstance(data, dict):
            raise ValueError("Analyzer-Antwort muss ein JSON-Objekt sein.")

        summary = data.get("summary")
        findings = data.get("findings", [])
        root_cause = data.get("root_cause", "")
        repair_requirements = data.get("repair_requirements", [])

        if not isinstance(summary, str) or not summary.strip():
            raise ValueError("Analyzer-Antwort benötigt ein gültiges 'summary'.")

        if not isinstance(findings, list) or not all(
            isinstance(item, str) for item in findings
        ):
            raise ValueError("'findings' muss eine Liste aus Strings sein.")

        if not isinstance(root_cause, str):
            raise ValueError("'root_cause' muss ein String sein.")

        if not isinstance(repair_requirements, list) or not all(
            isinstance(item, str) for item in repair_requirements
        ):
            raise ValueError(
                "'repair_requirements' muss eine Liste aus Strings sein."
            )

        return RepairAnalysis(
            summary=summary,
            findings=findings,
            root_cause=root_cause,
            repair_requirements=repair_requirements,
            metadata={"source": "agent_analyzer"},
        )
