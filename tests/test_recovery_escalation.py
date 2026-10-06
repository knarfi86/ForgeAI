from forgeai.ai.agent_analyzer import AgentAnalyzer, RepairAnalysis
from forgeai.ai.agent_contracts import AgentPlan, AgentTask
from forgeai.ai.agent_orchestrator import AgentOrchestrator
from forgeai.ai.agent_repairer import AgentRepairer
from forgeai.ai.agent_state import AgentRun, AgentState
from forgeai.ai.model_router import ModelRouter
from forgeai.core.recovery_escalation import (
    RecoveryEscalationAction,
    RecoveryEscalationPolicy,
)
from forgeai.core.stagnation_detector import StagnationStatus


def stagnating_status() -> StagnationStatus:
    return StagnationStatus(
        active=True,
        error_signature="E-v1-same",
        same_error_count=3,
        repeated_paths=("main.py",),
        same_target_count=2,
        reason_codes=("repeated_failure", "repeated_target"),
        detected_after_repair_attempt=2,
    )


def test_policy_broadens_analysis_when_budget_remains():
    decision = RecoveryEscalationPolicy().decide(
        stagnating_status(),
        repair_attempt=2,
        max_repair_attempts=3,
    )

    assert decision.active is True
    assert decision.action == RecoveryEscalationAction.BROADEN_ANALYSIS
    assert decision.escalation_round == 1
    assert decision.failure_signature == "E-v1-same"
    assert decision.repeated_paths == ("main.py",)
    assert decision.remaining_repair_attempts == 1
    assert "stagnation_detected" in decision.reason_codes
    assert any("Caller" in item for item in decision.guidance)


def test_policy_stops_when_stagnation_exhausted_repair_budget():
    decision = RecoveryEscalationPolicy().decide(
        stagnating_status(),
        repair_attempt=3,
        max_repair_attempts=3,
        previous_escalation_round=1,
    )

    assert decision.active is True
    assert decision.action == RecoveryEscalationAction.STOP
    assert decision.escalation_round == 2
    assert decision.remaining_repair_attempts == 0
    assert "repair_budget_exhausted" in decision.reason_codes


def test_policy_is_inactive_without_stagnation():
    decision = RecoveryEscalationPolicy().decide(
        StagnationStatus(),
        repair_attempt=1,
        max_repair_attempts=3,
    )

    assert decision.active is False
    assert decision.action == RecoveryEscalationAction.NONE
    assert decision.remaining_repair_attempts == 2


def test_policy_stops_failed_recovery_when_budget_is_exhausted_without_stagnation():
    decision = RecoveryEscalationPolicy().decide(
        StagnationStatus(),
        repair_attempt=3,
        max_repair_attempts=3,
    )

    assert decision.active is True
    assert decision.action == RecoveryEscalationAction.STOP
    assert decision.reason_codes == ("repair_budget_exhausted",)


def _repair_round(orchestrator: AgentOrchestrator, output: str) -> AgentState:
    orchestrator.current_analysis = RepairAnalysis(
        summary="analysis",
        root_cause="cause",
        repair_requirements=["fix"],
    )
    orchestrator.current_plan = AgentPlan(
        summary="repair",
        proposed_changes=[{
            "action": "replace",
            "path": "main.py",
            "description": "repair target",
        }],
        metadata={"source": "agent_repairer"},
    )
    orchestrator.begin_repair()
    orchestrator.begin_execution()
    orchestrator.begin_testing()
    return orchestrator.handle_verification_result(False, output)


def test_orchestrator_escalates_after_repeated_failed_repair():
    run = AgentRun("task-1", max_repair_attempts=3)
    orchestrator = AgentOrchestrator(run)

    orchestrator.begin_execution()
    orchestrator.begin_testing()
    orchestrator.handle_verification_result(False, "KeyError: velocity")
    _repair_round(orchestrator, "KeyError: velocity")
    state = _repair_round(orchestrator, "KeyError: velocity")

    assert state == AgentState.ANALYZING
    assert run.stagnation_status.active is True
    assert run.recovery_escalation.action == RecoveryEscalationAction.BROADEN_ANALYSIS
    assert len(run.recovery_escalation_history) == 1


def test_orchestrator_stops_after_escalated_repair_exhausts_budget():
    run = AgentRun("task-1", max_repair_attempts=3)
    orchestrator = AgentOrchestrator(run)

    orchestrator.begin_execution()
    orchestrator.begin_testing()
    orchestrator.handle_verification_result(False, "KeyError: velocity")
    _repair_round(orchestrator, "KeyError: velocity")
    _repair_round(orchestrator, "KeyError: velocity")
    state = _repair_round(orchestrator, "KeyError: velocity")

    assert state == AgentState.FAILED
    assert run.recovery_escalation.action == RecoveryEscalationAction.STOP
    assert [entry.action for entry in run.recovery_escalation_history] == [
        RecoveryEscalationAction.BROADEN_ANALYSIS,
        RecoveryEscalationAction.STOP,
    ]


def test_orchestrator_stops_at_budget_even_if_final_failure_changed():
    run = AgentRun("task-1", max_repair_attempts=3)
    orchestrator = AgentOrchestrator(run)

    orchestrator.begin_execution()
    orchestrator.begin_testing()
    orchestrator.handle_verification_result(False, "KeyError: velocity")
    _repair_round(orchestrator, "KeyError: velocity")
    _repair_round(orchestrator, "KeyError: velocity")
    state = _repair_round(orchestrator, "TypeError: changed failure")

    assert run.stagnation_status.active is False
    assert state == AgentState.FAILED
    assert run.recovery_escalation.action == RecoveryEscalationAction.STOP
    assert "repair_budget_exhausted" in run.recovery_escalation.reason_codes


class _PromptRouter(ModelRouter):
    def __init__(self, response: str):
        self.response = response
        self.calls = []

    def generate(self, role, prompt, **kwargs):
        self.calls.append((role, prompt))
        return self.response


def test_analyzer_receives_script_derived_escalation_context():
    decision = RecoveryEscalationPolicy().decide(
        stagnating_status(), repair_attempt=2, max_repair_attempts=3
    )
    router = _PromptRouter(
        '{"summary":"broaden","findings":[],"root_cause":"unknown",'
        '"repair_requirements":["inspect callers"]}'
    )
    analyzer = AgentAnalyzer(router)
    analyzer.analyze(
        AgentTask("task-1", "repair"),
        "failed",
        "PROJECT_CONTEXT",
        recovery_escalation=decision,
    )

    prompt = router.calls[0][1]
    assert '"action": "broaden_analysis"' in prompt
    assert '"failure_signature": "E-v1-same"' in prompt
    assert '"repeated_paths": [\n    "main.py"\n  ]' in prompt
    assert "Erfinde keine Caller oder Abhängigkeiten" in prompt


def test_repairer_receives_script_derived_escalation_context():
    decision = RecoveryEscalationPolicy().decide(
        stagnating_status(), repair_attempt=2, max_repair_attempts=3
    )
    router = _PromptRouter(
        '{"summary":"repair","proposed_changes":[],"rationale":"evidence"}'
    )
    repairer = AgentRepairer(router)
    repairer.repair(
        AgentTask("task-1", "repair"),
        RepairAnalysis(summary="analysis"),
        "PROJECT_CONTEXT",
        recovery_escalation=decision,
    )

    prompt = router.calls[0][1]
    assert '"action": "broaden_analysis"' in prompt
    assert "stagnierende Reparaturplan nicht unverändert" in prompt
    assert "Nutze nur im aktuellen Projektkontext belegte Caller" in prompt
