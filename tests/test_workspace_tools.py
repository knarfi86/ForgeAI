from pathlib import Path

import pytest

from forgeai.core.workspace_tools import WorkspaceTools


@pytest.fixture
def workspace(tmp_path: Path) -> WorkspaceTools:
    return WorkspaceTools(tmp_path)


def test_replace_text_creates_preview_without_writing(workspace: WorkspaceTools):
    target = workspace.root / "sample.txt"
    target.write_text("ABC\nDEF\n", encoding="utf-8")

    preview = workspace.replace_text("sample.txt", "ABC", "XYZ")

    assert preview.operation == "replace"
    assert preview.path == target
    assert preview.before == "ABC\nDEF\n"
    assert preview.after == "XYZ\nDEF\n"
    assert target.read_text(encoding="utf-8") == "ABC\nDEF\n"


def test_replace_text_rejects_missing_old_block(workspace: WorkspaceTools):
    target = workspace.root / "sample.txt"
    target.write_text("ABC\nDEF\n", encoding="utf-8")

    with pytest.raises(ValueError, match="nicht gefunden"):
        workspace.replace_text("sample.txt", "NOT_FOUND", "XYZ")


def test_replace_text_rejects_multiple_matches(workspace: WorkspaceTools):
    target = workspace.root / "sample.txt"
    target.write_text("ABC\nABC\n", encoding="utf-8")

    with pytest.raises(ValueError, match="2-mal gefunden"):
        workspace.replace_text("sample.txt", "ABC", "XYZ")


def test_replace_text_rejects_empty_old_block(workspace: WorkspaceTools):
    target = workspace.root / "sample.txt"
    target.write_text("ABC\n", encoding="utf-8")

    with pytest.raises(ValueError, match="darf nicht leer sein"):
        workspace.replace_text("sample.txt", "", "XYZ")


def test_insert_before_creates_preview(workspace: WorkspaceTools):
    target = workspace.root / "sample.txt"
    target.write_text("ABC\nDEF\n", encoding="utf-8")

    preview = workspace.insert_before("sample.txt", "DEF", "INSERTED\n")

    assert preview.operation == "insert_before"
    assert preview.after == "ABC\nINSERTED\nDEF\n"
    assert target.read_text(encoding="utf-8") == "ABC\nDEF\n"


def test_insert_before_rejects_missing_anchor(workspace: WorkspaceTools):
    target = workspace.root / "sample.txt"
    target.write_text("ABC\nDEF\n", encoding="utf-8")

    with pytest.raises(ValueError, match="nicht gefunden"):
        workspace.insert_before("sample.txt", "NOT_FOUND", "INSERTED\n")


def test_insert_before_rejects_multiple_anchors(workspace: WorkspaceTools):
    target = workspace.root / "sample.txt"
    target.write_text("ABC\nABC\n", encoding="utf-8")

    with pytest.raises(ValueError, match="2-mal gefunden"):
        workspace.insert_before("sample.txt", "ABC", "INSERTED\n")


def test_insert_after_creates_preview(workspace: WorkspaceTools):
    target = workspace.root / "sample.txt"
    target.write_text("ABC\nDEF\n", encoding="utf-8")

    preview = workspace.insert_after("sample.txt", "ABC", "\nINSERTED")

    assert preview.operation == "insert_after"
    assert preview.after == "ABC\nINSERTED\nDEF\n"
    assert target.read_text(encoding="utf-8") == "ABC\nDEF\n"


def test_insert_after_rejects_missing_anchor(workspace: WorkspaceTools):
    target = workspace.root / "sample.txt"
    target.write_text("ABC\nDEF\n", encoding="utf-8")

    with pytest.raises(ValueError, match="nicht gefunden"):
        workspace.insert_after("sample.txt", "NOT_FOUND", "INSERTED")


def test_insert_after_rejects_multiple_anchors(workspace: WorkspaceTools):
    target = workspace.root / "sample.txt"
    target.write_text("ABC\nABC\n", encoding="utf-8")

    with pytest.raises(ValueError, match="2-mal gefunden"):
        workspace.insert_after("sample.txt", "ABC", "INSERTED")


