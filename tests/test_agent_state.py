import pytest

from forgeai.ai.agent_state import AgentRun, AgentState


def test_agent_run_starts_idle():
    run = AgentRun("task-1")

    assert run.task_id == "task-1"
    assert run.state == AgentState.IDLE
    assert run.review_round == 0
    assert run.execution_round == 0
    assert run.repair_attempt == 0


def test_transition_records_history():
    run = AgentRun("task-1")

    run.transition(AgentState.PLANNING)

    assert run.state == AgentState.PLANNING
    assert len(run.history) == 1
    assert run.history[0]["state"] == "planning"


def test_review_round_increments():
    run = AgentRun("task-1")

    assert run.start_review() == 1
    assert run.start_review() == 2
    assert run.review_round == 2


def test_review_round_limit_is_enforced():
    run = AgentRun("task-1", max_review_rounds=2)

    run.start_review()
    run.start_review()

    with pytest.raises(RuntimeError, match="Review-Runden"):
        run.start_review()


def test_execution_round_increments():
    run = AgentRun("task-1")

    assert run.start_execution() == 1
    assert run.start_execution() == 2
    assert run.execution_round == 2


def test_repair_attempt_increments():
    run = AgentRun("task-1")

    assert run.start_repair() == 1
    assert run.start_repair() == 2
    assert run.repair_attempt == 2


def test_repair_limit_is_enforced():
    run = AgentRun("task-1", max_repair_attempts=2)

    run.start_repair()
    run.start_repair()

    with pytest.raises(RuntimeError, match="Reparaturversuche"):
        run.start_repair()


def test_terminal_states_are_recorded():
    run = AgentRun("task-1")

    run.complete()

    assert run.state == AgentState.COMPLETED
    assert run.history[-1]["state"] == "completed"


def test_failure_state_is_recorded():
    run = AgentRun("task-1")

    run.fail()

    assert run.state == AgentState.FAILED
    assert run.history[-1]["state"] == "failed"


def test_abort_state_is_recorded():
    run = AgentRun("task-1")

    run.abort()

    assert run.state == AgentState.ABORTED
    assert run.history[-1]["state"] == "aborted"


def test_invalid_state_is_rejected():
    run = AgentRun("task-1")

    with pytest.raises(ValueError, match="Ungültiger AgentState"):
        run.transition("not-a-state")