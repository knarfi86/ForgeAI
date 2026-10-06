from pathlib import Path

import pytest

from forgeai.ai.request_routing import extract_local_paths, is_local_read_request
from forgeai.core.ai_context import AIContextProvider
from forgeai.core.file_indexer import FileIndexer
from forgeai.core.filesystem import FileSystem
from forgeai.core.workspace_database import WorkspaceDatabase
from forgeai.core.workspace_manager import WorkspaceManager


def make_manager(tmp_path: Path) -> WorkspaceManager:
    database = WorkspaceDatabase(tmp_path / "workspace.db")
    return WorkspaceManager(database, FileIndexer(database, FileSystem()))


def test_normal_chat_does_not_require_local_read_access():
    assert not is_local_read_request("Erkläre mir Quantenmechanik einfach")
    assert not is_local_read_request("Schreibe mir einen lustigen Prompt")


def test_explicit_local_read_request_is_detected():
    assert is_local_read_request("Lies bitte die Datei C:\\Temp\\bericht.txt")
    assert is_local_read_request("Analysiere diesen Ordner")


def test_windows_paths_are_extracted_without_filesystem_access():
    paths = extract_local_paths(
        r'Lies "C:\Users\frank\Desktop\test.txt" und G:\Data\demo.json.'
    )
    assert paths == [r"C:\Users\frank\Desktop\test.txt", r"G:\Data\demo.json"]


def test_external_file_grant_works_without_project(tmp_path: Path):
    manager = make_manager(tmp_path)
    target = tmp_path / "outside.txt"
    target.write_text("forge truth", encoding="utf-8")

    manager.grant_external_ai_access(target)

    assert manager.active_project is None
    assert manager.is_read_path_granted(target)
    assert not manager.is_ai_path_granted(target)


def test_external_directory_grant_covers_children(tmp_path: Path):
    manager = make_manager(tmp_path)
    folder = tmp_path / "shared"
    folder.mkdir()
    target = folder / "child.txt"
    target.write_text("child", encoding="utf-8")

    manager.grant_external_ai_access(folder)

    assert manager.is_read_path_granted(target)


def test_global_read_is_read_only_and_does_not_grant_project_write(tmp_path: Path):
    manager = make_manager(tmp_path)
    target = tmp_path / "anything.txt"
    target.write_text("read me", encoding="utf-8")

    manager.set_global_read_access(True)

    assert manager.global_read_access_enabled()
    assert manager.is_read_path_granted(target)
    assert not manager.is_ai_path_granted(target)


def test_global_read_does_not_enumerate_files_by_itself(tmp_path: Path):
    manager = make_manager(tmp_path)
    target = tmp_path / "anything.txt"
    target.write_text("read me", encoding="utf-8")
    manager.set_global_read_access(True)

    assert manager.ai_accessible_files() == []


def test_expand_read_targets_requires_permission(tmp_path: Path):
    manager = make_manager(tmp_path)
    target = tmp_path / "secret.txt"
    target.write_text("secret", encoding="utf-8")

    assert manager.expand_read_targets([target]) == []

    manager.grant_external_ai_access(target)
    assert manager.expand_read_targets([target]) == [target.resolve()]


def test_projectless_context_can_include_explicit_external_file(tmp_path: Path):
    database = WorkspaceDatabase(tmp_path / "workspace.db")
    filesystem = FileSystem()
    target = tmp_path / "outside.txt"
    target.write_text("external evidence", encoding="utf-8")
    provider = AIContextProvider(database, filesystem, accessible_files_provider=lambda: [])

    context, included = provider.build(None, extra_paths=[target])

    assert "external evidence" in context
    assert included == [f"extern:{target.resolve()}"]


def test_projectless_context_is_empty_without_explicit_external_targets(tmp_path: Path):
    database = WorkspaceDatabase(tmp_path / "workspace.db")
    provider = AIContextProvider(database, FileSystem(), accessible_files_provider=lambda: [])

    assert provider.build(None) == ("", [])


def test_external_grants_persist_in_database(tmp_path: Path):
    database_path = tmp_path / "workspace.db"
    target = tmp_path / "persisted.txt"
    target.write_text("persisted", encoding="utf-8")

    first_db = WorkspaceDatabase(database_path)
    first = WorkspaceManager(first_db, FileIndexer(first_db, FileSystem()))
    first.grant_external_ai_access(target)
    first_db.close()

    second_db = WorkspaceDatabase(database_path)
    second = WorkspaceManager(second_db, FileIndexer(second_db, FileSystem()))
    assert second.is_read_path_granted(target)


