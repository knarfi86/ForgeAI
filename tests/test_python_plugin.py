from __future__ import annotations

from pathlib import Path

from forgeai.core.capability_registry import CapabilityRegistry
from forgeai.core.completion_gate import CompletionEvidenceCategory
from forgeai.core.fact_evidence_provider import FactContext, FactQuery, FactRegistry, FactService, FactStatus
from forgeai.core.plugin_manager import CapabilityExecutionContext, PluginManager
from forgeai.core.verification_framework import VerificationContext, VerificationRegistry, VerificationStatus
from forgeai.plugins.python_plugin import (
    FACT_PROVIDER_ID,
    PLUGIN_ID,
    VERIFICATION_PROFILE_ID,
    PythonPlugin,
    register_python_plugin,
)


def _manager() -> PluginManager:
    return PluginManager(
        CapabilityRegistry(),
        fact_service=FactService(FactRegistry()),
        verification_registry=VerificationRegistry(),
    )


def test_python_plugin_registers_manifest_fact_provider_profile_and_executor():
    manager = _manager()
    register_python_plugin(manager)

    manifest = manager.registry.get(PLUGIN_ID)
    assert manifest.name == "Python Development"
    assert "code.python.modify" in manifest.capabilities
    assert manifest.verification_profiles == (VERIFICATION_PROFILE_ID,)
    assert manager.fact_service is not None
    assert FACT_PROVIDER_ID in manager.fact_service.registry.list_provider_ids()
    assert manager.verification_registry is not None
    assert VERIFICATION_PROFILE_ID in manager.verification_registry.list_profile_ids()


def test_python_facts_are_observed_from_real_interpreter(tmp_path):
    manager = _manager()
    plugin = register_python_plugin(manager)
    context = FactContext(task_id="t", execution_round=1, project_path=str(tmp_path))

    available = plugin.observe_fact(context, FactQuery("python.available"))
    version = plugin.observe_fact(context, FactQuery("python.version"))
    pytest_available = plugin.observe_fact(context, FactQuery("python.pytest.available"))

    assert available.status == FactStatus.OBSERVED
    assert available.value is True
    assert version.status == FactStatus.OBSERVED
    assert isinstance(version.value, str) and version.value
    assert pytest_available.status == FactStatus.OBSERVED
    assert isinstance(pytest_available.value, bool)


def test_python_availability_flows_through_central_fact_service(tmp_path):
    manager = _manager()
    register_python_plugin(manager)

    availability = manager.evaluate_availability(
        PLUGIN_ID,
        CapabilityExecutionContext(
            task_id="t",
            execution_round=2,
            project_path=str(tmp_path),
        ),
    )

    assert availability.available is True
    assert availability.fact_ids
    assert any(detail.startswith("Python ") for detail in availability.details)


def test_python_project_markers_are_filesystem_observations(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("pytest\n", encoding="utf-8")
    plugin = PythonPlugin()

    observation = plugin.observe_fact(
        FactContext(task_id="t", execution_round=1, project_path=str(tmp_path)),
        FactQuery("python.project.markers"),
    )

    assert observation.status == FactStatus.OBSERVED
    assert observation.value == ("pyproject.toml", "requirements.txt")


def test_python_verification_profile_compiles_good_project_and_rejects_bad_source(tmp_path):
    manager = _manager()
    register_python_plugin(manager)
    registry = manager.verification_registry
    assert registry is not None
    profile = registry.get_profile(VERIFICATION_PROFILE_ID)
    provider = registry.get_provider("python.verifier")
    compile_check = next(check for check in profile.checks if check.check_id == "python-compile")

    good = tmp_path / "good.py"
    good.write_text("value = 42\n", encoding="utf-8")
    context = VerificationContext(task_id="t", execution_round=1, project_path=str(tmp_path))
    good_result = provider.verify(context, compile_check)
    assert good_result.status == VerificationStatus.PASS
    assert good_result.category == CompletionEvidenceCategory.TECHNICAL

    bad = tmp_path / "bad.py"
    bad.write_text("def broken(:\n    pass\n", encoding="utf-8")
    bad_result = provider.verify(context, compile_check)
    assert bad_result.status == VerificationStatus.FAIL
    assert "Syntaxprüfung" in bad_result.summary


def test_python_executor_is_serially_usable_and_defaults_to_safe_inspect(tmp_path):
    manager = _manager()
    register_python_plugin(manager)
    manager.set_autonomous(PLUGIN_ID, True)

    plan = manager.build_execution_plan("Bitte Python Code prüfen", project_path=tmp_path)
    assert [step.plugin_id for step in plan.steps] == [PLUGIN_ID]

    results = manager.execute_serial(
        plan,
        CapabilityExecutionContext(
            task_id="t",
            execution_round=1,
            project_path=str(tmp_path),
        ),
    )
    result = results[0]
    assert result.action == "inspect"
    assert result.success is True
    assert "Python " in result.output


def test_python_executor_runs_compile_only_when_explicitly_requested(tmp_path):
    (tmp_path / "module.py").write_text("x = 1\n", encoding="utf-8")
    manager = _manager()
    register_python_plugin(manager)
    manager.set_autonomous(PLUGIN_ID, True)
    plan = manager.build_execution_plan("python", project_path=tmp_path)

    result = manager.execute_serial(
        plan,
        CapabilityExecutionContext(
            task_id="t",
            execution_round=1,
            project_path=str(tmp_path),
            metadata={"plugin_actions": {PLUGIN_ID: "compile"}},
        ),
    )[0]

    assert result.action == "compile"
    assert result.success is True
    assert "Python-Datei(en) geprüft" in result.output


def test_builtin_registration_includes_python_plugin():
    from forgeai.plugins import register_builtin_plugins

    manager = _manager()
    register_builtin_plugins(manager)

    assert manager.registry.get(PLUGIN_ID).name == "Python Development"
