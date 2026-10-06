from __future__ import annotations

from dataclasses import replace

from .agent_analyzer import AgentAnalyzer, RepairAnalysis
from .agent_contracts import AgentPlan, AgentTask, ReviewDecision, ReviewResult
from .agent_planner import AgentPlanner
from .agent_repairer import AgentRepairer
from .agent_reviewer import AgentReviewer
from .agent_state import AgentRun, AgentState, VerificationRecord
from forgeai.core.agent_reality import AgentReality, RealitySource
from forgeai.core.stagnation_detector import StagnationDetector
from forgeai.core.recovery_escalation import (
    RecoveryEscalationAction,
    RecoveryEscalationPolicy,
)
from forgeai.core.verification_framework import (
    VerificationProfile,
    VerificationProfileRequirement,
    VerificationReport,
)
from forgeai.core.completion_gate import (
    CompletionEvidence,
    CompletionEvidenceCategory,
    CompletionEvidenceMode,
    CompletionEvidenceStatus,
    CompletionGate,
    CompletionOutcome,
)
from forgeai.core.plugin_manager import (
    CapabilityExecutionContext,
    CapabilityExecutionPlan,
    PluginManager,
)
from forgeai.core.capability_execution_gate import CapabilityExecutionGateResult
from forgeai.core.fact_evidence_provider import (
    FactContext,
    FactQuery,
    FactResolution,
    FactService,
)


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
        reality: AgentReality | None = None,
        stagnation_detector: StagnationDetector | None = None,
        recovery_escalation_policy: RecoveryEscalationPolicy | None = None,
        completion_gate: CompletionGate | None = None,
        completion_required_categories: tuple[CompletionEvidenceCategory, ...] = (
            CompletionEvidenceCategory.TECHNICAL,
        ),
        fact_service: FactService | None = None,
        capability_context: dict[str, object] | None = None,
    ) -> None:
        self.run = run
        self.planner = planner
        self.reviewer = reviewer
        self.analyzer = analyzer
        self.repairer = repairer
        self.review_enabled = review_enabled
        self.require_user_approval = require_user_approval
        self.reality = reality
        self.stagnation_detector = stagnation_detector or StagnationDetector()
        self.recovery_escalation_policy = recovery_escalation_policy or RecoveryEscalationPolicy()
        self.completion_gate = completion_gate or CompletionGate()
        self.completion_required_categories = tuple(completion_required_categories)
        self.fact_service = fact_service
        inherited_capability_context = self.run.metadata.get("capability_context", {})
        if capability_context is None and isinstance(inherited_capability_context, dict):
            capability_context = inherited_capability_context
        self.capability_context = dict(capability_context or {})
        self.current_plan: AgentPlan | None = None
        self.current_review: ReviewResult | None = None
        self.current_analysis: RepairAnalysis | None = None
        self.last_test_output: str = ""

    def attach_reality(self, reality: AgentReality) -> None:
        "Attach the Reality projection used for runtime observations."
        if not isinstance(reality, AgentReality):
            raise TypeError("reality must be an AgentReality instance.")
        self.reality = reality

    def _record_reality_state(self, phase: str) -> None:
        "Record the current AgentRun state when Reality is attached."
        if self.reality is None:
            return

        self.reality.record_run_state(
            phase=phase,
            actor=RealitySource.ORCHESTRATOR,
            run=self.run,
        )

    def start(self) -> AgentState:
        """Startet einen neuen Agentenlauf mit der Planungsphase."""
        if self.run.state != AgentState.IDLE:
            raise RuntimeError(
                f"Agentenlauf kann nicht gestartet werden: "
                f"aktueller Zustand ist {self.run.state.value!r}."
            )

        self.run.transition(AgentState.PLANNING)
        self._record_reality_state("planning")
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

        planner_kwargs = {
            "revision_context": self.run.revision_context,
        }
        if self.capability_context:
            planner_kwargs["capability_context"] = self.capability_context

        self.current_plan = self.planner.plan(
            task,
            project_context,
            **planner_kwargs,
        )
        self.current_review = None
        return self.current_plan

    def begin_review(self) -> AgentState:
        """Startet eine Review-Runde, sofern Reviews aktiviert sind."""
        if not self.review_enabled:
            return self.run.state

        self.run.start_review()
        self._record_reality_state("review")
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

        reviewer_kwargs = {}
        if self.capability_context:
            reviewer_kwargs["capability_context"] = self.capability_context

        self.current_review = self.reviewer.review(
            self.current_plan,
            project_context,
            **reviewer_kwargs,
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
        self._record_reality_state("approval")
        return self.run.state

    def approve(self) -> AgentState:
        """Setzt einen freigegebenen Lauf in die Ausführung.

        Sichtbare plugin_actions erhalten dabei eine einmalige Freigabe für
        diesen AgentRun. Globale Plugin-Autonomieeinstellungen bleiben unverändert.
        """
        if self.run.state != AgentState.APPROVAL_REQUIRED:
            raise RuntimeError(
                "Eine Freigabe ist im aktuellen Agentenzustand nicht möglich."
            )

        plugin_actions = (
            list(self.current_plan.plugin_actions)
            if self.current_plan is not None
            else []
        )
        approved_ids = tuple(
            dict.fromkeys(
                str(action.get("plugin_id", "")).strip()
                for action in plugin_actions
                if str(action.get("plugin_id", "")).strip()
            )
        )
        self.run.metadata["approved_plugin_ids"] = approved_ids
        self.run.metadata["approved_plugin_actions"] = tuple(
            {
                "plugin_id": str(action.get("plugin_id", "")).strip(),
                "action": str(action.get("action", "")).strip(),
                "parameters": dict(action.get("parameters", {})),
            }
            for action in plugin_actions
        )
        return self.begin_execution()

    def begin_execution(self) -> AgentState:
        """Startet eine Ausführungsrunde."""
        self.run.start_execution()
        self._record_reality_state("execution")
        return self.run.state

    def begin_testing(self) -> AgentState:
        """Startet die Verifikation nach einer Ausführung."""
        self.run.transition(AgentState.TESTING)
        self._record_reality_state("testing")
        return self.run.state

    def begin_analysis(self) -> AgentState:
        """Startet die Fehleranalyse nach einem fehlgeschlagenen Test."""
        self.run.transition(AgentState.ANALYZING)
        self._record_reality_state("analysis")
        return self.run.state

    def handle_verification_result(
        self,
        success: bool,
        test_output: str = "",
    ) -> AgentState:
        """Verarbeitet das Ergebnis des technischen Verifikationslaufs."""
        if self.run.state != AgentState.TESTING:
            raise RuntimeError(
                "Das Verifikationsergebnis kann nur im Zustand "
                "'testing' verarbeitet werden."
            )

        self.last_test_output = test_output

        planned_paths = tuple(sorted({
            change["path"]
            for change in (self.current_plan.proposed_changes if self.current_plan else [])
            if isinstance(change.get("path"), str) and change["path"]
        }))
        previous_failure = self._latest_failure_signature()
        verification = self.run.record_verification(success, test_output, planned_paths)
        self._record_repair_outcome_if_applicable(previous_failure, verification)
        self.run.stagnation_status = self.stagnation_detector.evaluate(
            self.run.verification_history,
            self.run.repair_history,
        )

        previous_escalation_round = (
            self.run.recovery_escalation_history[-1].escalation_round
            if self.run.recovery_escalation_history
            else 0
        )

        if success:
            self.run.record_recovery_escalation(
                self.recovery_escalation_policy.decide(
                    self.run.stagnation_status,
                    repair_attempt=0,
                    max_repair_attempts=self.run.max_repair_attempts,
                    previous_escalation_round=previous_escalation_round,
                )
            )
            self.run.add_completion_evidence(
                CompletionEvidence(
                    evidence_id="completion:technical:latest",
                    category=CompletionEvidenceCategory.TECHNICAL,
                    status=CompletionEvidenceStatus.PASS,
                    summary="Technische Verifikation erfolgreich.",
                    source="agent_verification",
                    mode=CompletionEvidenceMode.FACT,
                    observed_value=test_output,
                    execution_round=self.run.execution_round,
                )
            )
            return self.evaluate_completion()

        escalation = self.recovery_escalation_policy.decide(
            self.run.stagnation_status,
            repair_attempt=self.run.repair_attempt,
            max_repair_attempts=self.run.max_repair_attempts,
            previous_escalation_round=previous_escalation_round,
        )
        self.run.record_recovery_escalation(escalation)

        if escalation.action == RecoveryEscalationAction.STOP:
            return self.fail()

        return self.begin_analysis()


    def preflight_capability_execution(
        self,
        plugin_manager: PluginManager,
        plan: CapabilityExecutionPlan | None = None,
        *,
        project_path: str | None = None,
        metadata: dict | None = None,
    ) -> CapabilityExecutionGateResult:
        """Validate one optional plugin plan before any executor may run.

        This gate is intentionally separate from ordinary core file execution.
        It re-checks current authorization, runtime facts, dependencies, executor
        presence and verification profiles, then records the evidence in AgentRun.
        """
        if self.run.state != AgentState.EXECUTING:
            raise RuntimeError(
                "Capability-Preflight ist nur im Zustand 'executing' möglich."
            )
        if not isinstance(plugin_manager, PluginManager):
            raise TypeError("plugin_manager muss PluginManager sein.")

        capability_plan = plan
        if capability_plan is None:
            if not self.run.capability_plans:
                raise RuntimeError("Kein CapabilityExecutionPlan für diesen Lauf vorhanden.")
            capability_plan = self.run.capability_plans[-1]

        context = CapabilityExecutionContext(
            task_id=self.run.task_id,
            execution_round=self.run.execution_round,
            project_path=project_path or capability_plan.project_path,
            metadata=dict(metadata or {}),
        )
        result = plugin_manager.preflight_execution(capability_plan, context)
        self.run.metadata["capability_execution_gate"] = dict(result.as_dict())

        known_fact_ids = {record.fact_id for record in self.run.fact_history}
        for record in result.fact_records:
            if record.fact_id not in known_fact_ids:
                self.run.record_fact(record)
                known_fact_ids.add(record.fact_id)

        if result.ready:
            registry = plugin_manager.verification_registry
            for profile_id in result.verification_profiles:
                if registry is None:
                    raise RuntimeError(
                        "Capability Gate meldet VerificationProfile ohne Registry."
                    )
                self.require_verification_profile(registry.get_profile(profile_id))
            self._record_reality_state("capability_gate_ready")
        else:
            self._record_reality_state("capability_gate_blocked")

        return result

    def execute_capability_plan(
        self,
        plugin_manager: PluginManager,
        plan: CapabilityExecutionPlan | None = None,
        *,
        project_path: str | None = None,
        metadata: dict | None = None,
    ) -> tuple[object, ...]:
        """Execute an explicit plugin/tool plan through the mandatory gate.

        This is the orchestrator entry point for future concrete plugin_actions.
        It is never invoked automatically for ordinary file-change plans.
        """
        capability_plan = plan
        if capability_plan is None:
            if not self.run.capability_plans:
                raise RuntimeError("Kein CapabilityExecutionPlan für diesen Lauf vorhanden.")
            capability_plan = self.run.capability_plans[-1]

        execution_metadata = dict(metadata or {})
        if "approved_plugin_ids" not in execution_metadata:
            approved = self.run.metadata.get("approved_plugin_ids", ())
            execution_metadata["approved_plugin_ids"] = tuple(approved)
        if "approved_plugin_actions" not in execution_metadata:
            approved_actions = self.run.metadata.get("approved_plugin_actions", ())
            execution_metadata["approved_plugin_actions"] = tuple(approved_actions)

        gate = self.preflight_capability_execution(
            plugin_manager,
            capability_plan,
            project_path=project_path,
            metadata=execution_metadata,
        )
        if not gate.ready:
            raise RuntimeError(
                "Capability Execution Gate blockiert die Plugin-Ausführung: "
                + ", ".join(gate.reason_codes)
            )

        context = CapabilityExecutionContext(
            task_id=self.run.task_id,
            execution_round=self.run.execution_round,
            project_path=project_path or capability_plan.project_path,
            metadata=execution_metadata,
        )
        try:
            results = plugin_manager.execute_serial(capability_plan, context)
        finally:
            # One-shot approval is consumed by the execution attempt itself.
            self.run.metadata["approved_plugin_ids"] = ()
            self.run.metadata["approved_plugin_actions"] = ()
        history = self.run.metadata.setdefault("capability_execution_history", [])
        if isinstance(history, list):
            history.append(
                {
                    "execution_round": self.run.execution_round,
                    "plugins": tuple(step.plugin_id for step in capability_plan.steps),
                    "actions": tuple(
                        {
                            "plugin_id": step.plugin_id,
                            "action": step.action_id,
                            "parameters": dict(step.parameters),
                        }
                        for step in capability_plan.steps
                    ),
                    "verification_profiles": gate.verification_profiles,
                    "result_count": len(results),
                }
            )
        self._record_reality_state("capability_execution")
        return results


    def execute_current_plugin_actions(
        self,
        plugin_manager: PluginManager,
        *,
        project_path: str | None = None,
    ) -> tuple[object, ...]:
        """Build and execute the current AgentPlan's explicit plugin_actions."""
        if self.current_plan is None:
            raise RuntimeError("Kein aktueller AgentPlan vorhanden.")
        if not self.current_plan.plugin_actions:
            return ()

        action_plan = plugin_manager.build_action_execution_plan(
            self.current_plan.summary,
            self.current_plan.plugin_actions,
            project_path=project_path,
        )
        if action_plan.blocked:
            details = []
            for item in action_plan.blocked:
                reason = ", ".join(item.reasons) or item.authorization.value
                details.append(f"{item.plugin_id}: {reason}")
            raise RuntimeError(
                "Plugin-Aktionsplan ist nicht ausführbar: " + " | ".join(details)
            )

        self.run.record_capability_plan(action_plan)
        return self.execute_capability_plan(
            plugin_manager,
            action_plan,
            project_path=project_path,
        )

    def pending_verification_profile_ids(self) -> tuple[str, ...]:
        """Public read-only view of required verification profiles still pending."""
        return self._pending_required_verification_profiles()


    def resolve_fact(
        self,
        query: FactQuery,
        *,
        project_path: str | None = None,
        metadata: dict | None = None,
        force_refresh: bool = False,
    ) -> FactResolution:
        """Resolve one objective fact through the central script/API-first layer.

        The orchestrator records every fresh observation in AgentRun. Reused
        fresh cache entries remain traceable by their original fact_id and are
        not duplicated in history.
        """
        if self.fact_service is None:
            raise RuntimeError("Für diesen Agentenlauf wurde kein FactService konfiguriert.")

        context = FactContext(
            task_id=self.run.task_id,
            execution_round=self.run.execution_round,
            project_path=project_path,
            metadata=dict(metadata or {}),
        )
        resolution = self.fact_service.resolve(
            query,
            context,
            force_refresh=force_refresh,
        )
        if not resolution.used_cache:
            self.run.record_fact(resolution.record)
            self._record_reality_state("fact_observed")
        return resolution


    def require_verification_profile(
        self,
        profile: VerificationProfile,
    ) -> tuple[CompletionEvidenceCategory, ...]:
        """Declare a profile before completion so its categories become mandatory."""
        if not isinstance(profile, VerificationProfile):
            raise TypeError("profile muss VerificationProfile sein.")

        requirement = VerificationProfileRequirement.from_profile(profile)
        self.run.require_verification_profile(requirement)
        categories = list(self.completion_required_categories)
        for category in profile.required_categories:
            if category not in categories:
                categories.append(category)
        self.completion_required_categories = tuple(categories)
        return self.completion_required_categories

    def handle_verification_report(
        self,
        report: VerificationReport,
        *,
        evaluate: bool = False,
    ) -> AgentState:
        """Accept one fresh profile report and expose its evidence to CompletionGate."""
        if not isinstance(report, VerificationReport):
            raise TypeError("report muss VerificationReport sein.")
        if report.task_id != self.run.task_id:
            raise ValueError("VerificationReport.task_id passt nicht zum AgentRun.")
        if report.execution_round != self.run.execution_round:
            raise ValueError("VerificationReport.execution_round ist nicht aktuell.")
        if not any(
            item.profile_id == report.profile_id
            for item in self.run.required_verification_profiles
        ):
            raise ValueError("VerificationProfile wurde für diesen Lauf nicht angefordert.")
        if self.run.state not in {AgentState.TESTING, AgentState.COMPLETION_CHECKING}:
            raise RuntimeError(
                "VerificationReport kann nur während testing/completion_checking "
                "übernommen werden."
            )

        self.run.record_verification_report(report)
        for evidence in report.to_completion_evidence():
            self.run.add_completion_evidence(evidence)

        self._record_reality_state("verification_profile")
        if evaluate:
            return self.evaluate_completion()
        return self.run.state

    def add_completion_evidence(
        self,
        evidence: CompletionEvidence,
        *,
        evaluate: bool = False,
    ) -> AgentState:
        """Adds externally verified completion evidence.

        Future runtime, visual and semantic verifiers use this single entry point.
        The evidence itself must already have been established by a tool or be an
        evidence-backed inference; the CompletionGate never invents observations.
        """
        self.run.add_completion_evidence(evidence)
        if evaluate:
            return self.evaluate_completion()
        return self.run.state

    def evaluate_completion(self) -> AgentState:
        """Evaluate current completion evidence and map the result to AgentState."""
        decision = self.completion_gate.evaluate(
            self.run.completion_evidence,
            required_categories=self.completion_required_categories,
            current_execution_round=self.run.execution_round,
        )

        pending_profiles = self._pending_required_verification_profiles()
        if pending_profiles and decision.outcome == CompletionOutcome.COMPLETED:
            decision = replace(
                decision,
                outcome=CompletionOutcome.PENDING,
                reason_codes=tuple(dict.fromkeys(
                    (*decision.reason_codes, "required_verification_profile_pending")
                )),
            )

        self.run.record_completion_decision(decision)

        if decision.outcome == CompletionOutcome.COMPLETED:
            return self.complete()
        if decision.outcome == CompletionOutcome.PARTIALLY_COMPLETED:
            return self.partial_complete()
        if decision.outcome == CompletionOutcome.FAILED:
            return self.fail()

        self.run.transition(AgentState.COMPLETION_CHECKING)
        self._record_reality_state("completion_checking")
        return self.run.state


    def _pending_required_verification_profiles(self) -> tuple[str, ...]:
        pending: list[str] = []
        for requirement in self.run.required_verification_profiles:
            report = next((
                item for item in reversed(self.run.verification_reports)
                if item.profile_id == requirement.profile_id
                and item.execution_round == self.run.execution_round
            ), None)
            if report is None:
                pending.append(requirement.profile_id)
                continue

            required_ids = set(requirement.required_check_ids)
            passed_ids = {
                result.check_id
                for result in report.results
                if result.status.value == "pass"
            }
            failed_ids = {
                result.check_id
                for result in report.results
                if result.status.value == "fail"
            }
            if required_ids - passed_ids - failed_ids:
                pending.append(requirement.profile_id)
        return tuple(pending)



    def _latest_failure_signature(self) -> str | None:
        for entry in reversed(self.run.verification_history):
            if not entry.success and entry.failure_fingerprint:
                return entry.failure_fingerprint
        return None

    def _record_repair_outcome_if_applicable(
        self,
        failure_before: str | None,
        verification: VerificationRecord,
    ) -> None:
        if self.run.repair_attempt <= 0:
            return
        if any(
            entry.repair_attempt == self.run.repair_attempt
            for entry in self.run.repair_history
        ):
            return
        if self.current_analysis is None or self.current_plan is None:
            return
        if self.current_plan.metadata.get("source") != "agent_repairer":
            return

        planned_paths = tuple(sorted({
            change["path"]
            for change in self.current_plan.proposed_changes
            if isinstance(change.get("path"), str) and change["path"]
        }))
        self.run.record_repair_outcome(
            failure_before=failure_before,
            verification=verification,
            analysis_summary=self.current_analysis.summary,
            root_cause=self.current_analysis.root_cause,
            repair_requirements=tuple(self.current_analysis.repair_requirements),
            plan_summary=self.current_plan.summary,
            planned_paths=planned_paths,
        )

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
            recovery_escalation=self.run.recovery_escalation,
        )
        return self.current_analysis

    def begin_repair(self) -> AgentState:
        """Startet einen Reparaturversuch."""
        self.run.start_repair()
        self._record_reality_state("repair")
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
        repair_kwargs = {
            "revision_context": self.run.revision_context,
            "recovery_escalation": self.run.recovery_escalation,
        }
        if self.capability_context:
            repair_kwargs["capability_context"] = self.capability_context
        self.current_plan = self.repairer.repair(
            task,
            repair_analysis,
            project_context,
            **repair_kwargs,
        )
        self.current_review = None
        return self.current_plan

    def complete(self) -> AgentState:
        """Beendet einen erfolgreichen Lauf."""
        self.run.complete()
        self._record_reality_state("completed")
        return self.run.state

    def partial_complete(self) -> AgentState:
        """Beendet einen Lauf mit belegter, aber unvollständiger Auftragserfüllung."""
        self.run.partial_complete()
        self._record_reality_state("partially_completed")
        return self.run.state

    def complete_without_changes(self) -> AgentState:
        """Beendet einen Lauf erfolgreich, wenn keine änderungen erforderlich sind."""
        return self.complete()

    def fail(self) -> AgentState:
        """Markiert den Lauf als endgültig fehlgeschlagen."""
        self.run.fail()
        self._record_reality_state("failed")
        return self.run.state

    def abort(self) -> AgentState:
        """Bricht den Lauf ab."""
        self.run.abort()
        self._record_reality_state("aborted")
        return self.run.state
