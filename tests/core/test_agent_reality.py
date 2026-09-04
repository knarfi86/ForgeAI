from forgeai.ai.agent_state import AgentState
from forgeai.core.agent_reality import (
    Action,
    ActionStatus,
    AgentEvent,
    AgentIdentity,
    AgentReality,
    AuthorityLevel,
    AuthorityRule,
    Capability,
    CapabilityStatus,
    ContextReality,
    Decision,
    DecisionStatus,
    Evidence,
    EvidenceRelation,
    EventType,
    Observation,
    RealityConfidence,
    RealitySource,
    RunReality,
    TaskReality,
    Uncertainty,
    UncertaintyStatus,
    Verification,
    VerificationOutcome,
)


def test_agent_reality_can_be_constructed() -> None:
    reality = AgentReality(
        identity=AgentIdentity(
            agent_id="agent-test",
            provider="ollama",
            model="test-model",
            role="coder",
        ),
        task=TaskReality(
            task_id="task-test",
            user_request="test request",
            project_path="C:/test/project",
        ),
        run=RunReality(
            run_id="run-test",
            state=AgentState.PLANNING,
        ),
        context=ContextReality(
            context_id="context-test",
            max_tokens=1000,
            estimated_tokens=100,
        ),
    )

    assert reality.identity.model == "test-model"
    assert reality.task.task_id == "task-test"
    assert reality.run.state == AgentState.PLANNING
    assert reality.context is not None
    assert reality.context.max_tokens == 1000


def test_reality_records_observation_and_evidence() -> None:
    observation = Observation(
        observation_id="obs-1",
        type="test_result",
        source=RealitySource.VERIFIER,
        summary="Tests failed",
        success=False,
    )

    evidence = Evidence(
        evidence_id="evidence-1",
        relation=EvidenceRelation.SUPPORTS,
        statement="Verification failed",
        source=RealitySource.VERIFIER,
        observation_ids=[observation.observation_id],
        confidence=RealityConfidence.HIGH,
    )

    assert observation.success is False
    assert evidence.observation_ids == ["obs-1"]
    assert evidence.confidence == RealityConfidence.HIGH


def test_reality_models_cover_authority_action_and_verification() -> None:
    authority = AuthorityRule(
        authority_id="auth-1",
        resource="src/example.py",
        action="write",
        level=AuthorityLevel.CONFIRM_REQUIRED,
        source=RealitySource.WORKSPACE,
        requires_confirmation=True,
    )

    capability = Capability(
        capability_id="cap-1",
        name="write_workspace_file",
        status=CapabilityStatus.AVAILABLE,
    )

    decision = Decision(
        decision_id="decision-1",
        title="Apply change",
        selected_option="apply_preview",
        status=DecisionStatus.PROPOSED,
    )

    action = Action(
        action_id="action-1",
        action_type="replace",
        target="src/example.py",
        status=ActionStatus.PROPOSED,
        authority_id=authority.authority_id,
    )

    verification = Verification(
        verification_id="verification-1",
        target="pytest",
        expected="all tests pass",
        outcome=VerificationOutcome.FAIL,
    )

    assert authority.requires_confirmation is True
    assert capability.status == CapabilityStatus.AVAILABLE
    assert decision.status == DecisionStatus.PROPOSED
    assert action.authority_id == "auth-1"
    assert verification.outcome == VerificationOutcome.FAIL


def test_reality_contains_events_and_uncertainty() -> None:
    event = AgentEvent(
        event_id="event-1",
        event_type=EventType.RUN_STARTED,
        task_id="task-test",
        run_id="run-test",
        actor=RealitySource.ORCHESTRATOR,
        phase="planning",
    )

    uncertainty = Uncertainty(
        uncertainty_id="uncertainty-1",
        question="Why did the test fail?",
        reason="The available output is incomplete.",
        status=UncertaintyStatus.OPEN,
        resolution_action="rerun tests with full output",
    )

    assert event.event_type == EventType.RUN_STARTED
    assert event.actor == RealitySource.ORCHESTRATOR
    assert uncertainty.status == UncertaintyStatus.OPEN
    assert uncertainty.resolution_action is not None
