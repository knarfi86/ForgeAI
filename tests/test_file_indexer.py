from pathlib import Path

import pytest

from forgeai.core.file_indexer import FileIndexer
from forgeai.core.filesystem import FileSystem
from forgeai.core.workspace_database import WorkspaceDatabase


@pytest.fixture
def database(tmp_path: Path) -> WorkspaceDatabase:
    return WorkspaceDatabase(tmp_path / "workspace.db")


@pytest.fixture
def filesystem() -> FileSystem:
    return FileSystem()


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    return root


@pytest.fixture
def indexer(
    database: WorkspaceDatabase,
    filesystem: FileSystem,
) -> FileIndexer:
    return FileIndexer(database, filesystem)


def test_index_collects_supported_files(
    indexer: FileIndexer,
    project: Path,
):
    (project / "main.py").write_text("print('hello')", encoding="utf-8")
    (project / "README.md").write_text("# Test", encoding="utf-8")
    (project / "config.json").write_text("{}", encoding="utf-8")
    (project / "image.png").write_bytes(b"png")

    stats = indexer.index(project)

    assert stats.file_count == 3
    assert stats.file_types == {
        "Python": 1,
        "Markdown": 1,
        "JSON": 1,
    }


def test_index_collects_folders(
    indexer: FileIndexer,
    project: Path,
):
    src = project / "src"
    nested = src / "nested"
    nested.mkdir(parents=True)

    (nested / "main.py").write_text("print('hello')", encoding="utf-8")

    stats = indexer.index(project)

    assert stats.folder_count == 2

    rows = indexer.database.fetchall(
        "SELECT relative_path FROM project_folders "
        "WHERE project_path=? ORDER BY relative_path",
        (str(project.resolve()),),
    )

    assert [row["relative_path"] for row in rows] == [
        "src",
        "src/nested",
    ]


def test_index_ignores_configured_directories(
    indexer: FileIndexer,
    project: Path,
):
    src = project / "src"
    cache = project / "__pycache__"
    venv = project / ".venv"

    src.mkdir()
    cache.mkdir()
    venv.mkdir()

    (src / "main.py").write_text("main", encoding="utf-8")
    (cache / "cached.py").write_text("cache", encoding="utf-8")
    (venv / "venv.py").write_text("venv", encoding="utf-8")

    stats = indexer.index(project)

    assert stats.file_count == 1

    rows = indexer.database.fetchall(
        "SELECT relative_path FROM project_files "
        "WHERE project_path=?",
        (str(project.resolve()),),
    )

    assert [row["relative_path"] for row in rows] == ["src/main.py"]


def test_index_stores_file_metadata(
    indexer: FileIndexer,
    project: Path,
):
    target = project / "main.py"
    target.write_text("hello", encoding="utf-8")

    indexer.index(project)

    row = indexer.database.fetchone(
        "SELECT relative_path, file_type, size_bytes, "
        "modified_at, sha256 FROM project_files "
        "WHERE project_path=?",
        (str(project.resolve()),),
    )

    assert row is not None
    assert row["relative_path"] == "main.py"
    assert row["file_type"] == "Python"
    assert row["size_bytes"] == len("hello".encode("utf-8"))
    assert row["modified_at"]
    assert row["sha256"]


def test_reindex_replaces_previous_index(
    indexer: FileIndexer,
    project: Path,
):
    first = project / "first.py"
    first.write_text("first", encoding="utf-8")

    indexer.index(project)

    first.unlink()

    second = project / "second.py"
    second.write_text("second", encoding="utf-8")

    stats = indexer.index(project)

    assert stats.file_count == 1

    rows = indexer.database.fetchall(
        "SELECT relative_path FROM project_files "
        "WHERE project_path=?",
        (str(project.resolve()),),
    )

    assert [row["relative_path"] for row in rows] == ["second.py"]
