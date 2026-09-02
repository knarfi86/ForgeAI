from __future__ import annotations

import pytest

from forgeai.ai.agent_contracts import AgentTask
from forgeai.ai.agent_planner import AgentPlanner


class FakeRouter:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[tuple[str, str]] = []

    def generate(self, role: str, prompt: str) -> str:
        self.calls.append((role, prompt))
        return self.response


class FakeExternalPlanner:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[tuple[AgentTask, str]] = []

    def plan(self, task: AgentTask, project_context: str) -> str:
        self.calls.append((task, project_context))
        return self.response


def valid_response() -> str:
    return (
        '{"summary":"Plan erstellen",'
        '"proposed_changes":[{"action":"replace",'
        '"path":"example.py",'
        '"description":"Code anpassen"}],'
        '"rationale":"Notwendige Änderung"}'
    )


def make_task() -> AgentTask:
    return AgentTask(
        task_id="task-1",
        user_request="Passe example.py an.",
    )


def test_planner_creates_agent_plan() -> None:
    router = FakeRouter(valid_response())
    planner = AgentPlanner(router)

    result = planner.plan(
        make_task(),
        "PROJECT CONTEXT",
    )

    assert result.summary == "Plan erstellen"
    assert len(result.proposed_changes) == 1
    assert result.proposed_changes[0]["path"] == "example.py"
    assert result.rationale == "Notwendige Änderung"


def test_planner_uses_planner_model_role() -> None:
    router = FakeRouter(valid_response())
    planner = AgentPlanner(router)

    planner.plan(make_task(), "PROJECT")

    assert len(router.calls) == 1
    role, prompt = router.calls[0]

    assert role == "planner"
    assert "Passe example.py an." in prompt
    assert "PROJECT" in prompt


def test_planner_includes_revision_context_in_prompt() -> None:
    router = FakeRouter(valid_response())
    planner = AgentPlanner(router)

    revision_context = [
        {
            "review_round": 1,
            "decision": "revise",
            "findings": ["Die Änderung berücksichtigt Fehlerbehandlung nicht."],
            "required_changes": ["Fehlerbehandlung ergänzen."],
        }
    ]

    planner.plan(
        make_task(),
        "PROJECT",
        revision_context=revision_context,
    )

    assert len(router.calls) == 1
    prompt = router.calls[0][1]

    assert "REVISION_CONTEXT:" in prompt
    assert "Fehlerbehandlung ergänzen." in prompt
    assert "Die Änderung berücksichtigt Fehlerbehandlung nicht." in prompt


def test_external_planner_is_optional() -> None:
    router = FakeRouter(valid_response())
    planner = AgentPlanner(router)

    result = planner.plan(make_task())

    assert result.summary == "Plan erstellen"


def test_external_planner_input_is_forwarded() -> None:
    router = FakeRouter(valid_response())
    external = FakeExternalPlanner("EXTERNER PLAN")

    planner = AgentPlanner(
        router,
        external_planner=external,
    )

    task = make_task()
    planner.plan(task, "PROJECT")

    assert external.calls == [(task, "PROJECT")]
    assert "EXTERNAL_PLANNER_INPUT:" in router.calls[0][1]
    assert "EXTERNER PLAN" in router.calls[0][1]


def test_external_planner_does_not_replace_local_plan() -> None:
    router = FakeRouter(valid_response())
    external = FakeExternalPlanner(
        '{"summary":"Externer Plan"}'
    )

    planner = AgentPlanner(
        router,
        external_planner=external,
    )

    result = planner.plan(make_task())

    assert result.summary == "Plan erstellen"


def test_invalid_json_is_rejected() -> None:
    router = FakeRouter("kein json")
    planner = AgentPlanner(router)

    with pytest.raises(ValueError, match="gültiges JSON"):
        planner.plan(make_task())


def test_empty_response_is_rejected() -> None:
    router = FakeRouter("")
    planner = AgentPlanner(router)

    with pytest.raises(ValueError, match="keine gültige Antwort"):
        planner.plan(make_task())


def test_non_object_json_is_rejected() -> None:
    router = FakeRouter("[]")
    planner = AgentPlanner(router)

    with pytest.raises(ValueError, match="JSON-Objekt"):
        planner.plan(make_task())


def test_missing_summary_is_rejected() -> None:
    router = FakeRouter(
        '{"proposed_changes":[],"rationale":"x"}'
    )
    planner = AgentPlanner(router)

    with pytest.raises(ValueError, match="summary"):
        planner.plan(make_task())


def test_invalid_change_is_rejected() -> None:
    router = FakeRouter(
        '{"summary":"Plan","proposed_changes":[{"path":"x.py"}]}'
    )
    planner = AgentPlanner(router)

    with pytest.raises(ValueError, match="action"):
        planner.plan(make_task())


def test_invalid_change_list_is_rejected() -> None:
    router = FakeRouter(
        '{"summary":"Plan","proposed_changes":"invalid"}'
    )
    planner = AgentPlanner(router)

    with pytest.raises(ValueError, match="Liste"):
        planner.plan(make_task())


def test_planner_never_writes_files(tmp_path) -> None:
    router = FakeRouter(valid_response())
    planner = AgentPlanner(router)

    planner.plan(make_task(), str(tmp_path))

    assert list(tmp_path.iterdir()) == []

