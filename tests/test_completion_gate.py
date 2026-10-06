from forgeai.ai.agent_orchestrator import AgentOrchestrator
from forgeai.ai.agent_state import AgentRun, AgentState
from forgeai.core.completion_gate import (
    CompletionEvidence,
    CompletionEvidenceCategory,
    CompletionEvidenceMode,
    CompletionEvidenceStatus,
    CompletionGate,
    CompletionOutcome,
)


def fact(
    evidence_id: str,
    category: CompletionEvidenceCategory,
    status: CompletionEvidenceStatus,
    *,
    execution_round: int = 1,
) -> CompletionEvidence:
    return CompletionEvidence(
        evidence_id=evidence_id,
        category=category,
        status=status,
        summary=evidence_id,
        source="test_tool",
        mode=CompletionEvidenceMode.FACT,
        execution_round=execution_round,
    )


def test_technical_truth_is_always_required():
    decision = CompletionGate().evaluate(
        [fact("runtime:1", CompletionEvidenceCategory.RUNTIME, CompletionEvidenceStatus.PASS)],
        required_categories=(CompletionEvidenceCategory.RUNTIME,),
        current_execution_round=1,
    )

    assert decision.outcome == CompletionOutcome.PENDING
    assert CompletionEvidenceCategory.TECHNICAL in decision.required_categories
    assert CompletionEvidenceCategory.TECHNICAL in decision.pending_categories


def test_all_required_observed_facts_complete():
    decision = CompletionGate().evaluate(
        [
            fact("technical:1", CompletionEvidenceCategory.TECHNICAL, CompletionEvidenceStatus.PASS),
            fact("runtime:1", CompletionEvidenceCategory.RUNTIME, CompletionEvidenceStatus.PASS),
            fact("visual:1", CompletionEvidenceCategory.VISUAL, CompletionEvidenceStatus.PASS),
        ],
        required_categories=(
            CompletionEvidenceCategory.TECHNICAL,
            CompletionEvidenceCategory.RUNTIME,
            CompletionEvidenceCategory.VISUAL,
        ),
        current_execution_round=1,
    )

    assert decision.outcome == CompletionOutcome.COMPLETED
    assert decision.pending_categories == ()
    assert decision.failed_categories == ()


def test_failed_technical_evidence_is_final_failure():
    decision = CompletionGate().evaluate(
        [fact("technical:1", CompletionEvidenceCategory.TECHNICAL, CompletionEvidenceStatus.FAIL)],
        current_execution_round=1,
    )

    assert decision.outcome == CompletionOutcome.FAILED
    assert "technical_verification_failed" in decision.reason_codes


def test_failed_non_technical_requirement_is_partial_completion():
    decision = CompletionGate().evaluate(
        [
            fact("technical:1", CompletionEvidenceCategory.TECHNICAL, CompletionEvidenceStatus.PASS),
            fact("visual:1", CompletionEvidenceCategory.VISUAL, CompletionEvidenceStatus.FAIL),
        ],
        required_categories=(
            CompletionEvidenceCategory.TECHNICAL,
            CompletionEvidenceCategory.VISUAL,
        ),
        current_execution_round=1,
    )

    assert decision.outcome == CompletionOutcome.PARTIALLY_COMPLETED
    assert decision.failed_categories == (CompletionEvidenceCategory.VISUAL,)


def test_objective_inference_does_not_count_as_observed_truth():
    decision = CompletionGate().evaluate(
        [
            CompletionEvidence(
                evidence_id="technical:guess",
                category=CompletionEvidenceCategory.TECHNICAL,
                status=CompletionEvidenceStatus.PASS,
                summary="LLM thinks tests passed",
                source="model",
                mode=CompletionEvidenceMode.INFERENCE,
                execution_round=1,
            )
        ],
        current_execution_round=1,
    )

    assert decision.outcome == CompletionOutcome.PENDING
    assert "technical:guess" in decision.ignored_evidence_ids
    assert "objective_claim_not_observed_fact" in decision.reason_codes


def test_semantic_inference_must_reference_real_fact_evidence():
    decision = CompletionGate().evaluate(
        [
            fact("technical:1", CompletionEvidenceCategory.TECHNICAL, CompletionEvidenceStatus.PASS),
            CompletionEvidence(
                evidence_id="semantic:1",
                category=CompletionEvidenceCategory.SEMANTIC,
                status=CompletionEvidenceStatus.PASS,
                summary="User request fulfilled",
                source="semantic_reviewer",
                mode=CompletionEvidenceMode.INFERENCE,
                supporting_evidence_ids=("made-up:evidence",),
                execution_round=1,
            ),
        ],
        required_categories=(
            CompletionEvidenceCategory.TECHNICAL,
            CompletionEvidenceCategory.SEMANTIC,
        ),
        current_execution_round=1,
    )

    assert decision.outcome == CompletionOutcome.PENDING
    assert "semantic:1" in decision.ignored_evidence_ids
    assert "semantic_inference_missing_support" in decision.reason_codes


