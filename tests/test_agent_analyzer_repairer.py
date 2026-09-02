from forgeai.ai.agent_analyzer import AgentAnalyzer, RepairAnalysis
from forgeai.ai.agent_contracts import AgentPlan, AgentTask
from forgeai.ai.agent_repairer import AgentRepairer
from forgeai.ai.model_router import ModelRouter


def test_analyzer_parses_valid_response():
    response = """
    {
      "summary": "Tests schlagen wegen eines fehlenden Imports fehl.",
      "findings": ["ImportError in test_example.py"],
      "root_cause": "Das benötigte Modul wird nicht importiert.",
      "repair_requirements": ["Import ergänzen."]
    }
    """

    result = AgentAnalyzer._parse_response(response)

    assert isinstance(result, RepairAnalysis)
    assert result.summary.startswith("Tests schlagen")
    assert result.findings == ["ImportError in test_example.py"]
    assert result.repair_requirements == ["Import ergänzen."]


def test_analyzer_rejects_invalid_response():
    try:
        AgentAnalyzer._parse_response(
            '{"summary": "", "findings": [], "root_cause": "", "repair_requirements": []}'
        )
    except ValueError as exc:
        assert "summary" in str(exc)
    else:
        raise AssertionError("Ungültige Analyzer-Antwort wurde akzeptiert.")


def test_analyzer_uses_advisor_route():
    class FakeRouter(ModelRouter):
        def __init__(self):
            self.calls = []

        def generate(self, role, prompt, **kwargs):
            self.calls.append((role, prompt))
            return (
                '{"summary":"Fehler","findings":[],"root_cause":"Ursache",'
                '"repair_requirements":[]}'
            )

    router = FakeRouter()
    analyzer = AgentAnalyzer(router)

    task = AgentTask("task-1", "Behebe den Fehler.")
    result = analyzer.analyze(
        task,
        "FAILED: test_example",
        "PROJECT_CONTEXT",
    )

    assert result.summary == "Fehler"
    assert router.calls[0][0] == "advisor"


def test_repairer_parses_valid_response():
    response = """
    {
      "summary": "Import reparieren.",
      "proposed_changes": [
        {
          "action": "insert_after",
          "path": "example.py",
          "description": "Fehlenden Import ergänzen."
        }
      ],
      "rationale": "Der Testfehler weist auf den fehlenden Import hin."
    }
    """

    result = AgentRepairer._parse_response(response)

    assert isinstance(result, AgentPlan)
    assert result.summary == "Import reparieren."
    assert result.proposed_changes[0]["action"] == "insert_after"


def test_repairer_rejects_unsupported_action():
    response = """
    {
      "summary": "Reparatur",
      "proposed_changes": [
        {
          "action": "delete_all",
          "path": "example.py",
          "description": "Alles l?schen."
        }
      ],
      "rationale": "Test"
    }
    """

    try:
        AgentRepairer._parse_response(response)
    except ValueError as exc:
        assert "action" in str(exc)
    else:
        raise AssertionError(
            "Nicht unterst?tzte Repairer-Aktion wurde akzeptiert."
        )



def test_repairer_uses_repairer_route():
    class FakeRouter(ModelRouter):
        def __init__(self):
            self.calls = []

        def generate(self, role, prompt, **kwargs):
            self.calls.append((role, prompt))
            return (
                '{"summary":"Reparatur","proposed_changes":[],"rationale":"Test"}'
            )

    router = FakeRouter()
    repairer = AgentRepairer(router)

    task = AgentTask("task-1", "Behebe den Fehler.")
    analysis = RepairAnalysis(
        summary="Fehleranalyse",
        findings=["Fehler gefunden"],
        root_cause="Ursache",
        repair_requirements=["Fehler beheben"],
    )

    result = repairer.repair(task, analysis, "PROJECT_CONTEXT")

    assert result.summary == "Reparatur"
    assert router.calls[0][0] == "repairer"
