"""Preview-first local workspace tools for future assistant actions."""

import difflib
from dataclasses import dataclass
from pathlib import Path

from forgeai.core.filesystem import FileSystem


@dataclass(frozen=True)
class ChangePreview:
    """An unapplied local file modification with a human-readable diff."""

    operation: str
    path: Path
    before: str
    after: str
    destination: Path | None = None

    @property
    def diff(self) -> str:
        if self.operation == "create_directory":
            return f"Neuer Ordner: {self.path}\n"
        source_name = str(self.path)
        target_name = str(self.destination or self.path)
        return "".join(difflib.unified_diff(
            self.before.splitlines(keepends=True), self.after.splitlines(keepends=True),
            fromfile=source_name, tofile=target_name,
        ))


class WorkspaceTools:
    """Exposes only local, root-confined tools and requires explicit application."""

    def __init__(self, root: str | Path, filesystem: FileSystem | None = None):
        self.filesystem = filesystem or FileSystem()
        self.root = self.filesystem.resolve(root)

    def read_file(self, path: str | Path) -> str:
        return self.filesystem.read_text(self._path(path))

    def read_directory(self, path: str | Path = ".") -> list[str]:
        return [item.name for item in self.filesystem.read_directory(self._path(path))]

    def search_files(self, pattern: str) -> list[str]:
        return [path.relative_to(self.root).as_posix() for path in self.filesystem.search_files(self.root, pattern)]

    def find_text(self, text: str) -> list[str]:
        return [path.relative_to(self.root).as_posix() for path in self.filesystem.find_text(self.root, text)]

    def replace_text(self, path: str | Path, old: str, new: str) -> ChangePreview:
        target = self._path(path)
        before = self.filesystem.read_text(target)
        if old not in before:
            raise ValueError("Der zu ersetzende Text wurde nicht gefunden.")
        return ChangePreview("replace", target, before, before.replace(old, new))

    def create_file(self, path: str | Path, content: str = "") -> ChangePreview:
        target = self._path(path)
        if self.filesystem.is_file(target) or self.filesystem.is_directory(target):
            raise FileExistsError(target)
        return ChangePreview("create", target, "", content)

    def create_directory(self, path: str | Path) -> ChangePreview:
        target = self._path(path)
        if self.filesystem.is_file(target) or self.filesystem.is_directory(target):
            raise FileExistsError(target)
        return ChangePreview("create_directory", target, "", "")

    def rename_file(self, path: str | Path, destination: str | Path) -> ChangePreview:
        target = self._path(path)
        renamed = self._path(destination)
        return ChangePreview("rename", target, self.filesystem.read_text(target), "", renamed)

    def delete_file(self, path: str | Path) -> ChangePreview:
        target = self._path(path)
        return ChangePreview("delete", target, self.filesystem.read_text(target), "")

    def apply(self, preview: ChangePreview, *, confirmed: bool = False) -> None:
        if preview.operation in {"replace", "create"}:
            self.filesystem.write_text(preview.path, preview.after, confirmed=confirmed)
        elif preview.operation == "create_directory":
            self.filesystem.create_directory(preview.path, confirmed=confirmed)
        elif preview.operation == "rename" and preview.destination:
            self.filesystem.move_file(preview.path, preview.destination, confirmed=confirmed)
        elif preview.operation == "delete":
            self.filesystem.delete_file(preview.path, confirmed=confirmed)
        else:
            raise ValueError(f"Unbekannte Dateioperation: {preview.operation}")

    def _path(self, path: str | Path) -> Path:
        candidate = self.filesystem.resolve(self.root / path)
        if candidate != self.root and self.root not in candidate.parents:
            raise ValueError("Dateioperation außerhalb des geöffneten Projekts ist nicht erlaubt.")
        return candidate