def test_semantic_inference_with_fact_support_can_complete():
    decision = CompletionGate().evaluate(
        [
            fact("technical:1", CompletionEvidenceCategory.TECHNICAL, CompletionEvidenceStatus.PASS),
            CompletionEvidence(
                evidence_id="semantic:1",
                category=CompletionEvidenceCategory.SEMANTIC,
                status=CompletionEvidenceStatus.PASS,
                summary="User request fulfilled",
                source="semantic_reviewer",
                mode=CompletionEvidenceMode.INFERENCE,
                supporting_evidence_ids=("technical:1",),
                execution_round=1,
            ),
        ],
        required_categories=(
            CompletionEvidenceCategory.TECHNICAL,
            CompletionEvidenceCategory.SEMANTIC,
        ),
        current_execution_round=1,
    )

    assert decision.outcome == CompletionOutcome.COMPLETED
    assert CompletionEvidenceCategory.SEMANTIC in decision.satisfied_categories


def test_stale_evidence_is_ignored():
    decision = CompletionGate().evaluate(
        [fact(
            "technical:old",
            CompletionEvidenceCategory.TECHNICAL,
            CompletionEvidenceStatus.PASS,
            execution_round=1,
        )],
        current_execution_round=2,
    )

    assert decision.outcome == CompletionOutcome.PENDING
    assert "technical:old" in decision.ignored_evidence_ids
    assert "stale_evidence_ignored" in decision.reason_codes


def test_orchestrator_keeps_existing_technical_only_flow_completed():
    run = AgentRun("task-1")
    orchestrator = AgentOrchestrator(run)

    orchestrator.begin_execution()
    orchestrator.begin_testing()
    state = orchestrator.handle_verification_result(True, "12 passed")

    assert state == AgentState.COMPLETED
    assert run.completion_decision.outcome == CompletionOutcome.COMPLETED
    assert run.completion_evidence[-1].category == CompletionEvidenceCategory.TECHNICAL


def test_orchestrator_waits_when_semantic_evidence_is_required():
    run = AgentRun("task-1")
    orchestrator = AgentOrchestrator(
        run,
        completion_required_categories=(
            CompletionEvidenceCategory.TECHNICAL,
            CompletionEvidenceCategory.SEMANTIC,
        ),
    )

    orchestrator.begin_execution()
    orchestrator.begin_testing()
    state = orchestrator.handle_verification_result(True, "12 passed")

    assert state == AgentState.COMPLETION_CHECKING
    assert run.completion_decision.outcome == CompletionOutcome.PENDING
    assert run.completion_decision.pending_categories == (
        CompletionEvidenceCategory.SEMANTIC,
    )


def test_orchestrator_finishes_after_evidence_backed_semantic_check():
    run = AgentRun("task-1")
    orchestrator = AgentOrchestrator(
        run,
        completion_required_categories=(
            CompletionEvidenceCategory.TECHNICAL,
            CompletionEvidenceCategory.SEMANTIC,
        ),
    )

    orchestrator.begin_execution()
    orchestrator.begin_testing()
    assert orchestrator.handle_verification_result(True, "12 passed") == AgentState.COMPLETION_CHECKING

    state = orchestrator.add_completion_evidence(
        CompletionEvidence(
            evidence_id="semantic:latest",
            category=CompletionEvidenceCategory.SEMANTIC,
            status=CompletionEvidenceStatus.PASS,
            summary="Requested behavior is supported by current evidence.",
            source="semantic_reviewer",
            mode=CompletionEvidenceMode.INFERENCE,
            supporting_evidence_ids=("completion:technical:latest",),
            execution_round=run.execution_round,
        ),
        evaluate=True,
    )

    assert state == AgentState.COMPLETED
    assert run.completion_decision.outcome == CompletionOutcome.COMPLETED


def test_orchestrator_marks_failed_visual_requirement_as_partial():
    run = AgentRun("task-1")
    orchestrator = AgentOrchestrator(
        run,
        completion_required_categories=(
            CompletionEvidenceCategory.TECHNICAL,
            CompletionEvidenceCategory.VISUAL,
        ),
    )

    orchestrator.begin_execution()
    orchestrator.begin_testing()
    assert orchestrator.handle_verification_result(True, "12 passed") == AgentState.COMPLETION_CHECKING

    state = orchestrator.add_completion_evidence(
        fact(
            "visual:latest",
            CompletionEvidenceCategory.VISUAL,
            CompletionEvidenceStatus.FAIL,
            execution_round=run.execution_round,
        ),
        evaluate=True,
    )

    assert state == AgentState.PARTIALLY_COMPLETED
    assert run.completion_decision.outcome == CompletionOutcome.PARTIALLY_COMPLETED
