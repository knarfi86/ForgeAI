from pathlib import Path

import pytest

from forgeai.core.file_indexer import FileIndexer
from forgeai.core.filesystem import FileSystem
from forgeai.core.models import ProjectMode
from forgeai.core.workspace_database import WorkspaceDatabase
from forgeai.core.workspace_manager import WorkspaceManager


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    return root


@pytest.fixture
def manager(tmp_path: Path) -> WorkspaceManager:
    database = WorkspaceDatabase(tmp_path / "workspace.db")
    filesystem = FileSystem()
    indexer = FileIndexer(database, filesystem)
    return WorkspaceManager(database, indexer)


@pytest.fixture
def active_manager(
    manager: WorkspaceManager,
    project: Path,
) -> WorkspaceManager:
    manager.database.upsert_project(str(project), project.name)
    manager.active_project = project
    return manager


def test_project_mode_defaults_to_read_only(
    active_manager: WorkspaceManager,
):
    assert active_manager.project_mode() == ProjectMode.READ_ONLY


def test_set_project_mode_persists_mode(
    active_manager: WorkspaceManager,
):
    active_manager.set_project_mode(ProjectMode.WRITE_WITH_CONFIRMATION)

    assert active_manager.project_mode() == ProjectMode.WRITE_WITH_CONFIRMATION


def test_grant_ai_access_for_file(
    active_manager: WorkspaceManager,
    project: Path,
):
    target = project / "main.py"
    target.write_text("print('hello')", encoding="utf-8")

    active_manager.grant_ai_access(target)

    grants = active_manager.ai_grants()

    assert len(grants) == 1
    assert grants[0]["relative_path"] == "main.py"
    assert grants[0]["grant_type"] == "file"
    assert active_manager.is_ai_path_granted(target)


def test_revoke_ai_access_for_file(
    active_manager: WorkspaceManager,
    project: Path,
):
    target = project / "main.py"
    target.write_text("print('hello')", encoding="utf-8")

    active_manager.grant_ai_access(target)
    assert active_manager.is_ai_path_granted(target)

    active_manager.revoke_ai_access(target)

    assert not active_manager.is_ai_path_granted(target)
    assert active_manager.ai_grants() == []


def test_grant_ai_access_for_directory(
    active_manager: WorkspaceManager,
    project: Path,
):
    source = project / "src"
    source.mkdir()

    active_manager.grant_ai_access(source)

    assert active_manager.is_ai_path_granted(source)


def test_directory_grant_allows_existing_children(
    active_manager: WorkspaceManager,
    project: Path,
):
    source = project / "src"
    source.mkdir()

    target = source / "main.py"
    target.write_text("print('hello')", encoding="utf-8")

    active_manager.grant_ai_access(source)

    assert active_manager.is_ai_path_granted(target)


def test_directory_grant_allows_nonexistent_child(
    active_manager: WorkspaceManager,
    project: Path,
):
    source = project / "src"
    source.mkdir()

    future_file = source / "new_file.py"

    active_manager.grant_ai_access(source)

    assert active_manager.is_ai_path_granted(future_file)


def test_file_grant_does_not_allow_other_file(
    active_manager: WorkspaceManager,
    project: Path,
):
    granted = project / "allowed.py"
    other = project / "other.py"

    granted.write_text("allowed", encoding="utf-8")
    other.write_text("other", encoding="utf-8")

    active_manager.grant_ai_access(granted)

    assert active_manager.is_ai_path_granted(granted)
    assert not active_manager.is_ai_path_granted(other)


def test_paths_outside_project_are_not_granted(
    active_manager: WorkspaceManager,
    project: Path,
):
    outside = project.parent / "outside.py"
    outside.write_text("secret", encoding="utf-8")

    assert not active_manager.is_ai_path_granted(outside)


def test_grant_ai_access_rejects_path_outside_project(
    active_manager: WorkspaceManager,
    project: Path,
):
    outside = project.parent / "outside.py"
    outside.write_text("secret", encoding="utf-8")

    with pytest.raises(ValueError, match="auf das aktive Projekt beschränkt"):
        active_manager.grant_ai_access(outside)


def test_session_grant_allows_file_without_persistent_grant(
    active_manager: WorkspaceManager,
    project: Path,
):
    target = project / "session.py"
    target.write_text("print('session')", encoding="utf-8")

    active_manager.grant_session_access(target)

    assert active_manager.is_ai_path_granted(target)
    assert active_manager.ai_grants() == []


def test_session_grant_allows_children_of_granted_directory(
    active_manager: WorkspaceManager,
    project: Path,
):
    source = project / "src"
    source.mkdir()

    target = source / "session.py"
    target.write_text("print('session')", encoding="utf-8")

    active_manager.grant_session_access(source)

    assert active_manager.is_ai_path_granted(target)


def test_session_grant_is_cleared_when_project_closes(
    active_manager: WorkspaceManager,
    project: Path,
):
    target = project / "session.py"
    target.write_text("print('session')", encoding="utf-8")

    active_manager.grant_session_access(target)

    assert active_manager.is_ai_path_granted(target)

    active_manager.close_project()

    assert active_manager.active_project is None
    assert not active_manager.is_ai_path_granted(target)


