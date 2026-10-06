from __future__ import annotations

from forgeai.core.capability_registry import (
    CapabilityRegistry,
    PluginFactRequirement,
    PluginManifest,
    ResourceRequirements,
)
from forgeai.core.fact_evidence_provider import (
    FactObservation,
    FactRegistry,
    FactService,
    FactSourceType,
    FactStatus,
    FunctionFactProvider,
)
from forgeai.core.plugin_manager import (
    CapabilityAuthorization,
    CapabilityExecutionContext,
    PluginManager,
)


def _manager() -> PluginManager:
    return PluginManager(CapabilityRegistry())


def test_registered_plugin_is_enabled_but_manual_until_user_allows_autonomy():
    manager = _manager()
    manager.register_plugin(
        PluginManifest(
            plugin_id="python",
            name="Python",
            version="1",
            capabilities=("code.python",),
            task_hints=("python",),
        )
    )

    selection = manager.select_for_request("python ändern")
    assert selection[0].authorization == CapabilityAuthorization.MANUAL_ONLY

    manager.set_autonomous("python", True)
    selection = manager.select_for_request("python ändern")
    assert selection[0].authorization == CapabilityAuthorization.ALLOWED


def test_disabled_plugin_is_never_auto_selected_into_steps():
    manager = _manager()
    manager.register_plugin(
        PluginManifest(
            plugin_id="video",
            name="Video",
            version="1",
            capabilities=("video.generate",),
            task_hints=("video",),
        )
    )
    manager.set_autonomous("video", True)
    manager.set_enabled("video", False)

    plan = manager.build_execution_plan("video erstellen")
    assert plan.steps == ()
    assert plan.blocked[0].authorization == CapabilityAuthorization.DISABLED


def test_project_override_can_allow_autonomy_without_changing_global_default(tmp_path):
    manager = _manager()
    manager.register_plugin(
        PluginManifest(
            plugin_id="gamedev",
            name="GameDev",
            version="1",
            capabilities=("game.dev",),
            task_hints=("spiel",),
        )
    )
    manager.set_autonomous("gamedev", False)
    manager.set_project_autonomous("gamedev", tmp_path, True)

    project_plan = manager.build_execution_plan("spiel bauen", project_path=tmp_path)
    global_plan = manager.build_execution_plan("spiel bauen")

    assert [step.plugin_id for step in project_plan.steps] == ["gamedev"]
    assert global_plan.steps == ()


def test_dependency_order_is_stable_and_serial():
    manager = _manager()
    trace: list[str] = []

    manager.register_plugin(
        PluginManifest(
            plugin_id="base",
            name="Base",
            version="1",
            capabilities=("base.use",),
        ),
        executor=lambda context, step: trace.append(step.plugin_id),
    )
    manager.register_plugin(
        PluginManifest(
            plugin_id="higher",
            name="Higher",
            version="1",
            capabilities=("higher.use",),
            dependencies=("base",),
            task_hints=("job",),
        ),
        executor=lambda context, step: trace.append(step.plugin_id),
    )
    manager.set_autonomous("base", True)
    manager.set_autonomous("higher", True)

    plan = manager.build_execution_plan("job")
    assert plan.execution_mode == "serial"
    assert [step.plugin_id for step in plan.steps] == ["base", "higher"]

    manager.execute_serial(
        plan,
        CapabilityExecutionContext(task_id="t", execution_round=1),
    )
    assert trace == ["base", "higher"]


def test_fact_requirements_are_checked_through_fact_service():
    facts = FactRegistry()
    facts.register_provider(
        FunctionFactProvider(
            provider_id="python-probe",
            source_type=FactSourceType.SCRIPT,
            fact_keys=("tool.python.available",),
            callback=lambda context, query: FactObservation(
                status=FactStatus.OBSERVED,
                value=True,
                summary="Python gefunden",
                source_detail="python --version",
            ),
        )
    )
    manager = PluginManager(CapabilityRegistry(), fact_service=FactService(facts))
    manager.register_plugin(
        PluginManifest(
            plugin_id="python",
            name="Python",
            version="1",
            capabilities=("code.python",),
            task_hints=("python",),
            fact_requirements=(
                PluginFactRequirement(
                    fact_key="tool.python.available",
                    provider_id="python-probe",
                    expected_value=True,
                ),
            ),
        )
    )
    manager.set_autonomous("python", True)
    plan = manager.build_execution_plan("python")

    availability = manager.validate_plan(
        plan,
        CapabilityExecutionContext(task_id="t", execution_round=2),
    )

    assert availability[0].available is True
    assert len(availability[0].fact_ids) == 1


