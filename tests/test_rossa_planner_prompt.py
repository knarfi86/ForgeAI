from forgeai.ai.agent_contracts import AgentTask
from forgeai.ai.agent_planner import AgentPlanner


def test_rossa_planner_prompt_contains_core_role_and_project_context():
    task = AgentTask(task_id="plan-rossa", user_request="Passe demo.py an.")
    prompt = AgentPlanner._build_prompt(
        task=task,
        project_context="demo.py enthält run()",
        external_context="",
        revision_context=[],
    )

    assert "# ROSSA Systems" in prompt
    assert "# ROSSA Role: Project Planning Agent" in prompt
    assert "TASK_ID: plan-rossa" in prompt
    assert "PROJECT_CONTEXT:" in prompt
    assert '"proposed_changes"' in prompt
    assert "Du bist der Planungsagent von ForgeAI." not in prompt


def test_rossa_planner_prompt_preserves_external_and_revision_context():
    task = AgentTask(task_id="plan-revision", user_request="Überarbeiten")
    prompt = AgentPlanner._build_prompt(
        task=task,
        project_context="PROJECT",
        external_context="EXTERNAL IDEA",
        revision_context=[{
            "findings": ["Problem"],
            "required_changes": ["Fix ergänzen"],
        }],
    )

    assert "EXTERNAL_PLANNER_INPUT:" in prompt
    assert "EXTERNAL IDEA" in prompt
    assert "REVISION_CONTEXT:" in prompt
    assert "Fix ergänzen" in prompt
    assert "Übernimm ihn nicht automatisch." in prompt


def test_rossa_planner_prompt_requires_json_only():
    task = AgentTask(task_id="plan-json", user_request="Planen")
    prompt = AgentPlanner._build_prompt(
        task=task,
        project_context="",
        external_context="",
        revision_context=[],
    )
    assert "Antworte ausschließlich als gültiges JSON." in prompt
    assert "keinen Text außerhalb des JSON-Objekts" in prompt
