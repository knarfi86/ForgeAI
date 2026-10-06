import pytest

from forgeai.ai.agent_orchestrator import AgentOrchestrator
from forgeai.ai.agent_state import AgentRun, AgentState
from forgeai.core.completion_gate import (
    CompletionEvidenceCategory,
    CompletionEvidenceMode,
    CompletionOutcome,
)
from forgeai.core.verification_framework import (
    FunctionVerificationProvider,
    VerificationCheck,
    VerificationContext,
    VerificationEngine,
    VerificationProfile,
    VerificationRegistry,
    VerificationResult,
    VerificationStatus,
)


def provider_result(status=VerificationStatus.PASS, *, category=CompletionEvidenceCategory.RUNTIME):
    def callback(context, check):
        return VerificationResult(
            check_id=check.check_id,
            provider_id=check.provider_id,
            category=category,
            status=status,
            summary="observed",
            source=check.provider_id,
            mode=CompletionEvidenceMode.FACT,
            observed_value=f"round={context.execution_round}",
        )
    return callback


def test_registry_registers_provider_and_profile():
    registry = VerificationRegistry()
    registry.register_provider(FunctionVerificationProvider(
        provider_id="runtime.window",
        category=CompletionEvidenceCategory.RUNTIME,
        callback=provider_result(),
    ))
    registry.register_profile(VerificationProfile(
        profile_id="runtime-basic",
        checks=(VerificationCheck(
            check_id="window-visible",
            provider_id="runtime.window",
            category=CompletionEvidenceCategory.RUNTIME,
        ),),
    ))

    assert registry.list_provider_ids() == ("runtime.window",)
    assert registry.list_profile_ids() == ("runtime-basic",)


def test_objective_provider_cannot_register_as_inference():
    registry = VerificationRegistry()
    with pytest.raises(ValueError, match="FACT-Evidence"):
        registry.register_provider(FunctionVerificationProvider(
            provider_id="runtime.guess",
            category=CompletionEvidenceCategory.RUNTIME,
            callback=provider_result(),
            mode=CompletionEvidenceMode.INFERENCE,
        ))


def test_engine_executes_profile_and_creates_fresh_evidence():
    registry = VerificationRegistry()
    registry.register_provider(FunctionVerificationProvider(
        provider_id="runtime.window",
        category=CompletionEvidenceCategory.RUNTIME,
        callback=provider_result(),
    ))
    registry.register_profile(VerificationProfile(
        profile_id="runtime-basic",
        checks=(VerificationCheck(
            check_id="window-visible",
            provider_id="runtime.window",
            category=CompletionEvidenceCategory.RUNTIME,
        ),),
    ))

    report = VerificationEngine(registry).run(
        "runtime-basic",
        VerificationContext(task_id="task-1", execution_round=3, project_path="C:/project"),
    )

    assert report.passed is True
    assert report.required_categories == (CompletionEvidenceCategory.RUNTIME,)
    evidence = report.to_completion_evidence()
    assert evidence[0].evidence_id == "verification:runtime-basic:window-visible:round-3"
    assert evidence[0].execution_round == 3
    assert evidence[0].category == CompletionEvidenceCategory.RUNTIME


def test_provider_exception_becomes_unknown_evidence_not_false_success():
    def explode(context, check):
        raise RuntimeError("window API unavailable")

    registry = VerificationRegistry()
    registry.register_provider(FunctionVerificationProvider(
        provider_id="runtime.window",
        category=CompletionEvidenceCategory.RUNTIME,
        callback=explode,
    ))
    registry.register_profile(VerificationProfile(
        profile_id="runtime-basic",
        checks=(VerificationCheck(
            check_id="window-visible",
            provider_id="runtime.window",
            category=CompletionEvidenceCategory.RUNTIME,
        ),),
    ))

    report = VerificationEngine(registry).run(
        "runtime-basic",
        VerificationContext(task_id="task-1", execution_round=1),
    )

    assert report.passed is False
    assert report.pending_required_check_ids == ("window-visible",)
    assert report.results[0].status == VerificationStatus.ERROR
    assert report.to_completion_evidence()[0].status.value == "unknown"


def test_profile_rejects_duplicate_check_ids():
    with pytest.raises(ValueError, match="eindeutig"):
        VerificationProfile(
            profile_id="bad",
            checks=(
                VerificationCheck("same", "p1", CompletionEvidenceCategory.RUNTIME),
                VerificationCheck("same", "p2", CompletionEvidenceCategory.VISUAL),
            ),
        )


def test_engine_rejects_category_mismatch():
    registry = VerificationRegistry()
    registry.register_provider(FunctionVerificationProvider(
        provider_id="runtime.window",
        category=CompletionEvidenceCategory.RUNTIME,
        callback=provider_result(),
    ))
    registry.register_profile(VerificationProfile(
        profile_id="visual",
        checks=(VerificationCheck(
            check_id="screen-green",
            provider_id="runtime.window",
            category=CompletionEvidenceCategory.VISUAL,
        ),),
    ))

    with pytest.raises(ValueError, match="erwartet aber"):
        VerificationEngine(registry).run(
            "visual",
            VerificationContext(task_id="task-1", execution_round=1),
        )


