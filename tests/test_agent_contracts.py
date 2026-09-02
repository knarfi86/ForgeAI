import pytest

from forgeai.ai.agent_contracts import (
    AgentPlan,
    AgentTask,
    ReviewDecision,
    ReviewResult,
)


def test_agent_task_stores_request():
    task = AgentTask(
        task_id="task-1",
        user_request="Füge eine Login-Funktion hinzu.",
        project_path="C:/project",
    )

    assert task.task_id == "task-1"
    assert task.user_request == "Füge eine Login-Funktion hinzu."
    assert task.project_path == "C:/project"


def test_agent_task_accepts_metadata():
    task = AgentTask(
        task_id="task-1",
        user_request="Test",
        metadata={"source": "chat"},
    )

    assert task.metadata["source"] == "chat"


def test_agent_task_rejects_empty_id():
    with pytest.raises(ValueError):
        AgentTask(task_id=" ", user_request="Test")


def test_agent_task_rejects_empty_request():
    with pytest.raises(ValueError):
        AgentTask(task_id="task-1", user_request=" ")


def test_agent_plan_stores_proposal():
    plan = AgentPlan(
        summary="Login-Modul ergänzen.",
        proposed_changes=[
            {
                "action": "create",
                "path": "login.py",
            }
        ],
        rationale="Das Projekt benötigt eine getrennte Login-Komponente.",
    )

    assert plan.summary == "Login-Modul ergänzen."
    assert len(plan.proposed_changes) == 1
    assert plan.proposed_changes[0]["action"] == "create"


def test_agent_plan_accepts_empty_change_list():
    plan = AgentPlan(summary="Nur Analyse durchführen.")

    assert plan.proposed_changes == []


def test_agent_plan_rejects_empty_summary():
    with pytest.raises(ValueError):
        AgentPlan(summary=" ")


def test_review_decisions_are_complete():
    assert ReviewDecision.APPROVE.value == "approve"
    assert ReviewDecision.REVISE.value == "revise"
    assert ReviewDecision.REJECT.value == "reject"


def test_review_result_stores_findings():
    result = ReviewResult(
        decision=ReviewDecision.REVISE,
        findings=["Fehlende Fehlerbehandlung."],
        required_changes=["Exception Handling ergänzen."],
        rationale="Der Plan würde im Fehlerfall abbrechen.",
    )

    assert result.decision == ReviewDecision.REVISE
    assert result.findings == ["Fehlende Fehlerbehandlung."]
    assert result.required_changes == ["Exception Handling ergänzen."]


def test_review_result_accepts_approve():
    result = ReviewResult(
        decision=ReviewDecision.APPROVE,
        rationale="Der Plan ist schlüssig.",
    )

    assert result.decision == ReviewDecision.APPROVE


def test_review_result_rejects_invalid_decision():
    with pytest.raises(ValueError):
        ReviewResult(decision="maybe")


def test_review_result_accepts_metadata():
    result = ReviewResult(
        decision=ReviewDecision.APPROVE,
        metadata={"model": "test-model"},
    )

    assert result.metadata["model"] == "test-model"
