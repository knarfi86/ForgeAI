from forgeai.ai.agent_contracts import AgentTask
from forgeai.ai.agent_state import AgentRun, AgentState
from forgeai.core.agent_reality import AgentReality, TaskReality


def test_task_reality_projects_agent_task() -> None:
    task = AgentTask(
        task_id="task-1",
        user_request="Add validation",
        project_path="C:/project",
        metadata={"source": "test"},
    )

    reality = TaskReality.from_agent_task(task)

    assert reality.task_id == task.task_id
    assert reality.user_request == task.user_request
    assert reality.project_path == "C:/project"
    assert reality.metadata == {"source": "test"}


def test_agent_reality_projects_task_and_run() -> None:
    task = AgentTask(
        task_id="task-1",
        user_request="Add validation",
        project_path="C:/project",
        metadata={"source": "test"},
    )

    run = AgentRun(
        task_id="task-1",
        state=AgentState.PLANNING,
        review_round=1,
        metadata={"model": "test-model"},
    )

    reality = AgentReality.from_task_and_run(
        task,
        run,
        agent_id="agent-1",
        provider="ollama",
        model="test-model",
        role="planner",
        run_id="run-1",
    )

    assert reality.identity.agent_id == "agent-1"
    assert reality.identity.provider == "ollama"
    assert reality.identity.model == "test-model"
    assert reality.task.task_id == "task-1"
    assert reality.task.user_request == "Add validation"
    assert reality.run.run_id == "run-1"
    assert reality.run.state == AgentState.PLANNING
    assert reality.run.review_round == 1


def test_agent_reality_projection_is_detached_from_sources() -> None:
    task = AgentTask(
        task_id="task-1",
        user_request="Add validation",
        project_path="C:/project",
        metadata={"source": "test"},
    )

    run = AgentRun(
        task_id="task-1",
        state=AgentState.PLANNING,
        metadata={"model": "test-model"},
    )

    reality = AgentReality.from_task_and_run(
        task,
        run,
        agent_id="agent-1",
        provider="ollama",
        model="test-model",
        role="planner",
        run_id="run-1",
    )

    reality.task.metadata["source"] = "changed"
    reality.run.metadata["model"] = "changed"

    assert task.metadata["source"] == "test"
    assert run.metadata["model"] == "test-model"


def test_agent_reality_rejects_invalid_task() -> None:
    run = AgentRun(task_id="task-1")

    try:
        AgentReality.from_task_and_run(
            "invalid",  # type: ignore[arg-type]
            run,
            agent_id="agent-1",
            provider="ollama",
            model="test-model",
            role="planner",
            run_id="run-1",
        )
    except TypeError as exc:
        assert "AgentTask" in str(exc)
    else:
        raise AssertionError("Expected TypeError")