def test_orchestrator_accepts_required_profile_report_before_completion():
    run = AgentRun("task-1")
    orchestrator = AgentOrchestrator(run)

    registry = VerificationRegistry()
    registry.register_provider(FunctionVerificationProvider(
        provider_id="runtime.window",
        category=CompletionEvidenceCategory.RUNTIME,
        callback=provider_result(),
    ))
    profile = VerificationProfile(
        profile_id="runtime-basic",
        checks=(VerificationCheck(
            check_id="window-visible",
            provider_id="runtime.window",
            category=CompletionEvidenceCategory.RUNTIME,
        ),),
    )
    registry.register_profile(profile)
    orchestrator.require_verification_profile(profile)

    orchestrator.begin_execution()
    orchestrator.begin_testing()
    assert orchestrator.handle_verification_result(True, "tests passed") == AgentState.COMPLETION_CHECKING

    report = VerificationEngine(registry).run(
        "runtime-basic",
        VerificationContext(task_id="task-1", execution_round=run.execution_round),
    )
    state = orchestrator.handle_verification_report(report, evaluate=True)

    assert state == AgentState.COMPLETED
    assert run.verification_reports[-1] == report
    assert run.required_verification_profiles[0].profile_id == "runtime-basic"
    assert CompletionEvidenceCategory.RUNTIME in orchestrator.completion_required_categories
    assert run.completion_decision.outcome == CompletionOutcome.COMPLETED


def test_orchestrator_rejects_stale_or_wrong_task_report():
    run = AgentRun("task-1")
    orchestrator = AgentOrchestrator(run)
    orchestrator.begin_execution()

    registry = VerificationRegistry()
    registry.register_provider(FunctionVerificationProvider(
        provider_id="runtime.window",
        category=CompletionEvidenceCategory.RUNTIME,
        callback=provider_result(),
    ))
    registry.register_profile(VerificationProfile(
        profile_id="runtime-basic",
        checks=(VerificationCheck(
            check_id="window-visible",
            provider_id="runtime.window",
            category=CompletionEvidenceCategory.RUNTIME,
        ),),
    ))
    profile = registry.get_profile("runtime-basic")
    orchestrator.require_verification_profile(profile)
    engine = VerificationEngine(registry)

    stale = engine.run(
        "runtime-basic",
        VerificationContext(task_id="task-1", execution_round=99),
    )
    with pytest.raises(ValueError, match="execution_round"):
        orchestrator.handle_verification_report(stale)

    wrong_task = engine.run(
        "runtime-basic",
        VerificationContext(task_id="other", execution_round=run.execution_round),
    )
    with pytest.raises(ValueError, match="task_id"):
        orchestrator.handle_verification_report(wrong_task)


def test_run_reality_projects_required_profiles_and_reports():
    from forgeai.core.agent_reality import RunReality

    run = AgentRun("task-1")
    orchestrator = AgentOrchestrator(run)
    registry = VerificationRegistry()
    registry.register_provider(FunctionVerificationProvider(
        provider_id="runtime.window",
        category=CompletionEvidenceCategory.RUNTIME,
        callback=provider_result(),
    ))
    profile = VerificationProfile(
        profile_id="runtime-basic",
        checks=(VerificationCheck(
            check_id="window-visible",
            provider_id="runtime.window",
            category=CompletionEvidenceCategory.RUNTIME,
        ),),
    )
    registry.register_profile(profile)
    orchestrator.require_verification_profile(profile)
    orchestrator.begin_execution()
    orchestrator.begin_testing()
    report = VerificationEngine(registry).run(
        "runtime-basic",
        VerificationContext(task_id="task-1", execution_round=run.execution_round),
    )
    orchestrator.handle_verification_report(report)

    reality = RunReality.from_agent_run(run, run_id="run-1")

    assert reality.required_verification_profiles[0]["profile_id"] == "runtime-basic"
    assert reality.verification_reports[0]["profile_id"] == "runtime-basic"
    assert reality.verification_reports[0]["execution_round"] == 1


def test_required_checks_same_category_must_all_be_proven():
    def callback(context, check):
        status = (
            VerificationStatus.PASS
            if check.check_id == "window-visible"
            else VerificationStatus.ERROR
        )
        return VerificationResult(
            check_id=check.check_id,
            provider_id=check.provider_id,
            category=CompletionEvidenceCategory.RUNTIME,
            status=status,
            summary=check.check_id,
            source=check.provider_id,
            mode=CompletionEvidenceMode.FACT,
        )

    run = AgentRun("task-1")
    orchestrator = AgentOrchestrator(run)
    registry = VerificationRegistry()
    registry.register_provider(FunctionVerificationProvider(
        provider_id="runtime.window",
        category=CompletionEvidenceCategory.RUNTIME,
        callback=callback,
    ))
    profile = VerificationProfile(
        profile_id="runtime-strict",
        checks=(
            VerificationCheck(
                check_id="window-visible",
                provider_id="runtime.window",
                category=CompletionEvidenceCategory.RUNTIME,
            ),
            VerificationCheck(
                check_id="window-responsive",
                provider_id="runtime.window",
                category=CompletionEvidenceCategory.RUNTIME,
            ),
        ),
    )
    registry.register_profile(profile)
    orchestrator.require_verification_profile(profile)
    orchestrator.begin_execution()
    orchestrator.begin_testing()
    assert orchestrator.handle_verification_result(True, "tests passed") == AgentState.COMPLETION_CHECKING

    report = VerificationEngine(registry).run(
        "runtime-strict",
        VerificationContext(task_id="task-1", execution_round=run.execution_round),
    )
    state = orchestrator.handle_verification_report(report, evaluate=True)

    assert state == AgentState.COMPLETION_CHECKING
    assert run.completion_decision.outcome == CompletionOutcome.PENDING
    assert "required_verification_profile_pending" in run.completion_decision.reason_codes
