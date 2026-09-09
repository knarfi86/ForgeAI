from pathlib import Path

import pytest

from forgeai.core.ai_context import AIContextProvider
from forgeai.core.file_indexer import FileIndexer
from forgeai.core.filesystem import FileSystem
from forgeai.core.workspace_database import WorkspaceDatabase
from forgeai.core.workspace_manager import WorkspaceManager


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    return root


@pytest.fixture
def provider(
    tmp_path: Path,
    project: Path,
) -> AIContextProvider:
    database = WorkspaceDatabase(tmp_path / "workspace.db")
    filesystem = FileSystem()
    indexer = FileIndexer(database, filesystem)
    manager = WorkspaceManager(database, indexer)

    database.upsert_project(str(project), project.name)
    manager.active_project = project

    return AIContextProvider(
        database,
        filesystem,
        accessible_files_provider=manager.ai_accessible_files,
    )


def grant_file(
    provider: AIContextProvider,
    project: Path,
    relative_path: str,
) -> None:
    provider.database.execute(
        """
        INSERT INTO ai_access_grants(project_path, relative_path, grant_type)
        VALUES (?, ?, 'file')
        """,
        (str(project.resolve()), relative_path),
    )


def grant_directory(
    provider: AIContextProvider,
    project: Path,
    relative_path: str,
) -> None:
    provider.database.execute(
        """
        INSERT INTO ai_access_grants(project_path, relative_path, grant_type)
        VALUES (?, ?, 'directory')
        """,
        (str(project.resolve()), relative_path),
    )


def test_build_without_project_returns_empty_context(
    provider: AIContextProvider,
):
    context, included = provider.build(None)

    assert context == ""
    assert included == []


def test_build_without_grants_returns_empty_context(
    provider: AIContextProvider,
    project: Path,
):
    target = project / "main.py"
    target.write_text("print('hello')", encoding="utf-8")

    context, included = provider.build(project)

    assert context == ""
    assert included == []


def test_build_includes_granted_file(
    provider: AIContextProvider,
    project: Path,
):
    target = project / "main.py"
    target.write_text("print('hello')", encoding="utf-8")

    grant_file(provider, project, "main.py")

    context, included = provider.build(project)

    assert "main.py" in context
    assert "print('hello')" in context
    assert included == ["main.py"]


def test_build_does_not_include_ungranted_file(
    provider: AIContextProvider,
    project: Path,
):
    allowed = project / "allowed.py"
    denied = project / "denied.py"

    allowed.write_text("allowed", encoding="utf-8")
    denied.write_text("denied", encoding="utf-8")

    grant_file(provider, project, "allowed.py")

    context, included = provider.build(project)

    assert "allowed.py" in context
    assert "allowed" in context
    assert "denied.py" not in context
    assert "denied" not in context
    assert included == ["allowed.py"]


def test_build_directory_grant_includes_previewable_children(
    provider: AIContextProvider,
    project: Path,
):
    source = project / "src"
    source.mkdir()

    python_file = source / "main.py"
    text_file = source / "notes.txt"

    python_file.write_text("print('main')", encoding="utf-8")
    text_file.write_text("notes", encoding="utf-8")

    grant_directory(provider, project, "src")

    context, included = provider.build(project)

    assert "src/main.py" in context
    assert "src/notes.txt" in context
    assert "src/main.py" in included
    assert "src/notes.txt" in included


def test_build_ignores_non_previewable_files(
    provider: AIContextProvider,
    project: Path,
):
    text_file = project / "main.py"
    binary_like = project / "image.png"

    text_file.write_text("print('hello')", encoding="utf-8")
    binary_like.write_bytes(b"not really an image")

    grant_file(provider, project, "main.py")
    grant_file(provider, project, "image.png")

    context, included = provider.build(project)

    assert "main.py" in context
    assert "image.png" not in context
    assert included == ["main.py"]


def test_build_exclude_noise_omits_noise_directories(
    provider: AIContextProvider,
    project: Path,
):
    source = project / "src"
    cache = project / ".pytest_cache"

    source.mkdir()
    cache.mkdir()

    source_file = source / "main.py"
    cache_file = cache / "cached.py"

    source_file.write_text("source", encoding="utf-8")
    cache_file.write_text("cache", encoding="utf-8")

    grant_directory(provider, project, ".")

    context, included = provider.build(
        project,
        exclude_noise=True,
    )

    assert "src/main.py" in context
    assert "source" in context
    assert ".pytest_cache/cached.py" not in context
    assert "cache" not in context
    assert "src/main.py" in included
    assert ".pytest_cache/cached.py" not in included


def test_build_always_ignores_indexer_ignored_directories(
    provider: AIContextProvider,
    project: Path,
):
    cache = project / "__pycache__"
    cache.mkdir()

    target = cache / "cached.py"
    target.write_text("cache", encoding="utf-8")

    grant_directory(provider, project, ".")

    context, included = provider.build(
        project,
        exclude_noise=False,
    )

    assert "__pycache__/cached.py" not in context
    assert "cache" not in context
    assert "__pycache__/cached.py" not in included


