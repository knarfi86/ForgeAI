from __future__ import annotations

import pytest

from forgeai.ai.agent_contracts import AgentPlan
from forgeai.ai.agent_orchestrator import AgentOrchestrator
from forgeai.ai.agent_state import AgentRun, AgentState
from forgeai.core.capability_execution_gate import CapabilityGateDecision
from forgeai.core.capability_registry import (
    CapabilityRegistry,
    CapabilityStatus,
    PluginActionSpec,
    PluginManifest,
)
from forgeai.core.plugin_manager import CapabilityExecutionContext, PluginManager


def _manager(*, status=CapabilityStatus.AVAILABLE, enabled=True, autonomous=False):
    manager = PluginManager(CapabilityRegistry())
    manager.register_plugin(
        PluginManifest(
            plugin_id="tool",
            name="Tool",
            version="1",
            status=status,
            capabilities=("tool.use",),
            actions=(
                PluginActionSpec(
                    action_id="run",
                    capability_ids=("tool.use",),
                    parameter_keys=("target",),
                    description="Run tool",
                ),
            ),
        ),
        executor=lambda context, step: {
            "success": True,
            "action": step.action_id,
            "parameters": dict(step.parameters),
        },
    )
    manager.set_enabled("tool", enabled)
    manager.set_autonomous("tool", autonomous)
    return manager


def test_agent_plan_accepts_structured_plugin_action():
    plan = AgentPlan(
        summary="Tool ausführen",
        plugin_actions=[
            {"plugin_id": "tool", "action": "run", "parameters": {"target": "x"}}
        ],
    )

    assert plan.plugin_actions[0]["action"] == "run"


def test_agent_plan_rejects_duplicate_plugin_actions_in_v1():
    with pytest.raises(ValueError, match="nur eine Aktion"):
        AgentPlan(
            summary="Doppelt",
            plugin_actions=[
                {"plugin_id": "tool", "action": "run", "parameters": {}},
                {"plugin_id": "tool", "action": "run", "parameters": {}},
            ],
        )


def test_planning_snapshot_exposes_declared_action_contract():
    manager = _manager()
    request_plan = manager.build_execution_plan("unrelated")

    snapshot = manager.planning_snapshot(request_plan)
    plugin = snapshot["plugins"][0]

    assert plugin["actions"][0]["action_id"] == "run"
    assert plugin["actions"][0]["parameter_keys"] == ("target",)


def test_manual_only_action_plan_requires_one_shot_approval_at_gate():
    manager = _manager(autonomous=False)
    plan = manager.build_action_execution_plan(
        "tool ausführen",
        [{"plugin_id": "tool", "action": "run", "parameters": {"target": "x"}}],
    )

    assert [step.plugin_id for step in plan.steps] == ["tool"]

    blocked = manager.preflight_execution(
        plan,
        CapabilityExecutionContext(task_id="t", execution_round=1),
    )
    assert blocked.decision == CapabilityGateDecision.BLOCKED
    assert "tool:authorization:manual_only" in blocked.reason_codes

    ready = manager.preflight_execution(
        plan,
        CapabilityExecutionContext(
            task_id="t",
            execution_round=1,
            metadata={"approved_plugin_ids": ("tool",)},
        ),
    )
    assert ready.decision == CapabilityGateDecision.READY
    assert ready.checks[0].manual_approval_used is True


def test_disabled_or_planned_plugin_action_is_never_executable():
    disabled = _manager(enabled=False)
    disabled_plan = disabled.build_action_execution_plan(
        "tool",
        [{"plugin_id": "tool", "action": "run", "parameters": {}}],
    )
    assert disabled_plan.steps == ()
    assert disabled_plan.blocked[0].authorization.value == "disabled"

    planned = _manager(status=CapabilityStatus.PLANNED, autonomous=True)
    planned_plan = planned.build_action_execution_plan(
        "tool",
        [{"plugin_id": "tool", "action": "run", "parameters": {}}],
    )
    assert planned_plan.steps == ()
    assert planned_plan.blocked[0].authorization.value == "unavailable"


def test_action_plan_rejects_unknown_action_and_parameters():
    manager = _manager()

    with pytest.raises(KeyError, match="deklariert keine Aktion"):
        manager.build_action_execution_plan(
            "tool",
            [{"plugin_id": "tool", "action": "invented", "parameters": {}}],
        )

    with pytest.raises(ValueError, match="Unbekannte Parameter"):
        manager.build_action_execution_plan(
            "tool",
            [{"plugin_id": "tool", "action": "run", "parameters": {"fake": 1}}],
        )


