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
def workspace_manager(
    tmp_path: Path,
    project: Path,
) -> WorkspaceManager:
    database = WorkspaceDatabase(tmp_path / "workspace.db")
    filesystem = FileSystem()
    indexer = FileIndexer(database, filesystem)

    manager = WorkspaceManager(database, indexer)

    manager.database.upsert_project(
        str(project.resolve()),
        project.name,
    )
    manager.active_project = project.resolve()
    manager.set_project_mode(ProjectMode.WRITE_WITH_CONFIRMATION)

    return manager


def grant_directory(
    workspace_manager: WorkspaceManager,
    relative_path: str,
) -> None:
    target = workspace_manager.active_project / relative_path
    workspace_manager.grant_ai_access(target)


def grant_file(
    workspace_manager: WorkspaceManager,
    relative_path: str,
) -> None:
    target = workspace_manager.active_project / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.touch()
    workspace_manager.grant_ai_access(target)


def test_directory_root_grant_allows_root_file_create(
    workspace_manager: WorkspaceManager,
):
    grant_directory(workspace_manager, ".")

    target = workspace_manager.active_project / "tessto1.txt"

    assert workspace_manager.is_ai_path_granted(target) is True


def test_directory_grant_allows_child_file_create(
    workspace_manager: WorkspaceManager,
    project: Path,
):
    (project / "src").mkdir()

    grant_directory(workspace_manager, "src")

    target = project / "src" / "tessto1.txt"

    assert workspace_manager.is_ai_path_granted(target) is True


def test_directory_grant_denies_sibling_file_create(
    workspace_manager: WorkspaceManager,
    project: Path,
):
    (project / "src").mkdir()
    (project / "tests").mkdir()

    grant_directory(workspace_manager, "src")

    allowed = project / "src" / "new.py"
    denied = project / "tests" / "new.py"

    assert workspace_manager.is_ai_path_granted(allowed) is True
    assert workspace_manager.is_ai_path_granted(denied) is False


def test_file_grant_denies_new_file_create(
    workspace_manager: WorkspaceManager,
):
    grant_file(workspace_manager, "existing.py")

    target = workspace_manager.active_project / "new.py"

    assert workspace_manager.is_ai_path_granted(target) is False


def test_directory_grant_allows_existing_file_edit(
    workspace_manager: WorkspaceManager,
    project: Path,
):
    target = project / "existing.py"
    target.write_text("print('hello')", encoding="utf-8")

    grant_directory(workspace_manager, ".")

    assert workspace_manager.is_ai_path_granted(target) is True


def test_path_outside_project_denied(
    workspace_manager: WorkspaceManager,
    project: Path,
):
    outside = project.parent / "outside.py"

    assert workspace_manager.is_ai_path_granted(outside) is False


def test_nested_directory_grant_allows_nested_create(
    workspace_manager: WorkspaceManager,
    project: Path,
):
    (project / "src").mkdir()

    grant_directory(workspace_manager, "src")

    target = project / "src" / "utils" / "helper.py"

    assert workspace_manager.is_ai_path_granted(target) is True


def test_file_grant_allows_exact_file_edit(
    workspace_manager: WorkspaceManager,
    project: Path,
):
    target = project / "existing.py"
    target.write_text("print('hello')", encoding="utf-8")

    workspace_manager.grant_ai_access(target)

    assert workspace_manager.is_ai_path_granted(target) is True


def test_file_grant_denies_other_file_access(
    workspace_manager: WorkspaceManager,
    project: Path,
):
    allowed = project / "existing.py"
    other = project / "other.py"

    allowed.write_text("allowed", encoding="utf-8")
    other.write_text("other", encoding="utf-8")

    workspace_manager.grant_ai_access(allowed)

    assert workspace_manager.is_ai_path_granted(allowed) is True
    assert workspace_manager.is_ai_path_granted(other) is False


def test_multiple_directory_grants_form_union(
    workspace_manager: WorkspaceManager,
    project: Path,
):
    (project / "src").mkdir()
    (project / "tests").mkdir()

    grant_directory(workspace_manager, "src")
    grant_directory(workspace_manager, "tests")

    src_target = project / "src" / "new.py"
    tests_target = project / "tests" / "new.py"
    docs_target = project / "docs" / "new.py"

    assert workspace_manager.is_ai_path_granted(src_target) is True
    assert workspace_manager.is_ai_path_granted(tests_target) is True
    assert workspace_manager.is_ai_path_granted(docs_target) is False
