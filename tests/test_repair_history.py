from forgeai.ai.agent_analyzer import RepairAnalysis
from forgeai.ai.agent_contracts import AgentPlan
from forgeai.ai.agent_orchestrator import AgentOrchestrator
from forgeai.ai.agent_state import AgentRun


def failed_repair_round(orchestrator, *, output, path="main.py", root_cause="cause"):
    orchestrator.current_analysis = RepairAnalysis(
        summary="analysis",
        root_cause=root_cause,
        repair_requirements=["fix it"],
    )
    orchestrator.current_plan = AgentPlan(
        summary="repair",
        proposed_changes=[{
            "action": "replace",
            "path": path,
            "description": "repair target",
        }],
        metadata={"source": "agent_repairer"},
    )
    orchestrator.begin_repair()
    orchestrator.begin_execution()
    orchestrator.begin_testing()
    return orchestrator.handle_verification_result(False, output)


def test_repair_history_links_before_after_analysis_plan_and_verification():
    run = AgentRun("task-1")
    orchestrator = AgentOrchestrator(run)

    orchestrator.begin_execution()
    orchestrator.begin_testing()
    orchestrator.handle_verification_result(False, "KeyError: velocity")
    before = run.verification_history[-1].failure_fingerprint

    failed_repair_round(orchestrator, output="KeyError: health")

    assert len(run.repair_history) == 1
    record = run.repair_history[0]
    assert record.repair_attempt == 1
    assert record.failure_before == before
    assert record.failure_after == run.verification_history[-1].failure_fingerprint
    assert record.changed_failure is True
    assert record.success is False
    assert record.analysis_summary == "analysis"
    assert record.root_cause == "cause"
    assert record.repair_requirements == ("fix it",)
    assert record.plan_summary == "repair"
    assert record.planned_paths == ("main.py",)


def test_orchestrator_detects_stagnation_and_requests_broader_analysis():
    run = AgentRun("task-1", max_repair_attempts=3)
    orchestrator = AgentOrchestrator(run)

    orchestrator.begin_execution()
    orchestrator.begin_testing()
    orchestrator.handle_verification_result(False, "KeyError: velocity")

    failed_repair_round(orchestrator, output="KeyError: velocity")
    assert run.stagnation_status.active is False

    failed_repair_round(orchestrator, output="KeyError: velocity")
    assert run.stagnation_status.active is True
    assert run.stagnation_status.same_error_count == 3
    assert run.stagnation_status.same_target_count == 2
    assert run.state.value == "analyzing"
    assert run.recovery_escalation.active is True
    assert run.recovery_escalation.action.value == "broaden_analysis"


def test_successful_repair_is_recorded_and_clears_active_stagnation():
    run = AgentRun("task-1", max_repair_attempts=3)
    orchestrator = AgentOrchestrator(run)

    orchestrator.begin_execution()
    orchestrator.begin_testing()
    orchestrator.handle_verification_result(False, "KeyError: velocity")
    failed_repair_round(orchestrator, output="KeyError: velocity")
    failed_repair_round(orchestrator, output="KeyError: velocity")
    assert run.stagnation_status.active is True

    orchestrator.current_analysis = RepairAnalysis(
        summary="analysis", root_cause="caller", repair_requirements=["fix caller"]
    )
    orchestrator.current_plan = AgentPlan(
        summary="repair caller",
        proposed_changes=[{
            "action": "replace",
            "path": "caller.py",
            "description": "fix caller",
        }],
        metadata={"source": "agent_repairer"},
    )
    orchestrator.begin_repair()
    orchestrator.begin_execution()
    orchestrator.begin_testing()
    orchestrator.handle_verification_result(True, "3 passed in 0.2s")

    assert run.repair_history[-1].success is True
    assert run.repair_history[-1].failure_after is None
    assert run.stagnation_status.active is False
    assert run.state.value == "completed"


def test_non_repair_execution_does_not_create_repair_history():
    run = AgentRun("task-1")
    orchestrator = AgentOrchestrator(run)
    orchestrator.current_plan = AgentPlan(
        summary="normal plan",
        proposed_changes=[{"path": "main.py", "action": "replace"}],
    )
    orchestrator.begin_execution()
    orchestrator.begin_testing()
    orchestrator.handle_verification_result(False, "error")
    assert run.repair_history == []


def test_retesting_same_repair_attempt_does_not_duplicate_repair_history():
    run = AgentRun("task-1")
    orchestrator = AgentOrchestrator(run)

    orchestrator.begin_execution()
    orchestrator.begin_testing()
    orchestrator.handle_verification_result(False, "KeyError: velocity")
    failed_repair_round(orchestrator, output="KeyError: velocity")
    assert len(run.repair_history) == 1

    # A pure re-execution/re-test without begin_repair is another verification,
    # not another repair attempt.
    orchestrator.begin_execution()
    orchestrator.begin_testing()
    orchestrator.handle_verification_result(False, "KeyError: velocity")
    assert len(run.repair_history) == 1
    assert len(run.verification_history) == 3