def test_create_file_creates_preview_without_writing(workspace: WorkspaceTools):
    preview = workspace.create_file("new.txt", "hello")

    assert preview.operation == "create"
    assert preview.before == ""
    assert preview.after == "hello"
    assert not (workspace.root / "new.txt").exists()


def test_create_file_rejects_existing_file(workspace: WorkspaceTools):
    target = workspace.root / "existing.txt"
    target.write_text("already here", encoding="utf-8")

    with pytest.raises(FileExistsError):
        workspace.create_file("existing.txt", "new")


def test_create_file_rejects_existing_directory(workspace: WorkspaceTools):
    target = workspace.root / "existing"
    target.mkdir()

    with pytest.raises(FileExistsError):
        workspace.create_file("existing", "new")


def test_create_directory_creates_preview_without_writing(workspace: WorkspaceTools):
    target = workspace.root / "new_directory"

    preview = workspace.create_directory("new_directory")

    assert preview.operation == "create_directory"
    assert preview.path == target
    assert not target.exists()


def test_create_directory_rejects_existing_directory(workspace: WorkspaceTools):
    target = workspace.root / "existing"
    target.mkdir()

    with pytest.raises(FileExistsError):
        workspace.create_directory("existing")


def test_create_directory_rejects_existing_file(workspace: WorkspaceTools):
    target = workspace.root / "existing.txt"
    target.write_text("file", encoding="utf-8")

    with pytest.raises(FileExistsError):
        workspace.create_directory("existing.txt")


def test_apply_requires_confirmation(workspace: WorkspaceTools):
    target = workspace.root / "sample.txt"
    target.write_text("ABC\n", encoding="utf-8")

    preview = workspace.replace_text("sample.txt", "ABC", "XYZ")

    with pytest.raises(PermissionError, match="bestätigte Vorschau"):
        workspace.apply(preview)

    assert target.read_text(encoding="utf-8") == "ABC\n"


def test_apply_replace_writes_with_confirmation(workspace: WorkspaceTools):
    target = workspace.root / "sample.txt"
    target.write_text("ABC\n", encoding="utf-8")

    preview = workspace.replace_text("sample.txt", "ABC", "XYZ")
    workspace.apply(preview, confirmed=True)

    assert target.read_text(encoding="utf-8") == "XYZ\n"


def test_apply_insert_before_writes_with_confirmation(workspace: WorkspaceTools):
    target = workspace.root / "sample.txt"
    target.write_text("ABC\nDEF\n", encoding="utf-8")

    preview = workspace.insert_before("sample.txt", "DEF", "INSERTED\n")
    workspace.apply(preview, confirmed=True)

    assert target.read_text(encoding="utf-8") == "ABC\nINSERTED\nDEF\n"


def test_apply_insert_after_writes_with_confirmation(workspace: WorkspaceTools):
    target = workspace.root / "sample.txt"
    target.write_text("ABC\nDEF\n", encoding="utf-8")

    preview = workspace.insert_after("sample.txt", "ABC", "\nINSERTED")
    workspace.apply(preview, confirmed=True)

    assert target.read_text(encoding="utf-8") == "ABC\nINSERTED\nDEF\n"


def test_apply_create_writes_with_confirmation(workspace: WorkspaceTools):
    target = workspace.root / "new.txt"

    preview = workspace.create_file("new.txt", "hello")
    workspace.apply(preview, confirmed=True)

    assert target.read_text(encoding="utf-8") == "hello"


def test_apply_create_directory_writes_with_confirmation(workspace: WorkspaceTools):
    target = workspace.root / "new_directory"

    preview = workspace.create_directory("new_directory")
    workspace.apply(preview, confirmed=True)

    assert target.is_dir()


def test_path_traversal_is_rejected(workspace: WorkspaceTools):
    outside = workspace.root.parent / "outside.txt"
    outside.write_text("secret", encoding="utf-8")

    with pytest.raises(ValueError, match="außerhalb"):
        workspace.read_file("../outside.txt")