def test_fact_value_mismatch_blocks_execution():
    facts = FactRegistry()
    facts.register_provider(
        FunctionFactProvider(
            provider_id="gpu-probe",
            source_type=FactSourceType.SCRIPT,
            fact_keys=("gpu.available",),
            callback=lambda context, query: FactObservation(
                status=FactStatus.OBSERVED,
                value=False,
                summary="Keine GPU",
                source_detail="probe",
            ),
        )
    )
    manager = PluginManager(CapabilityRegistry(), fact_service=FactService(facts))
    manager.register_plugin(
        PluginManifest(
            plugin_id="image",
            name="Image",
            version="1",
            capabilities=("image.generate",),
            task_hints=("bild",),
            fact_requirements=(
                PluginFactRequirement(
                    fact_key="gpu.available",
                    provider_id="gpu-probe",
                    expected_value=True,
                ),
            ),
            resources=ResourceRequirements(gpu_required=True, min_vram_mb=4096),
        ),
        executor=lambda context, step: "should-not-run",
    )
    manager.set_autonomous("image", True)
    plan = manager.build_execution_plan("bild")

    availability = manager.validate_plan(
        plan,
        CapabilityExecutionContext(task_id="t", execution_round=1),
    )
    assert availability[0].available is False
    assert "fact_value_mismatch:gpu.available" in availability[0].reason_codes


def test_preferences_roundtrip_and_model_roles_are_declarative_only(tmp_path):
    manager = _manager()
    manager.register_plugin(
        PluginManifest(
            plugin_id="coder",
            name="Coder",
            version="1",
            capabilities=("code.generate",),
            task_hints=("code",),
            model_roles=("coding", "reasoning"),
            verification_profiles=("code.default",),
        )
    )
    manager.set_autonomous("coder", True)
    manager.set_project_autonomous("coder", tmp_path, False)
    saved = manager.export_preferences()

    restored = _manager()
    restored.register_plugin(manager.registry.get("coder"))
    restored.import_preferences(saved)

    assert restored.preferences("coder").autonomous is True
    assert restored.preferences("coder").autonomous_for(tmp_path) is False
    plan = restored.build_execution_plan("code")
    assert restored.model_roles_for(plan) == ("coding", "reasoning")
    assert restored.verification_profiles_for(plan) == ("code.default",)


def test_capability_plan_is_persistable_in_agent_run_and_reality():
    from forgeai.ai.agent_contracts import AgentTask
    from forgeai.ai.agent_state import AgentRun
    from forgeai.core.agent_reality import AgentReality

    manager = _manager()
    manager.register_plugin(
        PluginManifest(
            plugin_id="python",
            name="Python",
            version="1",
            capabilities=("code.python",),
            task_hints=("python",),
        )
    )
    manager.set_autonomous("python", True)
    plan = manager.build_execution_plan("python")

    run = AgentRun(task_id="task-1")
    run.record_capability_plan(plan)
    task = AgentTask(task_id="task-1", user_request="python")
    reality = AgentReality.from_task_and_run(
        task=task,
        run=run,
        agent_id="a",
        provider="ollama",
        model="m",
        role="orchestrator",
        run_id="r",
    )

    assert run.capability_plans[-1].steps[0].plugin_id == "python"
    assert reality.run.capability_plans[-1]["execution_mode"] == "serial"


def test_blocked_dependency_blocks_dependent_plugin():
    manager = _manager()
    manager.register_plugin(
        PluginManifest(
            plugin_id="base",
            name="Base",
            version="1",
            capabilities=("base.use",),
        )
    )
    manager.register_plugin(
        PluginManifest(
            plugin_id="higher",
            name="Higher",
            version="1",
            capabilities=("higher.use",),
            dependencies=("base",),
            task_hints=("job",),
        )
    )
    manager.set_autonomous("higher", True)
    manager.set_autonomous("base", False)

    plan = manager.build_execution_plan("job")

    assert plan.steps == ()
    blocked = {item.plugin_id: item for item in plan.blocked}
    assert blocked["base"].authorization == CapabilityAuthorization.MANUAL_ONLY
    assert blocked["higher"].authorization == CapabilityAuthorization.UNAVAILABLE
    assert "dependency_blocked:base" in blocked["higher"].reasons
