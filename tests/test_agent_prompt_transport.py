from __future__ import annotations

import json

from forgeai.ai.agent_analyzer import AgentAnalyzer, RepairAnalysis
from forgeai.ai.agent_contracts import AgentPlan, AgentTask
from forgeai.ai.agent_planner import AgentPlanner
from forgeai.ai.agent_repairer import AgentRepairer
from forgeai.ai.agent_reviewer import AgentReviewer
from forgeai.ai.model_router import ModelRouter


class CaptureProvider:
    def __init__(self) -> None:
        self.calls = []
        self.response = "{}"

    def generate(self, prompt: str, model: str, **kwargs):
        self.calls.append((prompt, model, kwargs))
        return self.response


def router_with(provider: CaptureProvider) -> ModelRouter:
    router = ModelRouter()
    router.register_provider("capture", provider)
    router.set_primary("capture", "test-model")
    return router


def assert_separated(
    provider: CaptureProvider,
    role_marker: str,
    user_marker: str,
    contract_marker: str,
) -> None:
    prompt, model, kwargs = provider.calls[-1]
    assert model == "test-model"
    system_prompt = kwargs.get("system_prompt")
    assert isinstance(system_prompt, str)
    assert "# ROSSA Systems" in system_prompt
    assert role_marker in system_prompt
    assert contract_marker in system_prompt
    assert user_marker not in system_prompt
    assert user_marker in prompt
    assert contract_marker not in prompt
    assert "# ROSSA Systems" not in prompt


def test_planner_system_role_is_transport_separated():
    provider = CaptureProvider()
    provider.response = json.dumps({
        "summary": "Plan", "proposed_changes": [], "plugin_actions": [], "rationale": "OK"
    })
    AgentPlanner(router_with(provider)).plan(
        AgentTask("t1", "Passe demo.py an."), "PROJECT_DATA_TOKEN"
    )
    assert_separated(provider, "# ROSSA Role: Project Planning Agent", "PROJECT_DATA_TOKEN", "## Planning Contract")


def test_reviewer_system_role_is_transport_separated():
    provider = CaptureProvider()
    provider.response = json.dumps({
        "decision": "approve", "findings": [], "required_changes": [], "rationale": "OK"
    })
    plan = AgentPlan(summary="Plan", proposed_changes=[], rationale="OK")
    AgentReviewer(router_with(provider)).review(plan, "PROJECT_DATA_TOKEN")
    assert_separated(provider, "# ROSSA Role: Plan Review Agent", "PROJECT_DATA_TOKEN", "## Review Contract")


def test_analyzer_system_role_and_json_schema_are_transport_separated():
    provider = CaptureProvider()
    provider.response = json.dumps({
        "summary": "Fehler", "findings": [], "root_cause": "Ursache", "repair_requirements": []
    })
    AgentAnalyzer(router_with(provider)).analyze(
        AgentTask("t2", "Behebe Fehler"), "FAILURE_DATA_TOKEN", "PROJECT_DATA_TOKEN"
    )
    assert_separated(provider, "# ROSSA Role: Repair Analysis Agent", "FAILURE_DATA_TOKEN", "## Analysis Contract")
    assert provider.calls[-1][2]["response_format"]["type"] == "object"


def test_repairer_system_role_and_json_schema_are_transport_separated():
    provider = CaptureProvider()
    provider.response = json.dumps({
        "summary": "Repair", "proposed_changes": [], "plugin_actions": [], "rationale": "OK"
    })
    AgentRepairer(router_with(provider)).repair(
        AgentTask("t3", "Behebe Fehler"),
        RepairAnalysis(summary="Analyse", root_cause="Ursache"),
        "PROJECT_DATA_TOKEN",
    )
    assert_separated(provider, "# ROSSA Role: Repair Planning Agent", "PROJECT_DATA_TOKEN", "## Repair Planning Contract")
    assert provider.calls[-1][2]["response_format"]["type"] == "object"