def test_project_context_and_external_context_can_coexist(tmp_path: Path):
    database = WorkspaceDatabase(tmp_path / "workspace.db")
    filesystem = FileSystem()
    project = tmp_path / "project"
    project.mkdir()
    project_file = project / "main.py"
    project_file.write_text("print('project')", encoding="utf-8")
    external = tmp_path / "notes.txt"
    external.write_text("external note", encoding="utf-8")

    provider = AIContextProvider(
        database,
        filesystem,
        accessible_files_provider=lambda: [project_file],
    )
    context, included = provider.build(
        project,
        request="analysiere die datei",
        extra_paths=[external],
    )

    assert "print('project')" in context
    assert "external note" in context
    assert "main.py" in included
    assert f"extern:{external.resolve()}" in included


def test_main_window_routes_project_gate_and_read_gate_without_importing_qt():
    import ast

    source = Path(__file__).resolve().parents[1] / "forgeai/ui/main_window.py"
    module = ast.parse(source.read_text(encoding="utf-8"))
    main_window = next(
        node for node in module.body
        if isinstance(node, ast.ClassDef) and node.name == "MainWindow"
    )
    send_message = next(
        node for node in main_window.body
        if isinstance(node, ast.FunctionDef) and node.name == "send_message"
    )
    called = {
        node.func.attr
        for node in ast.walk(send_message)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }

    assert "_ensure_project_for_change_request" in called
    assert "_prepare_read_targets" in called


def test_main_window_exposes_access_ui_and_new_project_action_without_importing_qt():
    source = (Path(__file__).resolve().parents[1] / "forgeai/ui/main_window.py").read_text(encoding="utf-8")

    assert '"Neues Projekt"' in source
    assert '"KI-Lesefreigaben"' in source
    assert "def show_access_grants" in source


def test_unquoted_windows_file_path_with_spaces_is_not_truncated():
    assert extract_local_paths(
        r"Analysiere G:\Two Fronts UE5\Source\main.cpp"
    ) == [r"G:\Two Fronts UE5\Source\main.cpp"]


def test_unquoted_windows_directory_path_with_spaces_is_not_truncated():
    assert extract_local_paths(
        r"Analysiere G:\Two Fronts UE5"
    ) == [r"G:\Two Fronts UE5"]


def test_project_read_grant_uses_project_scope_and_reaches_context(tmp_path: Path):
    manager = make_manager(tmp_path)
    project = tmp_path / "project"
    project.mkdir()
    target = project / "main.py"
    target.write_text("print('project grant')", encoding="utf-8")
    manager.open_project(project)

    manager.grant_read_access(target)

    assert len(manager.ai_grants()) == 1
    assert manager.external_ai_grants() == []
    assert target.resolve() in manager.ai_accessible_files()


def test_read_grant_does_not_enable_project_writes(tmp_path: Path):
    from forgeai.core.models import ProjectMode

    manager = make_manager(tmp_path)
    project = tmp_path / "project"
    project.mkdir()
    target = project / "main.py"
    target.write_text("print('read only')", encoding="utf-8")
    manager.open_project(project)

    manager.grant_read_access(target)

    assert manager.project_mode() == ProjectMode.READ_ONLY


def test_main_window_read_grants_do_not_escalate_project_mode():
    import ast

    source = Path(__file__).resolve().parents[1] / "forgeai/ui/main_window.py"
    module = ast.parse(source.read_text(encoding="utf-8"))
    main_window = next(
        node for node in module.body
        if isinstance(node, ast.ClassDef) and node.name == "MainWindow"
    )
    for method_name in ("open_project", "grant_ai_access", "grant_ai_access_many"):
        method = next(
            node for node in main_window.body
            if isinstance(node, ast.FunctionDef) and node.name == method_name
        )
        calls = {
            node.func.attr
            for node in ast.walk(method)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        assert "set_project_mode" not in calls


def test_access_dialog_uses_scope_aware_read_grants_without_importing_qt():
    source = (
        Path(__file__).resolve().parents[1] / "forgeai/ui/access_grants_dialog.py"
    ).read_text(encoding="utf-8")

    assert "self.workspace.read_grants()" in source
    assert "self.workspace.grant_read_access(path)" in source
    assert "self.workspace.revoke_read_access" in source
