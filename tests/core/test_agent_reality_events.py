from forgeai.ai.agent_contracts import AgentTask
from forgeai.ai.agent_state import AgentRun, AgentState
from forgeai.core.agent_reality import (
    AgentReality,
    EventType,
    RealitySource,
)


def build_reality() -> AgentReality:
    task = AgentTask(
        task_id="task-1",
        user_request="Test agent events",
        project_path="C:/project",
    )

    run = AgentRun(
        task_id="task-1",
        state=AgentState.IDLE,
    )

    return AgentReality.from_task_and_run(
        task,
        run,
        agent_id="agent-1",
        provider="ollama",
        model="test-model",
        role="planner",
        run_id="run-1",
    )


def test_record_run_state_creates_event() -> None:
    reality = build_reality()

    event = reality.record_run_state(
        phase="planning",
    )

    assert event.event_type == EventType.STATE_CHANGED
    assert event.task_id == "task-1"
    assert event.run_id == "run-1"
    assert event.actor == RealitySource.ORCHESTRATOR
    assert event.state_before is None
    assert event.state_after == AgentState.IDLE.value
    assert len(reality.events) == 1


def test_record_run_state_tracks_state_changes() -> None:
    reality = build_reality()

    first = reality.record_run_state(
        phase="planning",
    )

    reality.run.state = AgentState.PLANNING

    second = reality.record_run_state(
        phase="planning",
    )

    assert first.state_after == AgentState.IDLE.value
    assert second.state_before == AgentState.IDLE.value
    assert second.state_after == AgentState.PLANNING.value
    assert second.payload["review_round"] == 0
    assert second.payload["execution_round"] == 0
    assert second.payload["repair_attempt"] == 0


def test_record_run_state_uses_sequential_event_ids() -> None:
    reality = build_reality()

    first = reality.record_run_state(phase="planning")
    second = reality.record_run_state(phase="planning")

    assert first.event_id == "run-1:state:1"
    assert second.event_id == "run-1:state:2"
