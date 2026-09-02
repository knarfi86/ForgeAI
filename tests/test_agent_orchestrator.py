import pytest
from forgeai.ai.agent_orchestrator import AgentOrchestrator
from forgeai.ai.agent_state import AgentRun, AgentState


def test_start_moves_run_to_planning():
    run = AgentRun(task_id="task-1")
    orchestrator = AgentOrchestrator(run)

    assert orchestrator.start() == AgentState.PLANNING
    assert run.state == AgentState.PLANNING


def test_start_rejects_non_idle_run():
    run = AgentRun(task_id="task-1")
    run.transition(AgentState.PLANNING)
    orchestrator = AgentOrchestrator(run)

    try:
        orchestrator.start()
    except RuntimeError:
        pass
    else:
        raise AssertionError("Start eines laufenden Agenten wurde akzeptiert.")


def test_review_can_be_started():
    run = AgentRun(task_id="task-1")
    orchestrator = AgentOrchestrator(run)

    orchestrator.start()

    assert orchestrator.begin_review() == AgentState.REVIEWING
    assert run.review_round == 1


def test_review_can_be_disabled():
    run = AgentRun(task_id="task-1")
    orchestrator = AgentOrchestrator(run, review_enabled=False)

    orchestrator.start()

    assert orchestrator.begin_review() == AgentState.PLANNING
    assert run.review_round == 0


def test_approval_is_required_by_default():
    run = AgentRun(task_id="task-1")
    orchestrator = AgentOrchestrator(run)

    orchestrator.start()
    orchestrator.begin_review()

    assert orchestrator.request_approval() == AgentState.APPROVAL_REQUIRED


def test_approval_can_be_disabled():
    run = AgentRun(task_id="task-1")
    orchestrator = AgentOrchestrator(
        run,
        require_user_approval=False,
    )

    orchestrator.start()

    assert orchestrator.request_approval() == AgentState.EXECUTING
    assert run.execution_round == 1


def test_approve_starts_execution():
    run = AgentRun(task_id="task-1")
    orchestrator = AgentOrchestrator(run)

    orchestrator.start()
    orchestrator.request_approval()

    assert orchestrator.approve() == AgentState.EXECUTING
    assert run.execution_round == 1


def test_approve_requires_approval_state():
    run = AgentRun(task_id="task-1")
    orchestrator = AgentOrchestrator(run)

    orchestrator.start()

    try:
        orchestrator.approve()
    except RuntimeError:
        pass
    else:
        raise AssertionError("Freigabe außerhalb des Freigabestatus wurde akzeptiert.")


def test_execution_moves_to_testing():
    run = AgentRun(task_id="task-1")
    orchestrator = AgentOrchestrator(run)

    orchestrator.start()
    orchestrator.begin_execution()

    assert orchestrator.begin_testing() == AgentState.TESTING


def test_failed_test_can_enter_analysis_and_repair():
    run = AgentRun(task_id="task-1")
    orchestrator = AgentOrchestrator(run)

    orchestrator.start()
    orchestrator.begin_execution()
    orchestrator.begin_testing()

    assert orchestrator.begin_analysis() == AgentState.ANALYZING
    assert orchestrator.begin_repair() == AgentState.REPAIRING
    assert run.repair_attempt == 1


def test_terminal_states_are_supported():
    for method_name, expected_state in (
        ("complete", AgentState.COMPLETED),
        ("fail", AgentState.FAILED),
        ("abort", AgentState.ABORTED),
    ):
        run = AgentRun(task_id="task-1")
        orchestrator = AgentOrchestrator(run)

        orchestrator.start()

        method = getattr(orchestrator, method_name)

        assert method() == expected_state
        assert run.state == expected_state


def test_review_disable_does_not_disable_testing():
    run = AgentRun(task_id="task-1")
    orchestrator = AgentOrchestrator(
        run,
        review_enabled=False,
    )

    orchestrator.start()
    orchestrator.begin_review()
    orchestrator.begin_execution()

    assert orchestrator.begin_testing() == AgentState.TESTING

def test_plan_uses_injected_planner():
    from forgeai.ai.agent_contracts import AgentPlan, AgentTask

    class FakePlanner:
        def plan(self, task, project_context="", revision_context=None):
            assert task.task_id == "task-1"
            assert task.user_request == "Erstelle eine Funktion."
            assert project_context == "Projektkontext"
            return AgentPlan(
                summary="Funktion erstellen",
                proposed_changes=[
                    {
                        "action": "create",
                        "path": "example.py",
                        "description": "Neue Funktion erstellen",
                    }
                ],
                rationale="Die Funktion benötigt eine neue Datei.",
            )

    run = AgentRun(task_id="task-1")
    orchestrator = AgentOrchestrator(
        run,
        planner=FakePlanner(),
    )

    orchestrator.start()

    task = AgentTask(
        task_id="task-1",
        user_request="Erstelle eine Funktion.",
    )

    plan = orchestrator.plan(
        task,
        "Projektkontext",
    )

    assert plan.summary == "Funktion erstellen"
    assert orchestrator.current_plan is plan
    assert run.state == AgentState.PLANNING