def test_build_respects_max_file_tokens(
    provider: AIContextProvider,
    project: Path,
):
    target = project / "main.py"
    content = "1234567890" * 10
    target.write_text(content, encoding="utf-8")

    grant_file(provider, project, "main.py")

    context, included = provider.build(
        project,
        max_context_tokens=100,
        max_file_tokens=5,
    )

    assert included == ["main.py"]
    assert "main.py" in context
    assert "1234567890" in context
    assert len(context.split("main.py", 1)[1]) < len(content)


def test_build_respects_total_context_budget(
    provider: AIContextProvider,
    project: Path,
):
    first = project / "first.py"
    second = project / "second.py"

    first.write_text("A" * 100, encoding="utf-8")
    second.write_text("B" * 100, encoding="utf-8")

    grant_file(provider, project, "first.py")
    grant_file(provider, project, "second.py")

    context, included = provider.build(
        project,
        max_context_tokens=35,
        max_file_tokens=20,
    )

    assert "first.py" in context
    assert "first.py" in included
    assert "second.py" not in included
    assert "B" * 50 not in context


def test_build_uses_character_budget_based_on_four_chars_per_token(
    provider: AIContextProvider,
    project: Path,
):
    target = project / "main.py"
    content = "A" * 100
    target.write_text(content, encoding="utf-8")

    grant_file(provider, project, "main.py")

    context, included = provider.build(
        project,
        max_context_tokens=100,
        max_file_tokens=5,
    )

    assert included == ["main.py"]

    file_marker = "\n--- Datei: main.py ---\n"
    file_start = context.index(file_marker) + len(file_marker)
    included_content = context[file_start:]

    assert included_content == "A" * 20


def test_build_returns_relative_posix_paths(
    provider: AIContextProvider,
    project: Path,
):
    source = project / "src"
    source.mkdir()

    target = source / "main.py"
    target.write_text("print('hello')", encoding="utf-8")

    grant_directory(provider, project, "src")

    _, included = provider.build(project)

    assert included == ["src/main.py"]
    assert "\\" not in included[0]


def test_multiple_grants_do_not_duplicate_files(
    provider: AIContextProvider,
    project: Path,
):
    source = project / "src"
    source.mkdir()

    target = source / "main.py"
    target.write_text("print('hello')", encoding="utf-8")

    grant_directory(provider, project, ".")
    grant_directory(provider, project, "src")

    _, included = provider.build(project)

    assert included.count("src/main.py") == 1


def test_build_skips_oversized_file_and_continues(
    provider: AIContextProvider,
    project: Path,
):
    oversized = project / "oversized.py"
    fitting = project / "fitting.py"

    oversized.write_text("A" * 500, encoding="utf-8")
    fitting.write_text("important", encoding="utf-8")

    grant_file(provider, project, "oversized.py")
    grant_file(provider, project, "fitting.py")

    context, included = provider.build(
        project,
        max_context_tokens=35,
        max_file_tokens=100,
    )

    assert "oversized.py" not in included
    assert "fitting.py" in included
    assert "important" in context


def test_build_request_prefers_relevant_file(
    provider: AIContextProvider,
    project: Path,
):
    unrelated = project / "notes.py"
    relevant = project / "game_client.py"

    unrelated.write_text("notes", encoding="utf-8")
    relevant.write_text("send_set_target_mode()", encoding="utf-8")

    grant_file(provider, project, "notes.py")
    grant_file(provider, project, "game_client.py")

    _, included = provider.build(
        project,
        max_context_tokens=100,
        max_file_tokens=10,
        request="?ndere die Zielmodus-Logik in game client",
    )

    assert included[0] == "game_client.py"


def test_build_broad_analysis_prioritizes_entrypoint(
    provider: AIContextProvider,
    project: Path,
):
    helper = project / "helper.py"
    entrypoint = project / "main.py"

    helper.write_text("helper", encoding="utf-8")
    entrypoint.write_text("main()", encoding="utf-8")

    grant_file(provider, project, "helper.py")
    grant_file(provider, project, "main.py")

    provider.database.execute(
        "INSERT INTO project_files("
        "project_path,relative_path,file_type,size_bytes,modified_at,sha256"
        ") VALUES(?,?,?,?,?,?)",
        (str(project.resolve()), "helper.py", "Python", 6, "", ""),
    )
    provider.database.execute(
        "INSERT INTO project_files("
        "project_path,relative_path,file_type,size_bytes,modified_at,sha256"
        ") VALUES(?,?,?,?,?,?)",
        (str(project.resolve()), "main.py", "Python", 7, "", ""),
    )

    _, included = provider.build(
        project,
        max_context_tokens=100,
        max_file_tokens=10,
        request="analysiere das aktuelle projekt auf fehler",
    )

    assert included[0] == "main.py"
