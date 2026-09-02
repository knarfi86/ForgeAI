from __future__ import annotations

from .agent_analyzer import AgentAnalyzer, RepairAnalysis
from .agent_contracts import AgentPlan, AgentTask, ReviewDecision, ReviewResult
from .agent_planner import AgentPlanner
from .agent_repairer import AgentRepairer
from .agent_reviewer import AgentReviewer
from .agent_state import AgentRun, AgentState


class AgentOrchestrator:
    """Steuert den Lebenszyklus eines Agentenlaufs.

    Der Orchestrator steuert ausschließlich den Ablauf.
    Planung, Review, Analyse, Reparatur und Ausführung werden über getrennte
    Komponenten angebunden.
    """

    def __init__(
        self,
        run: AgentRun,
        *,
        planner: AgentPlanner | None = None,
        reviewer: AgentReviewer | None = None,
        analyzer: AgentAnalyzer | None = None,
        repairer: AgentRepairer | None = None,
        review_enabled: bool = True,
        require_user_approval: bool = True,
    ) -> None:
        self.run = run
        self.planner = planner
        self.reviewer = reviewer
        self.analyzer = analyzer
        self.repairer = repairer
        self.review_enabled = review_enabled
        self.require_user_approval = require_user_approval
        self.current_plan: AgentPlan | None = None
        self.current_review: ReviewResult | None = None
        self.current_analysis: RepairAnalysis | None = None
        self.last_test_output: str = ""

    def start(self) -> AgentState:
        """Startet einen neuen Agentenlauf mit der Planungsphase."""
        if self.run.state != AgentState.IDLE:
            raise RuntimeError(
                f"Agentenlauf kann nicht gestartet werden: "
                f"aktueller Zustand ist {self.run.state.value!r}."
            )

        self.run.transition(AgentState.PLANNING)
        return self.run.state

    def plan(
        self,
        task: AgentTask,
        project_context: str = "",
    ) -> AgentPlan:
        """Erzeugt den Plan für die aktuelle Aufgabe."""
        if self.run.state != AgentState.PLANNING:
            raise RuntimeError(
                "Planung ist nur im Zustand 'planning' möglich."
            )

        if self.planner is None:
            raise RuntimeError(
                "Für diesen Agentenlauf wurde kein AgentPlanner konfiguriert."
            )

        self.current_plan = self.planner.plan(
            task,
            project_context,
            revision_context=self.run.revision_context,
        )
        self.current_review = None
        return self.current_plan

    def begin_review(self) -> AgentState:
        """Startet eine Review-Runde, sofern Reviews aktiviert sind."""
        if not self.review_enabled:
            return self.run.state

        self.run.start_review()
        return self.run.state

    def review(
        self,
        project_context: str = "",
    ) -> ReviewResult:
        """Prüft den aktuell geplanten Agentenplan."""
        if self.run.state != AgentState.REVIEWING:
            raise RuntimeError(
                "Review ist nur im Zustand 'reviewing' möglich."
            )

        if self.reviewer is None:
            raise RuntimeError(
                "Für diesen Agentenlauf wurde kein AgentReviewer konfiguriert."
            )

        if self.current_plan is None:
            raise RuntimeError(
                "Für das Review wurde noch kein AgentPlan erstellt."
            )

        self.current_review = self.reviewer.review(
            self.current_plan,
            project_context,
        )
        return self.current_review

    def handle_review_result(
        self,
        review_result: ReviewResult | None = None,
    ) -> AgentState:
        """Verarbeitet die Entscheidung eines normalen Plan-Reviews.

        APPROVE führt zur Freigabe bzw. Ausführung.
        REVISE führt zurück zur Planungsphase.
        REJECT beendet den Lauf als abgebrochen.
        """
        result = review_result or self.current_review

        if result is None:
            raise RuntimeError(
                "Es liegt kein ReviewResult zur Verarbeitung vor."
            )

        if not isinstance(result, ReviewResult):
            raise ValueError(
                "Ungültiges ReviewResult."
            )

        self.current_review = result

        if result.decision == ReviewDecision.APPROVE:
            return self.request_approval()

        if result.decision == ReviewDecision.REVISE:
            self._store_revision_context(result)
            self.run.transition(AgentState.PLANNING)
            return self.run.state

        if result.decision == ReviewDecision.REJECT:
            return self.abort()

        raise ValueError(
            f"Unbekannte Review-Entscheidung: {result.decision!r}"
        )

    def handle_repair_review_result(
        self,
        review_result: ReviewResult | None = None,
    ) -> AgentState:
        """Verarbeitet die Entscheidung eines Reparaturplan-Reviews.

        APPROVE führt zur Freigabe bzw. Ausführung.
        REVISE startet einen weiteren Reparaturversuch.
        REJECT beendet den Lauf als abgebrochen.
        """
        result = review_result or self.current_review

        if result is None:
            raise RuntimeError(
                "Es liegt kein ReviewResult zur Verarbeitung vor."
            )

        if not isinstance(result, ReviewResult):
            raise ValueError(
                "Ungültiges ReviewResult."
            )

        self.current_review = result

        if result.decision == ReviewDecision.APPROVE:
            return self.request_approval()

        if result.decision == ReviewDecision.REVISE:
            self._store_revision_context(result)
            return self.begin_repair()

        if result.decision == ReviewDecision.REJECT:
            return self.abort()

        raise ValueError(
            f"Unbekannte Review-Entscheidung: {result.decision!r}"
        )

    def _store_revision_context(
        self,
        result: ReviewResult,
    ) -> None:
        """Speichert Review-Feedback für die nächste Planungsrunde."""
        self.run.revision_context.append(
            {
                "review_round": self.run.review_round,
                "decision": result.decision.value,
                "findings": list(result.findings),
                "required_changes": list(result.required_changes),
                "rationale": result.rationale,
            }
        )

    def request_approval(
        self,
    ) -> AgentState:
        """Wechselt in den Freigabestatus, falls eine Freigabe nötig ist."""
        if not self.require_user_approval:
            return self.begin_execution()

        self.run.transition(AgentState.APPROVAL_REQUIRED)
        return self.run.state

    def approve(self) -> AgentState:
        """Setzt einen freigegebenen Lauf in die Ausführung."""
        if self.run.state != AgentState.APPROVAL_REQUIRED:
            raise RuntimeError(
                "Eine Freigabe ist im aktuellen Agentenzustand nicht möglich."
            )

        return self.begin_execution()

    def begin_execution(self) -> AgentState:
        """Startet eine Ausführungsrunde."""
        self.run.start_execution()
        return self.run.state

    def begin_testing(self) -> AgentState:
        """Startet die Verifikation nach einer Ausführung."""
        self.run.transition(AgentState.TESTING)
        return self.run.state

    def begin_analysis(self) -> AgentState:
        """Startet die Fehleranalyse nach einem fehlgeschlagenen Test."""
        self.run.transition(AgentState.ANALYZING)
        return self.run.state

    def analyze(
        self,
        task: AgentTask,
        test_output: str,
        project_context: str = "",
    ) -> RepairAnalysis:
        """Analysiert den aktuellen fehlgeschlagenen Verifikationslauf."""
        if self.run.state != AgentState.ANALYZING:
            raise RuntimeError(
                "Analyse ist nur im Zustand 'analyzing' möglich."
            )

        if self.analyzer is None:
            raise RuntimeError(
                "Für diesen Agentenlauf wurde kein AgentAnalyzer konfiguriert."
            )

        self.last_test_output = test_output

        self.current_analysis = self.analyzer.analyze(
            task,
            test_output,
            project_context,
            current_plan=self.current_plan,
        )
        return self.current_analysis

    def begin_repair(self) -> AgentState:
        """Startet einen Reparaturversuch."""
        self.run.start_repair()
        return self.run.state

    def repair(
        self,
        task: AgentTask,
        project_context: str = "",
        analysis: RepairAnalysis | None = None,
    ) -> AgentPlan:
        """Erzeugt aus der Fehleranalyse einen neuen Reparaturplan."""
        if self.run.state != AgentState.REPAIRING:
            raise RuntimeError(
                "Reparaturplanung ist nur im Zustand 'repairing' möglich."
            )

        if self.repairer is None:
            raise RuntimeError(
                "Für diesen Agentenlauf wurde kein AgentRepairer konfiguriert."
            )

        repair_analysis = analysis or self.current_analysis

        if repair_analysis is None:
            raise RuntimeError(
                "Für die Reparatur wurde noch keine Fehleranalyse erstellt."
            )

        self.current_analysis = repair_analysis
        self.current_plan = self.repairer.repair(
            task,
            repair_analysis,
            project_context,
            revision_context=self.run.revision_context,
        )
        self.current_review = None
        return self.current_plan

    def complete(self) -> AgentState:
        """Beendet einen erfolgreichen Lauf."""
        self.run.complete()
        return self.run.state

    def fail(self) -> AgentState:
        """Markiert den Lauf als endgültig fehlgeschlagen."""
        self.run.fail()
        return self.run.state

    def abort(self) -> AgentState:
        """Bricht den Lauf ab."""
        self.run.abort()
        return self.run.state
