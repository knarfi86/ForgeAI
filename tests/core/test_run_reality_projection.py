from forgeai.ai.agent_state import AgentRun, AgentState
from forgeai.core.agent_reality import RunReality


def test_run_reality_projects_agent_run() -> None:
    run = AgentRun(
        task_id="task-1",
        state=AgentState.REPAIRING,
        review_round=2,
        execution_round=3,
        repair_attempt=1,
        max_review_rounds=3,
        max_repair_attempts=3,
        history=[
            {
                "state": "planning",
                "review_round": 0,
                "execution_round": 0,
                "repair_attempt": 0,
            },
        ],
        metadata={"model": "test-model"},
        revision_context=[
            {
                "review_round": 1,
                "decision": "revise",
                "findings": ["missing validation"],
                "required_changes": ["add validation"],
                "rationale": "required by review",
            },
        ],
    )

    reality = RunReality.from_agent_run(
        run,
        run_id="run-1",
    )

    assert reality.run_id == "run-1"
    assert reality.state == AgentState.REPAIRING
    assert reality.review_round == 2
    assert reality.execution_round == 3
    assert reality.repair_attempt == 1
    assert reality.max_review_rounds == 3
    assert reality.max_repair_attempts == 3
    assert reality.metadata == {"model": "test-model"}
    assert reality.revision_context[0]["decision"] == "revise"
    assert reality.history[0]["state"] == "planning"


def test_run_reality_projection_is_detached_from_agent_run() -> None:
    run = AgentRun(
        task_id="task-1",
        metadata={"model": "test-model"},
    )

    reality = RunReality.from_agent_run(
        run,
        run_id="run-1",
    )

    reality.metadata["model"] = "changed"

    assert run.metadata["model"] == "test-model"


def test_run_reality_rejects_invalid_source() -> None:
    try:
        RunReality.from_agent_run("invalid", run_id="run-1")  # type: ignore[arg-type]
    except TypeError as exc:
        assert "AgentRun" in str(exc)
    else:
        raise AssertionError("Expected TypeError")


def test_run_reality_projects_recovery_evidence() -> None:
    from forgeai.ai.agent_state import RepairRecord, VerificationRecord
    from forgeai.core.stagnation_detector import StagnationStatus
    from forgeai.core.recovery_escalation import (
        RecoveryEscalationAction,
        RecoveryEscalationDecision,
    )

    run = AgentRun(task_id="task-1")
    run.verification_history.append(VerificationRecord(
        execution_round=1,
        repair_attempt=0,
        success=False,
        test_output="error",
        failure_fingerprint="E-v1-test",
        normalized_output="error",
        planned_paths=("main.py",),
    ))
    run.repair_history.append(RepairRecord(
        repair_attempt=1,
        execution_round=2,
        failure_before="E-v1-test",
        failure_after="E-v1-test",
        success=False,
        analysis_summary="analysis",
        root_cause="cause",
        repair_requirements=("fix",),
        plan_summary="repair",
        planned_paths=("main.py",),
        changed_failure=False,
    ))
    run.stagnation_status = StagnationStatus(
        active=True,
        error_signature="E-v1-test",
        same_error_count=2,
        repeated_paths=("main.py",),
        same_target_count=2,
        reason_codes=("repeated_failure", "repeated_target"),
        detected_after_repair_attempt=1,
    )
    run.recovery_escalation = RecoveryEscalationDecision(
        active=True,
        action=RecoveryEscalationAction.BROADEN_ANALYSIS,
        escalation_round=1,
        failure_signature="E-v1-test",
        repeated_paths=("main.py",),
        repair_attempt=1,
        remaining_repair_attempts=2,
    )
    run.recovery_escalation_history.append(run.recovery_escalation)

    reality = RunReality.from_agent_run(run, run_id="run-1")

    assert reality.verification_history[0]["failure_fingerprint"] == "E-v1-test"
    assert reality.repair_history[0]["planned_paths"] == ("main.py",)
    assert reality.stagnation_status["active"] is True
    assert reality.recovery_escalation["action"] == RecoveryEscalationAction.BROADEN_ANALYSIS
    assert reality.recovery_escalation_history[0]["escalation_round"] == 1
    reality.repair_history[0]["plan_summary"] = "changed"
    assert run.repair_history[0].plan_summary == "repair"


def test_run_reality_projects_completion_gate_state() -> None:
    from forgeai.core.completion_gate import (
        CompletionDecision,
        CompletionEvidence,
        CompletionEvidenceCategory,
        CompletionEvidenceMode,
        CompletionEvidenceStatus,
        CompletionOutcome,
    )

    run = AgentRun(task_id="task-1")
    evidence = CompletionEvidence(
        evidence_id="completion:technical:latest",
        category=CompletionEvidenceCategory.TECHNICAL,
        status=CompletionEvidenceStatus.PASS,
        summary="tests passed",
        source="verifier",
        mode=CompletionEvidenceMode.FACT,
        execution_round=1,
    )
    decision = CompletionDecision(
        outcome=CompletionOutcome.COMPLETED,
        required_categories=(CompletionEvidenceCategory.TECHNICAL,),
        satisfied_categories=(CompletionEvidenceCategory.TECHNICAL,),
        considered_evidence_ids=(evidence.evidence_id,),
    )
    run.completion_evidence.append(evidence)
    run.completion_decision = decision
    run.completion_history.append(decision)

    reality = RunReality.from_agent_run(run, run_id="run-1")

    assert reality.completion_evidence[0]["evidence_id"] == evidence.evidence_id
    assert reality.completion_decision["outcome"] == CompletionOutcome.COMPLETED
    assert reality.completion_history[0]["satisfied_categories"] == (
        CompletionEvidenceCategory.TECHNICAL,
    )
