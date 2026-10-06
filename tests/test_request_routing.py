"""Regression tests for content generation versus file-writing requests."""

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from forgeai.ai.request_routing import (
    is_project_change_request,
    is_tool_execution_request,
    tool_execution_requires_project,
)


@pytest.mark.parametrize("user_text", [
    "erstelle prompt für frau im schlafzimmer erotisch",
    "Erstelle einen FLUX-Prompt für ein Schlafzimmer",
    "Schreibe mir eine Beschreibung für einen Roboter",
    "Erstelle eine Liste mit Einheitenideen",
    "Bitte erstelle einen Video-Prompt für Wan",
    "Beschreibe den vorhandenen Code",
    "Analysiere die Architektur",
    "Zeige mir, warum das Spiel abstürzt",
])
def test_content_requests_are_chat_not_project_changes(user_text):
    assert is_project_change_request(user_text) is False


@pytest.mark.parametrize("user_text", [
    "Erstelle eine neue Datei namens tools.py",
    "Schreibe die Änderungen in die Datei README.md",
    "Erstelle einen Prompt und speichere ihn als Datei",
    "Erstelle einen Prompt und lege ihn in prompts.txt",
    "Ändere main.py und erstelle einen Prompt für den Kommentar",
    "Erstelle ein neues Spiel mit zehn Einheiten",
    "Ändere die Beleuchtung in main.py",
    "Repariere den fehlerhaften Import",
    "Implementiere die neue Einheitensteuerung",
])
def test_project_changes_still_reach_agent(user_text):
    assert is_project_change_request(user_text) is True


def test_word_fragments_do_not_trigger_changes():
    assert is_project_change_request("Beschreibe das Problem") is False


def test_actual_main_window_routing_and_schema_without_qt():
    """Exercise the original UI methods, even on systems without PySide6."""
    source = Path(__file__).resolve().parents[1] / "forgeai/ui/main_window.py"
    module = ast.parse(source.read_text(encoding="utf-8"))
    main_window = next(
        node for node in module.body
        if isinstance(node, ast.ClassDef) and node.name == "MainWindow"
    )
    methods = [
        node for node in main_window.body
        if isinstance(node, ast.FunctionDef)
        and node.name in ("_is_change_request", "_action_response_format")
    ]
    assert len(methods) == 2
    harness = ast.Module(
        body=[ast.ClassDef(
            name="RoutingHarness", bases=[], keywords=[],
            body=methods, decorator_list=[],
        )],
        type_ignores=[],
    )
    project_mode = SimpleNamespace(
        WRITE_WITH_CONFIRMATION="confirm", AUTO_WRITE="auto",
    )
    namespace = {
        "is_project_change_request": is_project_change_request,
        "ProjectMode": project_mode,
    }
    exec(compile(ast.fix_missing_locations(harness), str(source), "exec"), namespace)
    window = namespace["RoutingHarness"]()
    window.workspace = SimpleNamespace(
        active_project="project", project_mode=lambda: "confirm",
    )
    window._is_analysis_request = lambda _: False

    text_request = "erstelle prompt für frau im schlafzimmer erotisch"
    assert window._is_change_request(text_request) is False
    assert window._action_response_format(text_request) is None
    assert window._is_change_request("Ändere main.py") is True
    assert window._action_response_format("Ändere main.py")["type"] == "object"

@pytest.mark.parametrize("user_text", [
    "Prüfe das aktuelle Projekt mit Python auf Syntaxfehler",
    "Pruefe das aktuelle Projekt mit Python auf Syntaxfehler",
    "Prüfe nur forgeai/ai mit Python auf Syntaxfehle",
    "Führe pytest aus",
    "pytest ausführen",
    "Kompiliere die Python-Quellen",
])
def test_explicit_tool_requests_reach_agent_execution(user_text):
    assert is_tool_execution_request(user_text) is True


@pytest.mark.parametrize("user_text", [
    "Analysiere die Architektur",
    "Prüfe die Architektur",
    "Erkläre pytest",
    "Erkläre, wie ich Python auf Syntaxfehler prüfe",
])
def test_reasoning_requests_do_not_become_tool_execution(user_text):
    assert is_tool_execution_request(user_text) is False


def test_python_tool_execution_requires_project_with_current_verification_profile():
    assert tool_execution_requires_project(
        "Prüfe das aktuelle Projekt mit Python auf Syntaxfehler"
    ) is True
    assert tool_execution_requires_project("Führe pytest aus") is True
    assert tool_execution_requires_project("Prüfe den Python-Interpreter") is True


def test_main_window_analysis_classifier_defers_real_tool_execution_without_qt():
    source = Path(__file__).resolve().parents[1] / "forgeai/ui/main_window.py"
    module = ast.parse(source.read_text(encoding="utf-8"))
    main_window = next(
        node for node in module.body
        if isinstance(node, ast.ClassDef) and node.name == "MainWindow"
    )
    method = next(
        node for node in main_window.body
        if isinstance(node, ast.FunctionDef) and node.name == "_is_analysis_request"
    )
    harness = ast.Module(
        body=[ast.ClassDef(
            name="RoutingHarness", bases=[], keywords=[],
            body=[method], decorator_list=[],
        )],
        type_ignores=[],
    )
    namespace = {"is_tool_execution_request": is_tool_execution_request}
    exec(compile(ast.fix_missing_locations(harness), str(source), "exec"), namespace)
    classifier = namespace["RoutingHarness"]._is_analysis_request

    assert classifier("Prüfe die Architektur") is True
    assert classifier("Analysiere das Projekt") is True
    assert classifier("Prüfe das aktuelle Projekt mit Python auf Syntaxfehler") is False
    assert classifier("Führe pytest aus") is False
