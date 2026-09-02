from pathlib import Path

import pytest

from forgeai.core.filesystem import FileSystem


@pytest.fixture
def filesystem() -> FileSystem:
    return FileSystem()


def test_write_text_requires_confirmation(filesystem: FileSystem, tmp_path: Path):
    target = tmp_path / "sample.txt"

    with pytest.raises(PermissionError, match="bestätigte Vorschau"):
        filesystem.write_text(target, "hello")

    assert not target.exists()


def test_write_text_writes_with_confirmation(filesystem: FileSystem, tmp_path: Path):
    target = tmp_path / "sample.txt"

    filesystem.write_text(target, "hello", confirmed=True)

    assert target.read_text(encoding="utf-8") == "hello"


def test_create_directory_requires_confirmation(
    filesystem: FileSystem,
    tmp_path: Path,
):
    target = tmp_path / "new_directory"

    with pytest.raises(PermissionError, match="bestätigte Vorschau"):
        filesystem.create_directory(target)

    assert not target.exists()


def test_create_directory_creates_with_confirmation(
    filesystem: FileSystem,
    tmp_path: Path,
):
    target = tmp_path / "new_directory"

    result = filesystem.create_directory(target, confirmed=True)

    assert result == target.resolve()
    assert target.is_dir()


def test_delete_file_requires_confirmation(
    filesystem: FileSystem,
    tmp_path: Path,
):
    target = tmp_path / "sample.txt"
    target.write_text("hello", encoding="utf-8")

    with pytest.raises(PermissionError, match="bestätigte Vorschau"):
        filesystem.delete_file(target)

    assert target.exists()


def test_delete_file_deletes_with_confirmation(
    filesystem: FileSystem,
    tmp_path: Path,
):
    target = tmp_path / "sample.txt"
    target.write_text("hello", encoding="utf-8")

    filesystem.delete_file(target, confirmed=True)

    assert not target.exists()


def test_delete_file_rejects_directory(
    filesystem: FileSystem,
    tmp_path: Path,
):
    target = tmp_path / "directory"
    target.mkdir()

    with pytest.raises(IsADirectoryError):
        filesystem.delete_file(target, confirmed=True)

    assert target.is_dir()


def test_move_file_requires_confirmation(
    filesystem: FileSystem,
    tmp_path: Path,
):
    source = tmp_path / "source.txt"
    destination = tmp_path / "destination.txt"
    source.write_text("hello", encoding="utf-8")

    with pytest.raises(PermissionError, match="bestätigte Vorschau"):
        filesystem.move_file(source, destination)

    assert source.exists()
    assert not destination.exists()


def test_move_file_moves_with_confirmation(
    filesystem: FileSystem,
    tmp_path: Path,
):
    source = tmp_path / "source.txt"
    destination = tmp_path / "destination.txt"
    source.write_text("hello", encoding="utf-8")

    result = filesystem.move_file(source, destination, confirmed=True)

    assert result == destination.resolve()
    assert not source.exists()
    assert destination.read_text(encoding="utf-8") == "hello"


def test_copy_file_requires_confirmation(
    filesystem: FileSystem,
    tmp_path: Path,
):
    source = tmp_path / "source.txt"
    destination = tmp_path / "destination.txt"
    source.write_text("hello", encoding="utf-8")

    with pytest.raises(PermissionError, match="bestätigte Vorschau"):
        filesystem.copy_file(source, destination)

    assert source.exists()
    assert not destination.exists()


def test_copy_file_copies_with_confirmation(
    filesystem: FileSystem,
    tmp_path: Path,
):
    source = tmp_path / "source.txt"
    destination = tmp_path / "destination.txt"
    source.write_text("hello", encoding="utf-8")

    result = filesystem.copy_file(source, destination, confirmed=True)

    assert result == destination.resolve()
    assert source.exists()
    assert destination.read_text(encoding="utf-8") == "hello"


def test_read_directory_is_sorted_case_insensitively(
    filesystem: FileSystem,
    tmp_path: Path,
):
    (tmp_path / "zeta.txt").write_text("", encoding="utf-8")
    (tmp_path / "Alpha.txt").write_text("", encoding="utf-8")
    (tmp_path / "beta.txt").write_text("", encoding="utf-8")

    result = filesystem.read_directory(tmp_path)

    assert [item.name for item in result] == [
        "Alpha.txt",
        "beta.txt",
        "zeta.txt",
    ]


def test_walk_excludes_ignored_directories(
    filesystem: FileSystem,
    tmp_path: Path,
):
    ignored = tmp_path / "__pycache__"
    ignored.mkdir()
    (ignored / "ignored.py").write_text("ignored", encoding="utf-8")

    included = tmp_path / "src"
    included.mkdir()
    (included / "main.py").write_text("main", encoding="utf-8")

    result = filesystem.walk(tmp_path, {"__pycache__"})

    all_files = [
        directory / filename
        for directory, _, filenames in result
        for filename in filenames
    ]

    assert included / "main.py" in all_files
    assert ignored / "ignored.py" not in all_files


def test_is_previewable_recognizes_supported_text_extensions(
    filesystem: FileSystem,
):
    assert filesystem.is_previewable("test.py")
    assert filesystem.is_previewable("README.md")
    assert filesystem.is_previewable("config.json")


def test_is_previewable_rejects_unsupported_extension(
    filesystem: FileSystem,
):
    assert not filesystem.is_previewable("image.png")
    assert not filesystem.is_previewable("archive.zip")


def test_sha256_returns_expected_digest(
    filesystem: FileSystem,
    tmp_path: Path,
):
    target = tmp_path / "sample.txt"
    target.write_text("hello", encoding="utf-8")

    assert filesystem.sha256(target) == (
        "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    )


def test_resolve_returns_absolute_path(filesystem: FileSystem, tmp_path: Path):
    target = tmp_path / "sample.txt"

    resolved = filesystem.resolve(target)

    assert resolved.is_absolute()
    assert resolved == target.resolve()
