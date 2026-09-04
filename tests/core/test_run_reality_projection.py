from forgeai.ai.agent_state import AgentRun, AgentState
from forgeai.core.agent_reality import RunReality


def test_run_reality_projects_agent_run() -> None:
    run = AgentRun(
        task_id="task-1",
        state=AgentState.REPAIRING,
        review_round=2,
        execution_round=3,
        repair_attempt=1,
        max_review_rounds=3,
        max_repair_attempts=3,
        history=[
            {
                "state": "planning",
                "review_round": 0,
                "execution_round": 0,
                "repair_attempt": 0,
            },
        ],
        metadata={"model": "test-model"},
        revision_context=[
            {
                "review_round": 1,
                "decision": "revise",
                "findings": ["missing validation"],
                "required_changes": ["add validation"],
                "rationale": "required by review",
            },
        ],
    )

    reality = RunReality.from_agent_run(
        run,
        run_id="run-1",
    )

    assert reality.run_id == "run-1"
    assert reality.state == AgentState.REPAIRING
    assert reality.review_round == 2
    assert reality.execution_round == 3
    assert reality.repair_attempt == 1
    assert reality.max_review_rounds == 3
    assert reality.max_repair_attempts == 3
    assert reality.metadata == {"model": "test-model"}
    assert reality.revision_context[0]["decision"] == "revise"
    assert reality.history[0]["state"] == "planning"


def test_run_reality_projection_is_detached_from_agent_run() -> None:
    run = AgentRun(
        task_id="task-1",
        metadata={"model": "test-model"},
    )

    reality = RunReality.from_agent_run(
        run,
        run_id="run-1",
    )

    reality.metadata["model"] = "changed"

    assert run.metadata["model"] == "test-model"


def test_run_reality_rejects_invalid_source() -> None:
    try:
        RunReality.from_agent_run("invalid", run_id="run-1")  # type: ignore[arg-type]
    except TypeError as exc:
        assert "AgentRun" in str(exc)
    else:
        raise AssertionError("Expected TypeError")
