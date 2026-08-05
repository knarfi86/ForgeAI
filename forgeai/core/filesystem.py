"""Single local filesystem gateway for workspace data and project files."""

import hashlib
import os
import shutil
from datetime import datetime
from pathlib import Path


class FileSystem:
    """Performs local file access and protects destructive operations by default."""

    TEXT_EXTENSIONS = {
        ".py", ".md", ".txt", ".log", ".json", ".toml", ".yaml", ".yml",
        ".xml", ".lua", ".js", ".ts", ".html", ".css", ".cpp", ".h", ".cs",
        ".java",
    }

    def resolve(self, path: str | Path) -> Path:
        """Return an absolute local path without accessing any network resource."""
        return Path(path).expanduser().resolve()

    def read_text(self, path: str | Path) -> str:
        return self.resolve(path).read_text(encoding="utf-8", errors="replace")

    def write_text(self, path: str | Path, content: str, *, confirmed: bool = False) -> None:
        self._require_confirmation(confirmed)
        self.resolve(path).write_text(content, encoding="utf-8")

    def create_directory(self, path: str | Path, *, confirmed: bool = False) -> Path:
        self._require_confirmation(confirmed)
        directory = self.resolve(path)
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def copy_file(self, source: str | Path, destination: str | Path, *, confirmed: bool = False) -> Path:
        self._require_confirmation(confirmed)
        target = self.resolve(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        return Path(shutil.copy2(self.resolve(source), target))

    def move_file(self, source: str | Path, destination: str | Path, *, confirmed: bool = False) -> Path:
        self._require_confirmation(confirmed)
        target = self.resolve(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        return Path(shutil.move(str(self.resolve(source)), str(target)))

    def delete_file(self, path: str | Path, *, confirmed: bool = False) -> None:
        self._require_confirmation(confirmed)
        target = self.resolve(path)
        if target.is_dir():
            raise IsADirectoryError("Ordner werden nicht durch delete_file entfernt.")
        target.unlink()

    def read_directory(self, path: str | Path) -> list[Path]:
        return sorted(self.resolve(path).iterdir(), key=lambda item: item.name.lower())

    def walk(self, root: str | Path, ignored_directories: set[str]) -> list[tuple[Path, list[str], list[str]]]:
        """Return a deterministic recursive directory listing, excluding ignored folders."""
        result: list[tuple[Path, list[str], list[str]]] = []
        pending = [self.resolve(root)]
        while pending:
            directory = pending.pop()
            directories: list[str] = []
            files: list[str] = []
            for item in self.read_directory(directory):
                if item.is_dir() and item.name not in ignored_directories:
                    directories.append(item.name)
                elif item.is_file():
                    files.append(item.name)
            directories.sort(key=str.lower)
            files.sort(key=str.lower)
            result.append((directory, directories, files))
            pending.extend(directory / name for name in reversed(directories))
        return result

    def search_files(self, root: str | Path, pattern: str) -> list[Path]:
        return [path for path, _, files in self.walk(root, set()) for name in files
                if Path(name).match(pattern)]

    def find_text(self, root: str | Path, text: str) -> list[Path]:
        matches: list[Path] = []
        for directory, _, files in self.walk(root, set()):
            for name in files:
                path = directory / name
                if self.is_previewable(path) and text.casefold() in self.read_text(path).casefold():
                    matches.append(path)
        return matches

    def size(self, path: str | Path) -> int:
        return self.resolve(path).stat().st_size

    def modified_at(self, path: str | Path) -> datetime:
        return datetime.fromtimestamp(self.resolve(path).stat().st_mtime)

    def sha256(self, path: str | Path) -> str:
        digest = hashlib.sha256()
        with self.resolve(path).open("rb") as stream:
            for block in iter(lambda: stream.read(64 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    def is_file(self, path: str | Path) -> bool:
        return self.resolve(path).is_file()

    def is_directory(self, path: str | Path) -> bool:
        return self.resolve(path).is_dir()

    def is_previewable(self, path: str | Path) -> bool:
        return self.resolve(path).suffix.lower() in self.TEXT_EXTENSIONS

    def show_in_explorer(self, path: str | Path) -> None:
        """Open an existing local path with the Windows file manager."""
        os.startfile(self.resolve(path))  # noqa: S606 - intended local Explorer action

    @staticmethod
    def _require_confirmation(confirmed: bool) -> None:
        if not confirmed:
            raise PermissionError("Dateioperation benötigt eine bestätigte Vorschau.")