def test_session_grant_outside_project_is_ignored(
    active_manager: WorkspaceManager,
    project: Path,
):
    outside = project.parent / "outside.py"
    outside.write_text("secret", encoding="utf-8")

    active_manager.grant_session_access(outside)

    assert not active_manager.is_ai_path_granted(outside)


def test_active_model_requires_open_project(
    manager: WorkspaceManager,
):
    with pytest.raises(ValueError, match="Kein Projekt geöffnet"):
        manager.set_active_model("test-model")


def test_active_model_can_be_set_and_read(
    active_manager: WorkspaceManager,
):
    active_manager.set_active_model("qwen-test")

    assert active_manager.get_active_model() == "qwen-test"


def test_active_model_is_cleared_when_project_closes(
    active_manager: WorkspaceManager,
):
    active_manager.set_active_model("qwen-test")

    active_manager.close_project()

    assert active_manager.get_active_model() is None


def test_analyze_with_ollama_uses_local_project_analysis(
    active_manager: WorkspaceManager,
    project: Path,
    monkeypatch,
):
    target = project / "main.py"
    target.write_text("class Demo: pass\n", encoding="utf-8")

    def fail_if_network_analysis_is_used(*args, **kwargs):
        raise AssertionError("Ollama has no project-analysis endpoint")

    monkeypatch.setattr(
        "forgeai.ai.ollama_client.OllamaClient.analyze_project",
        fail_if_network_analysis_is_used,
    )

    active_manager.refresh_index()

    analysis = active_manager.analyze_with_ollama("http://localhost:11434")

    assert analysis["project_name"] == project.name
    assert "main.py" in analysis["files"]
    assert analysis["classes"]["main.py"] == ["Demo"]


def test_ai_accessible_files_includes_recursive_directory_grants(
    active_manager: WorkspaceManager,
    project: Path,
):
    src = project / "src"
    nested = src / "nested"
    nested.mkdir(parents=True)

    root_file = src / "main.py"
    nested_file = nested / "helper.py"
    secret_file = project / "secret.py"

    root_file.write_text("main", encoding="utf-8")
    nested_file.write_text("helper", encoding="utf-8")
    secret_file.write_text("secret", encoding="utf-8")

    active_manager.grant_ai_access(src)

    accessible = active_manager.ai_accessible_files()

    assert root_file in accessible
    assert nested_file in accessible
    assert secret_file not in accessible


def test_ai_accessible_files_includes_session_grants_and_deduplicates(
    active_manager: WorkspaceManager,
    project: Path,
):
    src = project / "src"
    src.mkdir()

    target = src / "main.py"
    target.write_text("main", encoding="utf-8")

    active_manager.grant_ai_access(src)
    active_manager.grant_session_access(target)

    accessible = active_manager.ai_accessible_files()

    assert target in accessible
    assert accessible.count(target) == 1



def test_session_file_grant_does_not_authorize_descendants(
    active_manager: WorkspaceManager,
    project: Path,
):
    target = project / "session.txt"
    target.write_text("session", encoding="utf-8")

    active_manager.grant_session_access(target)

    assert active_manager.is_ai_path_granted(target)
    assert not active_manager.is_ai_path_granted(target / "child.txt")


def test_opening_another_project_clears_session_grants(
    manager: WorkspaceManager,
    tmp_path: Path,
):
    parent = tmp_path / "parent"
    child = parent / "child"
    child.mkdir(parents=True)
    parent_file = parent / "session.txt"
    parent_file.write_text("parent", encoding="utf-8")

    manager.open_project(parent)
    manager.grant_session_access(parent)
    assert manager.is_ai_path_granted(parent_file)

    manager.open_project(child)

    assert manager._session_grants == {}
    assert not manager.is_ai_path_granted(child / "future.txt")


def test_parent_grants_are_inherited_dynamically_not_copied(
    manager: WorkspaceManager,
    tmp_path: Path,
):
    parent = tmp_path / "parent"
    child = parent / "child"
    child.mkdir(parents=True)
    target = child / "main.py"
    target.write_text("print('child')", encoding="utf-8")

    manager.open_project(parent)
    manager.grant_ai_access(parent)

    manager.open_project(child)

    assert manager.ai_grants() == []
    assert any(
        grant["origin"] == "inherited" and grant["relative_path"] == "."
        for grant in manager.effective_ai_grants()
    )
    assert manager.is_ai_path_granted(target)
    assert target.resolve() in manager.ai_accessible_files()

    manager.open_project(parent)
    manager.revoke_ai_access(parent)
    manager.open_project(child)

    assert not manager.is_ai_path_granted(target)
    assert manager.ai_grants() == []


def test_revoking_parent_grant_purges_legacy_child_copy(
    manager: WorkspaceManager,
    tmp_path: Path,
):
    parent = tmp_path / "parent"
    child = parent / "child"
    child.mkdir(parents=True)

    manager.open_project(parent)
    manager.grant_ai_access(parent)
    manager.database.upsert_project(str(child.resolve()), child.name)
    manager.database.execute(
        "INSERT INTO ai_access_grants(project_path,relative_path,grant_type) VALUES(?,?,?)",
        (str(child.resolve()), ".", "directory"),
    )

    manager.revoke_ai_access(parent)
    manager.open_project(child)

    assert manager.ai_grants() == []