def test_plan_requires_planner():
    from forgeai.ai.agent_contracts import AgentTask

    run = AgentRun(task_id="task-1")
    orchestrator = AgentOrchestrator(run)

    orchestrator.start()

    task = AgentTask(
        task_id="task-1",
        user_request="Erstelle eine Funktion.",
    )

    try:
        orchestrator.plan(task)
    except RuntimeError as exc:
        assert "kein AgentPlanner" in str(exc)
    else:
        raise AssertionError("Planung ohne AgentPlanner wurde akzeptiert.")


def test_plan_requires_planning_state():
    from forgeai.ai.agent_contracts import AgentPlan, AgentTask

    class FakePlanner:
        def plan(self, task, project_context="", revision_context=None):
            return AgentPlan(summary="Testplan")

    run = AgentRun(task_id="task-1")
    orchestrator = AgentOrchestrator(
        run,
        planner=FakePlanner(),
    )

    task = AgentTask(
        task_id="task-1",
        user_request="Testaufgabe",
    )

    try:
        orchestrator.plan(task)
    except RuntimeError as exc:
        assert "planning" in str(exc)
    else:
        raise AssertionError("Planung außerhalb von PLANNING wurde akzeptiert.")


def test_plan_does_not_automatically_start_review():
    from forgeai.ai.agent_contracts import AgentPlan, AgentTask

    class FakePlanner:
        def plan(self, task, project_context="", revision_context=None):
            return AgentPlan(summary="Testplan")

    run = AgentRun(task_id="task-1")
    orchestrator = AgentOrchestrator(
        run,
        planner=FakePlanner(),
    )

    orchestrator.start()

    task = AgentTask(
        task_id="task-1",
        user_request="Testaufgabe",
    )

    orchestrator.plan(task)

    assert run.state == AgentState.PLANNING
    assert run.review_round == 0

def test_review_uses_injected_reviewer():
    from forgeai.ai.agent_contracts import AgentPlan, AgentTask, ReviewDecision, ReviewResult

    class FakePlanner:
        def plan(self, task, project_context="", revision_context=None):
            return AgentPlan(summary="Testplan")

    class FakeReviewer:
        def review(self, plan, project_context=""):
            assert plan.summary == "Testplan"
            assert project_context == "Projektkontext"
            return ReviewResult(
                decision=ReviewDecision.APPROVE,
                rationale="Plan ist plausibel.",
            )

    run = AgentRun(task_id="task-1")
    orchestrator = AgentOrchestrator(
        run,
        planner=FakePlanner(),
        reviewer=FakeReviewer(),
    )

    orchestrator.start()

    task = AgentTask(
        task_id="task-1",
        user_request="Testaufgabe",
    )

    orchestrator.plan(task, "Projektkontext")
    orchestrator.begin_review()

    result = orchestrator.review("Projektkontext")

    assert result.decision == ReviewDecision.APPROVE
    assert result.rationale == "Plan ist plausibel."
    assert orchestrator.current_review is result
    assert run.state == AgentState.REVIEWING


def test_review_requires_reviewer():
    from forgeai.ai.agent_contracts import AgentPlan, AgentTask

    class FakePlanner:
        def plan(self, task, project_context="", revision_context=None):
            return AgentPlan(summary="Testplan")

    run = AgentRun(task_id="task-1")
    orchestrator = AgentOrchestrator(
        run,
        planner=FakePlanner(),
    )

    orchestrator.start()

    task = AgentTask(
        task_id="task-1",
        user_request="Testaufgabe",
    )

    orchestrator.plan(task)
    orchestrator.begin_review()

    try:
        orchestrator.review()
    except RuntimeError as exc:
        assert "kein AgentReviewer" in str(exc)
    else:
        raise AssertionError("Review ohne AgentReviewer wurde akzeptiert.")


def test_review_requires_plan():
    from forgeai.ai.agent_reviewer import AgentReviewer

    class FakeReviewer:
        def review(self, plan, project_context=""):
            return None

    run = AgentRun(task_id="task-1")
    orchestrator = AgentOrchestrator(
        run,
        reviewer=FakeReviewer(),
    )

    orchestrator.start()
    orchestrator.begin_review()

    try:
        orchestrator.review()
    except RuntimeError as exc:
        assert "kein AgentPlan" in str(exc)
    else:
        raise AssertionError("Review ohne AgentPlan wurde akzeptiert.")


