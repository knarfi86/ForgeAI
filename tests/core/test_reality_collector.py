from forgeai.core.agent_reality import (
    AgentEvent,
    AgentReality,
    AgentRun,
    AgentTask,
    EventType,
    RealitySource,
)
from forgeai.core.project_evidence import ProjectEvidence
from forgeai.core.reality_collector import RealityCollector


class FakeAnalyzer:
    def analyze(self, project_path):
        return {
            "project_path": str(project_path),
            "files": ["main.py"],
            "classes": {},
            "imports": {"main.py": ["pygame"]},
            "modules": ["main"],
            "dependency_graph": {"main": []},
        }

    def evidence_summary(self, project_path):
        return {
            "functions": {"main.py": ["main"]},
            "package_dependencies": ["pygame-ce"],
            "event_handlers": {},
            "syntax_errors": {},
            "event_retrievals": {},
        }


def make_reality():
    task = AgentTask(
        task_id="task-1",
        user_request="Test task",
    )
    run = AgentRun(task_id="task-1")

    return AgentReality.from_task_and_run(
        task=task,
        run=run,
        agent_id="test-agent",
        provider="test-provider",
        model="test-model",
        role="test",
        run_id="run-1",
    )


def test_collect_project_returns_project_evidence(tmp_path):
    reality = make_reality()
    collector = RealityCollector(FakeAnalyzer())

    result = collector.collect_project(reality, tmp_path)

    assert isinstance(result, ProjectEvidence)
    assert result.project_path == str(tmp_path)
    assert result.observations
    assert result.evidence


def test_collect_project_attaches_project_evidence_to_reality(tmp_path):
    reality = make_reality()
    collector = RealityCollector(FakeAnalyzer())

    collector.collect_project(reality, tmp_path)

    assert reality.observations
    assert reality.evidence

    assert all(
        observation.observation_id.startswith("project:")
        for observation in reality.observations
    )

    assert all(
        evidence.evidence_id.startswith("project:")
        for evidence in reality.evidence
    )


def test_collect_project_refreshes_without_duplicates(tmp_path):
    reality = make_reality()
    collector = RealityCollector(FakeAnalyzer())

    first = collector.collect_project(reality, tmp_path)
    first_observation_count = len(first.observations)
    first_evidence_count = len(first.evidence)

    collector.collect_project(reality, tmp_path)

    assert len(reality.observations) == first_observation_count
    assert len(reality.evidence) == first_evidence_count


def test_collect_project_preserves_runtime_events(tmp_path):
    reality = make_reality()

    event = AgentEvent(
        event_id="runtime-event-1",
        event_type=EventType.TASK_CREATED,
        task_id="task-1",
        run_id="run-1",
        actor=RealitySource.SYSTEM,
        phase="test",
    )
    reality.events.append(event)

    collector = RealityCollector(FakeAnalyzer())
    collector.collect_project(reality, tmp_path)

    assert reality.events == [event]
