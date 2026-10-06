from __future__ import annotations

from forgeai.ai.agent_contracts import AgentPlan, AgentTask, ReviewDecision, ReviewResult
from forgeai.ai.agent_orchestrator import AgentOrchestrator
from forgeai.ai.agent_planner import AgentPlanner
from forgeai.ai.agent_reviewer import AgentReviewer
from forgeai.ai.agent_state import AgentRun
from forgeai.core.capability_registry import (
    CapabilityRegistry,
    CapabilityStatus,
    PluginManifest,
)
from forgeai.core.plugin_manager import CapabilityAuthorization, PluginManager


class FakeRouter:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[tuple[str, str]] = []

    def generate(self, role: str, prompt: str, **kwargs) -> str:
        self.calls.append((role, prompt))
        return self.response


def test_capability_status_defaults_available_and_normalizes_strings():
    available = PluginManifest(plugin_id="a", name="A", version="1")
    experimental = PluginManifest(
        plugin_id="b",
        name="B",
        version="1",
        status="experimental",
    )

    assert available.status == CapabilityStatus.AVAILABLE
    assert experimental.status == CapabilityStatus.EXPERIMENTAL


def test_manifest_snapshot_exposes_lifecycle_status():
    registry = CapabilityRegistry()
    registry.register(
        PluginManifest(
            plugin_id="future",
            name="Future",
            version="1",
            status=CapabilityStatus.PLANNED,
            capabilities=("future.use",),
        )
    )

    assert registry.manifest_snapshot()[0]["status"] == "planned"


def test_planned_plugin_is_never_selected_for_autonomous_execution():
    manager = PluginManager(CapabilityRegistry())
    manager.register_plugin(
        PluginManifest(
            plugin_id="future",
            name="Future",
            version="1",
            status=CapabilityStatus.PLANNED,
            capabilities=("future.use",),
            task_hints=("future",),
        )
    )
    manager.set_autonomous("future", True)

    plan = manager.build_execution_plan("future benutzen")

    assert plan.steps == ()
    assert plan.blocked[0].authorization == CapabilityAuthorization.UNAVAILABLE


def test_experimental_plugin_can_be_selected_when_authorized():
    manager = PluginManager(CapabilityRegistry())
    manager.register_plugin(
        PluginManifest(
            plugin_id="lab",
            name="Lab",
            version="1",
            status=CapabilityStatus.EXPERIMENTAL,
            capabilities=("lab.use",),
            task_hints=("labor",),
        )
    )
    manager.set_autonomous("lab", True)

    plan = manager.build_execution_plan("labor benutzen")

    assert [step.plugin_id for step in plan.steps] == ["lab"]


def test_planning_snapshot_exposes_all_plugins_and_keeps_core_boundary():
    manager = PluginManager(CapabilityRegistry())
    manager.register_plugin(
        PluginManifest(
            plugin_id="python",
            name="Python",
            version="1",
            capabilities=("code.python.modify",),
            task_hints=("python",),
        )
    )
    manager.register_plugin(
        PluginManifest(
            plugin_id="future",
            name="Future",
            version="1",
            status=CapabilityStatus.PLANNED,
            capabilities=("future.use",),
        )
    )

    plan = manager.build_execution_plan("python ändern")
    snapshot = manager.planning_snapshot(plan)
    plugins = {item["plugin_id"]: item for item in snapshot["plugins"]}

    assert snapshot["scope"] == "optional_plugin_capabilities"
    assert snapshot["core_file_planning_unaffected"] is True
    assert plugins["python"]["authorization"] == "manual_only"
    assert plugins["python"]["matched"] is True
    assert plugins["python"]["selected_for_execution"] is False
    assert plugins["python"]["runtime_availability"] == "not_checked"
    assert plugins["future"]["status"] == "planned"
    assert plugins["future"]["authorization"] == "unavailable"


def test_planner_receives_capability_context_without_treating_it_as_core_restriction():
    router = FakeRouter(
        '{"summary":"Plan","proposed_changes":[],"rationale":"OK"}'
    )
    planner = AgentPlanner(router)
    task = AgentTask(task_id="task-plan", user_request="Python ändern")
    context = {
        "core_file_planning_unaffected": True,
        "plugins": [
            {
                "plugin_id": "python",
                "status": "available",
                "authorization": "manual_only",
                "runtime_availability": "not_checked",
            }
        ],
    }

    planner.plan(task, "PROJECT", capability_context=context)
    prompt = router.calls[0][1]

    assert "CAPABILITY_CONTEXT:" in prompt
    assert '"authorization": "manual_only"' in prompt
    assert "schränkt normale Core-Dateiplanung nicht ein" in prompt
    assert "runtime_availability=not_checked" in prompt


def test_reviewer_receives_capability_context_and_preserves_core_boundary():
    router = FakeRouter(
        '{"decision":"approve","findings":[],"required_changes":[],"rationale":"OK"}'
    )
    reviewer = AgentReviewer(router)
    plan = AgentPlan(summary="Plan")
    context = {
        "core_file_planning_unaffected": True,
        "plugins": [
            {
                "plugin_id": "future",
                "status": "planned",
                "authorization": "unavailable",
            }
        ],
    }

    reviewer.review(plan, "PROJECT", capability_context=context)
    prompt = router.calls[0][1]

    assert "CAPABILITY_CONTEXT:" in prompt
    assert '"status": "planned"' in prompt
    assert "schränkt normale Core-Dateiplanung nicht ein" in prompt
    assert "nicht autonom nutzbaren Plugin" in prompt


def test_orchestrator_forwards_run_capability_context_to_planner_and_reviewer():
    seen: dict[str, object] = {}

    class CapabilityPlanner:
        def plan(
            self,
            task,
            project_context="",
            revision_context=None,
            capability_context=None,
        ):
            seen["planner"] = capability_context
            return AgentPlan(summary="Testplan")

    class CapabilityReviewer:
        def review(self, plan, project_context="", capability_context=None):
            seen["reviewer"] = capability_context
            return ReviewResult(
                decision=ReviewDecision.APPROVE,
                rationale="OK",
            )

    context = {
        "scope": "optional_plugin_capabilities",
        "core_file_planning_unaffected": True,
    }
    run = AgentRun(task_id="task-cap")
    run.metadata["capability_context"] = context
    orchestrator = AgentOrchestrator(
        run,
        planner=CapabilityPlanner(),
        reviewer=CapabilityReviewer(),
    )
    orchestrator.start()
    task = AgentTask(task_id="task-cap", user_request="test")

    orchestrator.plan(task, "PROJECT")
    orchestrator.begin_review()
    orchestrator.review("PROJECT")

    assert seen["planner"] == context
    assert seen["reviewer"] == context
