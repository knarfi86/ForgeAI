from forgeai.ai.agent_contracts import AgentTask
from forgeai.ai.agent_orchestrator import AgentOrchestrator
from forgeai.ai.agent_state import AgentRun, AgentState
from forgeai.core.agent_reality import (
    AgentIdentity,
    AgentReality,
    EventType,
    RealitySource,
    RunReality,
    TaskReality,
)


def build_orchestrator_with_reality() -> tuple[AgentOrchestrator, AgentReality]:
    task = AgentTask(
        task_id="task-1",
        user_request="Test orchestrator events",
        project_path="C:/project",
    )

    run = AgentRun(
        task_id=task.task_id,
        state=AgentState.IDLE,
    )

    reality = AgentReality(
        identity=AgentIdentity(
            agent_id="agent-1",
            provider="ollama",
            model="test-model",
            role="planner",
        ),
        task=TaskReality.from_agent_task(task),
        run=RunReality.from_agent_run(
            run,
            run_id="run-1",
        ),
    )

    orchestrator = AgentOrchestrator(
        run,
        reality=reality,
    )

    return orchestrator, reality


def test_orchestrator_records_start_event() -> None:
    orchestrator, reality = build_orchestrator_with_reality()

    state = orchestrator.start()

    assert state == AgentState.PLANNING
    assert len(reality.events) == 1

    event = reality.events[0]
    assert event.event_type == EventType.STATE_CHANGED
    assert event.actor == RealitySource.ORCHESTRATOR
    assert event.phase == "planning"
    assert event.state_after == AgentState.PLANNING.value


def test_orchestrator_records_execution_transition() -> None:
    orchestrator, reality = build_orchestrator_with_reality()

    orchestrator.start()
    orchestrator.begin_execution()

    assert len(reality.events) == 2
    assert reality.events[0].state_after == AgentState.PLANNING.value
    assert reality.events[1].state_before == AgentState.PLANNING.value
    assert reality.events[1].state_after == AgentState.EXECUTING.value
    assert reality.events[1].phase == "execution"


def test_orchestrator_can_run_without_reality() -> None:
    run = AgentRun(
        task_id="task-1",
        state=AgentState.IDLE,
    )

    orchestrator = AgentOrchestrator(run)

    assert orchestrator.start() == AgentState.PLANNING
    assert orchestrator.reality is None


def test_orchestrator_can_attach_reality_later() -> None:
    orchestrator, reality = build_orchestrator_with_reality()

    assert orchestrator.reality is reality

    second_reality = AgentReality(
        identity=reality.identity,
        task=reality.task,
        run=reality.run,
    )

    orchestrator.attach_reality(second_reality)

    assert orchestrator.reality is second_reality
