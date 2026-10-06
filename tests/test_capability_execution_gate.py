from __future__ import annotations

import pytest

from forgeai.ai.agent_state import AgentRun, AgentState
from forgeai.ai.agent_orchestrator import AgentOrchestrator
from forgeai.core.capability_execution_gate import (
    CapabilityExecutionGate,
    CapabilityGateDecision,
)
from forgeai.core.capability_registry import (
    CapabilityRegistry,
    PluginFactRequirement,
    PluginManifest,
)
from forgeai.core.completion_gate import CompletionEvidenceCategory, CompletionEvidenceMode
from forgeai.core.fact_evidence_provider import (
    FactObservation,
    FactRegistry,
    FactService,
    FactSourceType,
    FactStatus,
    FunctionFactProvider,
)
from forgeai.core.plugin_manager import (
    CapabilityExecutionContext,
    PluginManager,
)
from forgeai.core.verification_framework import (
    FunctionVerificationProvider,
    VerificationCheck,
    VerificationProfile,
    VerificationRegistry,
    VerificationResult,
    VerificationStatus,
)


def _verification_provider(context, check):
    return VerificationResult(
        check_id=check.check_id,
        provider_id="verify",
        category=CompletionEvidenceCategory.TECHNICAL,
        status=VerificationStatus.PASS,
        summary="ok",
        source="verify",
        mode=CompletionEvidenceMode.FACT,
    )


def _manager(*, observed=True, with_executor=True, with_profile=True):
    facts = FactRegistry()
    facts.register_provider(
        FunctionFactProvider(
            provider_id="probe",
            source_type=FactSourceType.SCRIPT,
            fact_keys=("tool.available",),
            callback=lambda context, query: FactObservation(
                status=FactStatus.OBSERVED,
                value=observed,
                summary="Tool geprüft",
                source_detail="probe",
            ),
        )
    )
    verification = VerificationRegistry()
    if with_profile:
        verification.register_provider(
            FunctionVerificationProvider(
                provider_id="verify",
                category=CompletionEvidenceCategory.TECHNICAL,
                callback=_verification_provider,
                mode=CompletionEvidenceMode.FACT,
            )
        )
        verification.register_profile(
            VerificationProfile(
                profile_id="tool-profile",
                checks=(
                    VerificationCheck(
                        check_id="tool-check",
                        provider_id="verify",
                        category=CompletionEvidenceCategory.TECHNICAL,
                    ),
                ),
            )
        )
    manager = PluginManager(
        CapabilityRegistry(),
        fact_service=FactService(facts),
        verification_registry=verification,
    )
    executor = (lambda context, step: f"ran:{step.plugin_id}") if with_executor else None
    manager.register_plugin(
        PluginManifest(
            plugin_id="tool",
            name="Tool",
            version="1",
            capabilities=("tool.use",),
            task_hints=("tool",),
            fact_requirements=(
                PluginFactRequirement(
                    fact_key="tool.available",
                    provider_id="probe",
                    expected_value=True,
                ),
            ),
            verification_profiles=("tool-profile",),
        ),
        executor=executor,
    )
    manager.set_autonomous("tool", True)
    return manager


def _context():
    return CapabilityExecutionContext(task_id="task-1", execution_round=1)


def test_empty_plugin_plan_does_not_gate_core_execution():
    manager = _manager()
    plan = manager.build_execution_plan("unrelated core file change")
    result = CapabilityExecutionGate(manager).evaluate(plan, _context())

    assert result.decision == CapabilityGateDecision.NOT_REQUIRED
    assert result.ready is True
    assert result.reason_codes == ("no_plugin_execution_steps",)


def test_gate_proves_runtime_and_verification_requirements():
    manager = _manager()
    plan = manager.build_execution_plan("tool benutzen")
    result = manager.preflight_execution(plan, _context())

    assert result.decision == CapabilityGateDecision.READY
    assert result.ready is True
    assert result.verification_profiles == ("tool-profile",)
    assert len(result.fact_records) == 1
    assert result.fact_records[0].status == FactStatus.OBSERVED
    assert result.checks[0].fact_ids == (result.fact_records[0].fact_id,)


def test_gate_rechecks_authorization_after_planning():
    manager = _manager()
    plan = manager.build_execution_plan("tool benutzen")
    manager.set_autonomous("tool", False)

    result = manager.preflight_execution(plan, _context())

    assert result.decision == CapabilityGateDecision.BLOCKED
    assert "tool:authorization:manual_only" in result.reason_codes


def test_gate_blocks_runtime_fact_mismatch_before_executor_runs():
    manager = _manager(observed=False)
    plan = manager.build_execution_plan("tool benutzen")

    result = manager.preflight_execution(plan, _context())
    assert result.decision == CapabilityGateDecision.BLOCKED
    assert "tool:fact_value_mismatch:tool.available" in result.reason_codes

    with pytest.raises(RuntimeError, match="Capability Execution Gate"):
        manager.execute_serial(plan, _context())


def test_gate_requires_executor_for_real_plugin_execution():
    manager = _manager(with_executor=False)
    plan = manager.build_execution_plan("tool benutzen")

    result = manager.preflight_execution(plan, _context())

    assert result.decision == CapabilityGateDecision.BLOCKED
    assert "tool:executor_missing" in result.reason_codes


def test_gate_requires_declared_verification_profile_to_exist():
    manager = _manager(with_profile=False)
    plan = manager.build_execution_plan("tool benutzen")

    result = manager.preflight_execution(plan, _context())

    assert result.decision == CapabilityGateDecision.BLOCKED
    assert "tool:verification_profile_missing:tool-profile" in result.reason_codes


def test_orchestrator_records_gate_facts_and_verification_requirements():
    manager = _manager()
    plan = manager.build_execution_plan("tool benutzen")
    run = AgentRun(task_id="task-1", state=AgentState.EXECUTING, execution_round=1)
    run.record_capability_plan(plan)
    orchestrator = AgentOrchestrator(run)

    result = orchestrator.preflight_capability_execution(manager, plan)

    assert result.ready is True
    assert len(run.fact_history) == 1
    assert run.required_verification_profiles[0].profile_id == "tool-profile"
    assert run.metadata["capability_execution_gate"]["decision"] == "ready"


def test_orchestrator_executes_explicit_capability_plan_through_gate():
    manager = _manager()
    plan = manager.build_execution_plan("tool benutzen")
    run = AgentRun(task_id="task-1", state=AgentState.EXECUTING, execution_round=1)
    run.record_capability_plan(plan)
    orchestrator = AgentOrchestrator(run)

    results = orchestrator.execute_capability_plan(manager, plan)

    assert results == ("ran:tool",)
    assert run.metadata["capability_execution_history"][-1]["plugins"] == ("tool",)


def test_orchestrator_does_not_execute_when_gate_blocks():
    manager = _manager(observed=False)
    plan = manager.build_execution_plan("tool benutzen")
    run = AgentRun(task_id="task-1", state=AgentState.EXECUTING, execution_round=1)
    run.record_capability_plan(plan)
    orchestrator = AgentOrchestrator(run)

    with pytest.raises(RuntimeError, match="Capability Execution Gate"):
        orchestrator.execute_capability_plan(manager, plan)

    assert run.metadata["capability_execution_gate"]["decision"] == "blocked"
