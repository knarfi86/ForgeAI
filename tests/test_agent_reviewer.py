from forgeai.ai.agent_contracts import AgentPlan, ReviewDecision
from forgeai.ai.agent_reviewer import AgentReviewer


class FakeRouter:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def generate(self, role, prompt, **kwargs):
        self.calls.append((role, prompt, kwargs))
        return self.response


def make_plan():
    return AgentPlan(
        summary="Neue Funktion erstellen",
        proposed_changes=[
            {
                "action": "create",
                "path": "example.py",
                "description": "Neue Funktion erstellen",
            }
        ],
        rationale="Die Funktion benötigt eine neue Datei.",
    )


def test_reviewer_creates_approve_result():
    router = FakeRouter(
        '{"decision":"approve","findings":[],"required_changes":[],"rationale":"Plan ist plausibel."}'
    )

    reviewer = AgentReviewer(router)
    result = reviewer.review(
        make_plan(),
        "Projektkontext",
    )

    assert result.decision == ReviewDecision.APPROVE
    assert result.findings == []
    assert result.required_changes == []
    assert result.rationale == "Plan ist plausibel."


def test_reviewer_supports_revise():
    router = FakeRouter(
        '{"decision":"revise","findings":["Test fehlt"],"required_changes":["Test ergänzen"],"rationale":"Absicherung fehlt."}'
    )

    reviewer = AgentReviewer(router)
    result = reviewer.review(make_plan())

    assert result.decision == ReviewDecision.REVISE
    assert result.findings == ["Test fehlt"]
    assert result.required_changes == ["Test ergänzen"]


def test_reviewer_supports_reject():
    router = FakeRouter(
        '{"decision":"reject","findings":["Architekturproblem"],"required_changes":[],"rationale":"Ansatz ist ungeeignet."}'
    )

    reviewer = AgentReviewer(router)
    result = reviewer.review(make_plan())

    assert result.decision == ReviewDecision.REJECT


def test_reviewer_uses_reviewer_model_role():
    router = FakeRouter(
        '{"decision":"approve","findings":[],"required_changes":[],"rationale":"OK"}'
    )

    reviewer = AgentReviewer(router)
    reviewer.review(make_plan())

    assert router.calls[0][0] == "reviewer"


def test_reviewer_forwards_plan_and_context():
    router = FakeRouter(
        '{"decision":"approve","findings":[],"required_changes":[],"rationale":"OK"}'
    )

    reviewer = AgentReviewer(router)
    reviewer.review(
        make_plan(),
        "WICHTIGER_PROJEKTKONTEXT",
    )

    prompt = router.calls[0][1]

    assert "Neue Funktion erstellen" in prompt
    assert "example.py" in prompt
    assert "WICHTIGER_PROJEKTKONTEXT" in prompt


def test_reviewer_rejects_invalid_json():
    router = FakeRouter("kein json")

    reviewer = AgentReviewer(router)

    try:
        reviewer.review(make_plan())
    except ValueError as exc:
        assert "kein gültiges JSON" in str(exc)
    else:
        raise AssertionError("Ungültiges Reviewer-JSON wurde akzeptiert.")


def test_reviewer_rejects_invalid_decision():
    router = FakeRouter(
        '{"decision":"maybe","findings":[],"required_changes":[],"rationale":"?"}'
    )

    reviewer = AgentReviewer(router)

    try:
        reviewer.review(make_plan())
    except ValueError as exc:
        assert "ungültige Entscheidung" in str(exc)
    else:
        raise AssertionError("Ungültige Review-Entscheidung wurde akzeptiert.")


def test_reviewer_rejects_invalid_findings():
    router = FakeRouter(
        '{"decision":"approve","findings":"kein array","required_changes":[],"rationale":"OK"}'
    )

    reviewer = AgentReviewer(router)

    try:
        reviewer.review(make_plan())
    except ValueError as exc:
        assert "'findings'" in str(exc)
    else:
        raise AssertionError("Ungültige findings wurden akzeptiert.")


def test_reviewer_rejects_invalid_required_changes():
    router = FakeRouter(
        '{"decision":"approve","findings":[],"required_changes":"kein array","rationale":"OK"}'
    )

    reviewer = AgentReviewer(router)

    try:
        reviewer.review(make_plan())
    except ValueError as exc:
        assert "'required_changes'" in str(exc)
    else:
        raise AssertionError(
            "Ungültige required_changes wurden akzeptiert."
        )


def test_reviewer_does_not_write_files():
    router = FakeRouter(
        '{"decision":"approve","findings":[],"required_changes":[],"rationale":"OK"}'
    )

    reviewer = AgentReviewer(router)
    reviewer.review(make_plan())

    assert not hasattr(reviewer, "workspace_tools")
    assert not hasattr(reviewer, "filesystem")
