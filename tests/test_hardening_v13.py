from pathlib import Path
import ast


def _main_window_source() -> str:
    return (Path(__file__).resolve().parents[1] / "forgeai/ui/main_window.py").read_text(encoding="utf-8")


def test_project_grant_ui_guards_missing_project_before_workspace_call():
    source = _main_window_source()
    module = ast.parse(source)
    cls = next(node for node in module.body if isinstance(node, ast.ClassDef) and node.name == "MainWindow")
    method = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "grant_ai_access")
    body_text = ast.get_source_segment(source, method) or ""
    assert "if not self.workspace.active_project" in body_text
    assert "KI-Lesefreigaben" in body_text
    assert body_text.index("if not self.workspace.active_project") < body_text.index("self.workspace.grant_ai_access(path)")


def test_bulk_project_grant_ui_guards_missing_project():
    source = _main_window_source()
    assert source.count("Projektbezogene KI-Freigaben benötigen ein aktives Projekt") >= 2
