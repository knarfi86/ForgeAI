from forgeai.ai.agent_contracts import AgentPlan
from forgeai.ai.agent_reviewer import AgentReviewer


def make_plan() -> AgentPlan:
    return AgentPlan(
        summary="Neue Funktion erstellen",
        proposed_changes=[{
            "action": "create",
            "path": "example.py",
            "description": "Neue Funktion erstellen",
        }],
        rationale="Die Funktion benötigt eine neue Datei.",
    )


def test_rossa_reviewer_prompt_contains_core_role_plan_and_context():
    prompt = AgentReviewer._build_prompt(
        plan=make_plan(),
        project_context="WICHTIGER_PROJEKTKONTEXT",
    )

    assert "# ROSSA Systems" in prompt
    assert "# ROSSA Role: Plan Review Agent" in prompt
    assert "PROJECT_CONTEXT:" in prompt
    assert "WICHTIGER_PROJEKTKONTEXT" in prompt
    assert "AGENT_PLAN:" in prompt
    assert "example.py" in prompt
    assert '"decision": "approve"' in prompt
    assert "Du bist der kritische Review-Agent von ForgeAI." not in prompt


def test_rossa_reviewer_prompt_preserves_evidence_policy():
    prompt = AgentReviewer._build_prompt(
        plan=make_plan(),
        project_context="Projektkontext ohne Inhaltsrichtlinie",
    )

    assert "Erfinde keine generelle Inhaltsrichtlinie" in prompt
    assert "tatsächlichen Anforderung" in prompt
    assert "Sicherheitsgrenzen des verwendeten Modells bleiben unberührt" in prompt
    assert "approve" in prompt
    assert "revise" in prompt
    assert "reject" in prompt


def test_rossa_reviewer_prompt_requires_json_only():
    prompt = AgentReviewer._build_prompt(plan=make_plan(), project_context="")
    assert "Antworte ausschließlich als gültiges JSON." in prompt
    assert "keinen Text außerhalb des JSON-Objekts" in prompt
