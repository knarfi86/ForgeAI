from forgeai.ai.agent_analyzer import AgentAnalyzer
from forgeai.ai.agent_contracts import AgentPlan, AgentTask


def test_rossa_repair_analyzer_prompt_contains_core_role_and_runtime_context():
    task = AgentTask(task_id="task-rossa", user_request="Fehler beheben")
    plan = AgentPlan(
        summary="Aktueller Plan",
        proposed_changes=[{"path": "demo.py", "action": "replace", "description": "Fix"}],
        rationale="Testgrund",
    )

    prompt = AgentAnalyzer._build_prompt(
        task=task,
        test_output="AssertionError: expected 1 got 0",
        project_context="demo.py enthält run()",
        current_plan=plan,
    )

    assert "# ROSSA Systems" in prompt
    assert "# ROSSA Role: Repair Analysis Agent" in prompt
    assert "TASK_ID: task-rossa" in prompt
    assert "PROJECT_CONTEXT:" in prompt
    assert "TEST_OUTPUT:" in prompt
    assert '"repair_requirements"' in prompt
    assert "Erfinde keine Caller oder Abhängigkeiten" in prompt
    assert "Du bist der Analyse-Agent von ForgeAI." not in prompt


def test_rossa_repair_analyzer_prompt_requires_json_only():
    task = AgentTask(task_id="task-json", user_request="Analysieren")
    prompt = AgentAnalyzer._build_prompt(
        task=task,
        test_output="failure",
        project_context="",
        current_plan=None,
    )
    assert "Antworte ausschließlich als gültiges JSON." in prompt
    assert "keinen Text außerhalb des JSON-Objekts" in prompt
