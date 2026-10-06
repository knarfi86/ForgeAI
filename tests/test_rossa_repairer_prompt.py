from forgeai.ai.agent_analyzer import RepairAnalysis
from forgeai.ai.agent_contracts import AgentTask
from forgeai.ai.agent_repairer import AgentRepairer
from forgeai.core.recovery_escalation import (
    RecoveryEscalationAction,
    RecoveryEscalationDecision,
)


def make_task() -> AgentTask:
    return AgentTask(task_id="repair-rossa", user_request="Behebe den Fehler.")


def make_analysis() -> RepairAnalysis:
    return RepairAnalysis(
        summary="Verifikation fehlgeschlagen",
        findings=["ImportError in demo.py"],
        root_cause="Import fehlt",
        repair_requirements=["Import ergänzen"],
    )


def test_rossa_repairer_prompt_contains_core_role_and_evidence():
    prompt = AgentRepairer._build_prompt(
        task=make_task(),
        analysis=make_analysis(),
        project_context="demo.py enthält run()",
        revision_context=[{"required_changes": ["Test ergänzen"]}],
    )

    assert "# ROSSA Systems" in prompt
    assert "# ROSSA Role: Repair Planning Agent" in prompt
    assert "TASK_ID: repair-rossa" in prompt
    assert "PROJECT_CONTEXT:" in prompt
    assert "FAILURE_ANALYSIS:" in prompt
    assert "PREVIOUS_REVIEW_FEEDBACK:" in prompt
    assert "Test ergänzen" in prompt
    assert '"proposed_changes"' in prompt
    assert "Du bist der Reparatur-Agent von ForgeAI." not in prompt


def test_rossa_repairer_prompt_preserves_recovery_guidance():
    escalation = RecoveryEscalationDecision(
        active=True,
        action=RecoveryEscalationAction.BROADEN_ANALYSIS,
        escalation_round=2,
        failure_signature="E-same",
        repeated_paths=("main.py",),
        guidance=("Neue Evidence prüfen.",),
    )
    prompt = AgentRepairer._build_prompt(
        task=make_task(),
        analysis=make_analysis(),
        project_context="PROJECT",
        recovery_escalation=escalation,
    )

    assert '"action": "broaden_analysis"' in prompt
    assert '"failure_signature": "E-same"' in prompt
    assert "stagnierende Reparaturplan nicht unverändert" in prompt
    assert "Nutze nur im aktuellen Projektkontext belegte Caller" in prompt


def test_rossa_repairer_prompt_requires_json_only():
    prompt = AgentRepairer._build_prompt(
        task=make_task(),
        analysis=make_analysis(),
        project_context="",
    )
    assert "Antworte ausschließlich als gültiges JSON." in prompt
    assert "keinen Text außerhalb des JSON-Objekts" in prompt