def test_review_requires_reviewing_state():
    from forgeai.ai.agent_contracts import AgentPlan

    class FakeReviewer:
        def review(self, plan, project_context=""):
            return None

    run = AgentRun(task_id="task-1")
    orchestrator = AgentOrchestrator(
        run,
        reviewer=FakeReviewer(),
    )

    orchestrator.start()
    orchestrator.current_plan = AgentPlan(summary="Testplan")

    try:
        orchestrator.review()
    except RuntimeError as exc:
        assert "reviewing" in str(exc)
    else:
        raise AssertionError("Review außerhalb von REVIEWING wurde akzeptiert.")

def test_handle_approve_requests_user_approval():
    from forgeai.ai.agent_contracts import ReviewDecision, ReviewResult

    run = AgentRun(task_id="task-1")
    orchestrator = AgentOrchestrator(run)

    orchestrator.start()
    orchestrator.begin_review()

    result = ReviewResult(
        decision=ReviewDecision.APPROVE,
        rationale="Plan ist korrekt.",
    )

    assert orchestrator.handle_review_result(result) == AgentState.APPROVAL_REQUIRED
    assert run.state == AgentState.APPROVAL_REQUIRED


def test_handle_approve_can_start_execution_without_user_approval():
    from forgeai.ai.agent_contracts import ReviewDecision, ReviewResult

    run = AgentRun(task_id="task-1")
    orchestrator = AgentOrchestrator(
        run,
        require_user_approval=False,
    )

    orchestrator.start()
    orchestrator.begin_review()

    result = ReviewResult(
        decision=ReviewDecision.APPROVE,
        rationale="Plan ist korrekt.",
    )

    assert orchestrator.handle_review_result(result) == AgentState.EXECUTING
    assert run.execution_round == 1


def test_handle_revise_returns_to_planning():
    from forgeai.ai.agent_contracts import ReviewDecision, ReviewResult

    run = AgentRun(task_id="task-1")
    orchestrator = AgentOrchestrator(run)

    orchestrator.start()
    orchestrator.begin_review()

    result = ReviewResult(
        decision=ReviewDecision.REVISE,
        findings=["Test fehlt."],
        required_changes=["Tests ergänzen."],
        rationale="Plan muss überarbeitet werden.",
    )

    assert orchestrator.handle_review_result(result) == AgentState.PLANNING
    assert run.state == AgentState.PLANNING
    assert orchestrator.current_review is result


def test_handle_reject_aborts_run():
    from forgeai.ai.agent_contracts import ReviewDecision, ReviewResult

    run = AgentRun(task_id="task-1")
    orchestrator = AgentOrchestrator(run)

    orchestrator.start()
    orchestrator.begin_review()

    result = ReviewResult(
        decision=ReviewDecision.REJECT,
        findings=["Architektur ist ungeeignet."],
        rationale="Der vorgeschlagene Ansatz wird verworfen.",
    )

    assert orchestrator.handle_review_result(result) == AgentState.ABORTED
    assert run.state == AgentState.ABORTED
    assert orchestrator.current_review is result


def test_handle_review_result_uses_current_review():
    from forgeai.ai.agent_contracts import ReviewDecision, ReviewResult

    run = AgentRun(task_id="task-1")
    orchestrator = AgentOrchestrator(run)

    orchestrator.start()
    orchestrator.begin_review()

    orchestrator.current_review = ReviewResult(
        decision=ReviewDecision.REVISE,
        rationale="Überarbeitung erforderlich.",
    )

    assert orchestrator.handle_review_result() == AgentState.PLANNING


def test_handle_review_result_requires_result():
    run = AgentRun(task_id="task-1")
    orchestrator = AgentOrchestrator(run)

    try:
        orchestrator.handle_review_result()
    except RuntimeError as exc:
        assert "kein ReviewResult" in str(exc)
    else:
        raise AssertionError(
            "Review-Verarbeitung ohne Ergebnis wurde akzeptiert."
        )