def test_orchestrator_user_approval_unlocks_only_visible_plugin_action():
    manager = _manager(autonomous=False)
    plan = AgentPlan(
        summary="Tool ausführen",
        plugin_actions=[
            {"plugin_id": "tool", "action": "run", "parameters": {"target": "x"}}
        ],
    )
    run = AgentRun(task_id="t", state=AgentState.APPROVAL_REQUIRED)
    orchestrator = AgentOrchestrator(run)
    orchestrator.current_plan = plan

    state = orchestrator.approve()
    assert state == AgentState.EXECUTING
    assert run.metadata["approved_plugin_ids"] == ("tool",)

    results = orchestrator.execute_current_plugin_actions(manager)
    assert results[0]["action"] == "run"
    assert results[0]["parameters"] == {"target": "x"}
    assert run.metadata["capability_execution_history"][-1]["actions"][0]["action"] == "run"


def test_executor_failure_becomes_runtime_error():
    manager = PluginManager(CapabilityRegistry())
    manager.register_plugin(
        PluginManifest(
            plugin_id="bad",
            name="Bad",
            version="1",
            capabilities=("bad.use",),
            actions=(PluginActionSpec(action_id="run", capability_ids=("bad.use",)),),
        ),
        executor=lambda context, step: {"success": False, "output": "boom"},
    )
    manager.set_autonomous("bad", True)
    plan = manager.build_action_execution_plan(
        "bad",
        [{"plugin_id": "bad", "action": "run", "parameters": {}}],
    )

    with pytest.raises(RuntimeError, match="boom"):
        manager.execute_serial(
            plan,
            CapabilityExecutionContext(task_id="t", execution_round=1),
        )


def test_planner_parses_plugin_actions_into_agent_plan():
    from forgeai.ai.agent_contracts import AgentTask
    from forgeai.ai.agent_planner import AgentPlanner

    class Router:
        def generate(self, role, prompt, **kwargs):
            return (
                '{"summary":"Toolplan","proposed_changes":[],'
                '"plugin_actions":[{"plugin_id":"tool","action":"run",'
                '"parameters":{"target":"x"}}],"rationale":"Tool nötig"}'
            )

    plan = AgentPlanner(Router()).plan(
        AgentTask(task_id="t", user_request="Tool ausführen"),
        capability_context={"plugins": []},
    )

    assert plan.plugin_actions == [
        {"plugin_id": "tool", "action": "run", "parameters": {"target": "x"}}
    ]


def test_reviewer_prompt_contains_plugin_actions():
    from forgeai.ai.agent_reviewer import AgentReviewer

    class Router:
        def __init__(self):
            self.prompt = ""

        def generate(self, role, prompt, **kwargs):
            self.prompt = prompt
            return '{"decision":"approve","findings":[],"required_changes":[],"rationale":"OK"}'

    router = Router()
    reviewer = AgentReviewer(router)
    reviewer.review(
        AgentPlan(
            summary="Tool",
            plugin_actions=[
                {"plugin_id": "tool", "action": "run", "parameters": {}}
            ],
        ),
        capability_context={"plugins": []},
    )

    assert '"plugin_actions"' in router.prompt
    assert '"action": "run"' in router.prompt


def test_repairer_parses_plugin_actions():
    from forgeai.ai.agent_repairer import AgentRepairer

    plan = AgentRepairer._parse_response(
        '{"summary":"Repair","proposed_changes":[],'
        '"plugin_actions":[{"plugin_id":"tool","action":"run","parameters":{}}],'
        '"rationale":"prüfen"}'
    )

    assert plan.plugin_actions[0]["plugin_id"] == "tool"


def test_action_plan_never_hides_required_dependency_from_user():
    manager = PluginManager(CapabilityRegistry())
    manager.register_plugin(
        PluginManifest(
            plugin_id="base",
            name="Base",
            version="1",
            capabilities=("base.use",),
            actions=(PluginActionSpec(action_id="prepare", capability_ids=("base.use",)),),
        ),
        executor=lambda context, step: {"success": True},
    )
    manager.register_plugin(
        PluginManifest(
            plugin_id="higher",
            name="Higher",
            version="1",
            capabilities=("higher.use",),
            actions=(PluginActionSpec(action_id="run", capability_ids=("higher.use",)),),
            dependencies=("base",),
        ),
        executor=lambda context, step: {"success": True},
    )
    manager.set_autonomous("base", True)
    manager.set_autonomous("higher", True)

    plan = manager.build_action_execution_plan(
        "higher",
        [{"plugin_id": "higher", "action": "run", "parameters": {}}],
    )

    assert plan.steps == ()
    assert "dependency_action_required:base" in plan.blocked[0].reasons
