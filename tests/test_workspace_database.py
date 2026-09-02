from pathlib import Path

from forgeai.core.models import ProjectMode
from forgeai.core.workspace_database import WorkspaceDatabase


def test_workspace_database_creates_required_tables(tmp_path: Path):
    database = WorkspaceDatabase(tmp_path / "workspace.db")

    rows = database.fetchall(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' ORDER BY name"
    )

    tables = {row["name"] for row in rows}

    assert {
        "chats",
        "messages",
        "settings",
        "projects",
        "project_files",
        "project_folders",
        "project_state",
        "tasks",
        "project_knowledge",
        "project_analysis",
        "ai_access_grants",
    }.issubset(tables)

    database.close()


def test_upsert_project_creates_project_and_default_state(tmp_path: Path):
    database = WorkspaceDatabase(tmp_path / "workspace.db")

    project_path = str((tmp_path / "project").resolve())

    database.upsert_project(project_path, "project")

    project = database.fetchone(
        "SELECT path, name FROM projects WHERE path=?",
        (project_path,),
    )

    state = database.fetchone(
        "SELECT project_path, mode, is_favorite "
        "FROM project_state WHERE project_path=?",
        (project_path,),
    )

    assert project["path"] == project_path
    assert project["name"] == "project"

    assert state["project_path"] == project_path
    assert state["mode"] == ProjectMode.READ_ONLY.value
    assert state["is_favorite"] == 0

    database.close()


def test_upsert_project_preserves_existing_mode(tmp_path: Path):
    database = WorkspaceDatabase(tmp_path / "workspace.db")

    project_path = str((tmp_path / "project").resolve())

    database.upsert_project(project_path, "project")
    database.execute(
        "UPDATE project_state SET mode=? WHERE project_path=?",
        (
            ProjectMode.WRITE_WITH_CONFIRMATION.value,
            project_path,
        ),
    )

    database.upsert_project(project_path, "project-renamed")

    project = database.fetchone(
        "SELECT name FROM projects WHERE path=?",
        (project_path,),
    )
    state = database.fetchone(
        "SELECT mode FROM project_state WHERE project_path=?",
        (project_path,),
    )

    assert project["name"] == "project-renamed"
    assert state["mode"] == ProjectMode.WRITE_WITH_CONFIRMATION.value

    database.close()