def test_revise_passes_review_context_to_next_planning() -> None:
    from forgeai.ai.agent_contracts import AgentPlan, AgentTask, ReviewDecision, ReviewResult

    class FakePlanner:
        def __init__(self):
            self.calls = []

        def plan(self, task, project_context="", revision_context=None):
            self.calls.append(
                {
                    "task": task,
                    "project_context": project_context,
                    "revision_context": revision_context,
                }
            )
            return AgentPlan(summary=f"Plan {len(self.calls)}")

    class FakeReviewer:
        def review(self, plan, project_context=""):
            return ReviewResult(
                decision=ReviewDecision.REVISE,
                findings=["Der Plan berücksichtigt die Fehlerbehandlung nicht."],
                required_changes=["Fehlerbehandlung ergänzen."],
                rationale="Der Plan muss vor der Ausführung überarbeitet werden.",
            )

    planner = FakePlanner()
    reviewer = FakeReviewer()

    run = AgentRun(task_id="task-1")
    orchestrator = AgentOrchestrator(
        run,
        planner=planner,
        reviewer=reviewer,
    )

    orchestrator.start()

    task = AgentTask(
        task_id="task-1",
        user_request="Erstelle eine Funktion.",
    )

    first_plan = orchestrator.plan(task, "Projektkontext")

    assert first_plan.summary == "Plan 1"
    assert planner.calls[0]["revision_context"] == []

    orchestrator.begin_review()
    review = orchestrator.review("Projektkontext")

    assert review.decision == ReviewDecision.REVISE

    orchestrator.handle_review_result(review)

    assert run.state == AgentState.PLANNING
    assert len(run.revision_context) == 1
    assert run.revision_context[0]["findings"] == [
        "Der Plan berücksichtigt die Fehlerbehandlung nicht."
    ]
    assert run.revision_context[0]["required_changes"] == [
        "Fehlerbehandlung ergänzen."
    ]

    second_plan = orchestrator.plan(task, "Projektkontext")

    assert second_plan.summary == "Plan 2"
    assert len(planner.calls) == 2
    assert planner.calls[1]["revision_context"] == run.revision_context
    assert planner.calls[1]["revision_context"][0]["review_round"] == 1
def test_revise_can_enter_second_review_round_and_approve() -> None:
    from forgeai.ai.agent_contracts import AgentPlan, AgentTask, ReviewDecision, ReviewResult

    class FakePlanner:
        def __init__(self):
            self.calls = 0

        def plan(self, task, project_context="", revision_context=None):
            self.calls += 1
            return AgentPlan(summary=f"Plan {self.calls}")

    class FakeReviewer:
        def __init__(self):
            self.calls = 0

        def review(self, plan, project_context=""):
            self.calls += 1

            if self.calls == 1:
                return ReviewResult(
                    decision=ReviewDecision.REVISE,
                    findings=["Fehlerbehandlung fehlt."],
                    required_changes=["Fehlerbehandlung ergänzen."],
                    rationale="Der Plan ist noch nicht vollständig.",
                )

            return ReviewResult(
                decision=ReviewDecision.APPROVE,
                rationale="Der überarbeitete Plan ist vollständig.",
            )

    planner = FakePlanner()
    reviewer = FakeReviewer()

    run = AgentRun(task_id="task-1")
    orchestrator = AgentOrchestrator(
        run,
        planner=planner,
        reviewer=reviewer,
    )

    orchestrator.start()

    task = AgentTask(
        task_id="task-1",
        user_request="Erstelle eine Funktion.",
    )

    orchestrator.plan(task)

    orchestrator.begin_review()
    first_review = orchestrator.review()

    assert run.review_round == 1
    assert first_review.decision == ReviewDecision.REVISE

    orchestrator.handle_review_result(first_review)

    assert run.state == AgentState.PLANNING

    orchestrator.plan(task)

    orchestrator.begin_review()
    second_review = orchestrator.review()

    assert run.review_round == 2
    assert second_review.decision == ReviewDecision.APPROVE

    orchestrator.handle_review_result(second_review)

    assert run.state == AgentState.APPROVAL_REQUIRED
    assert planner.calls == 2
    assert reviewer.calls == 2
def test_review_limit_aborts_repeated_revision_cycle() -> None:
    from forgeai.ai.agent_contracts import AgentPlan, AgentTask, ReviewDecision, ReviewResult

    class FakePlanner:
        def plan(self, task, project_context="", revision_context=None):
            return AgentPlan(summary="Plan")

    class FakeReviewer:
        def review(self, plan, project_context=""):
            return ReviewResult(
                decision=ReviewDecision.REVISE,
                findings=["Plan ist noch nicht ausreichend."],
                required_changes=["Weitere Überarbeitung erforderlich."],
                rationale="Noch nicht freigabefähig.",
            )

    run = AgentRun(
        task_id="task-1",
        max_review_rounds=2,
    )

    orchestrator = AgentOrchestrator(
        run,
        planner=FakePlanner(),
        reviewer=FakeReviewer(),
    )

    orchestrator.start()

    task = AgentTask(
        task_id="task-1",
        user_request="Erstelle eine Funktion.",
    )

    orchestrator.plan(task)

    orchestrator.begin_review()
    first_review = orchestrator.review()
    orchestrator.handle_review_result(first_review)

    assert run.review_round == 1
    assert run.state == AgentState.PLANNING

    orchestrator.plan(task)

    orchestrator.begin_review()
    second_review = orchestrator.review()
    orchestrator.handle_review_result(second_review)

    assert run.review_round == 2
    assert run.state == AgentState.PLANNING

    with pytest.raises(RuntimeError, match="Review-Runden"):
        orchestrator.begin_review()

