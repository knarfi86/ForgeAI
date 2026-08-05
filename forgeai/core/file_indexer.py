"""Recursive, metadata-only indexing of supported project files."""

from collections import Counter
from pathlib import Path

from forgeai.core.filesystem import FileSystem
from forgeai.core.models import IndexedFile, ProjectStatistics
from forgeai.core.workspace_database import WorkspaceDatabase


class FileIndexer:
    """Indexes files and folders without analysing file contents."""

    EXTENSIONS = {
        ".py": "Python", ".md": "Markdown", ".json": "JSON",
        ".yaml": "YAML", ".yml": "YAML", ".toml": "TOML", ".xml": "XML", ".lua": "Lua",
        ".txt": "Text",
    }
    IGNORED_DIRECTORIES = {".git", ".venv", "__pycache__", "node_modules"}

    def __init__(self, database: WorkspaceDatabase, filesystem: FileSystem | None = None):
        self.database = database
        self.filesystem = filesystem or FileSystem()

    def index(self, project_path: str | Path) -> ProjectStatistics:
        root = self.filesystem.resolve(project_path)
        files, folders = self._collect(root)
        self._store(root, files, folders)
        return ProjectStatistics(len(files), len(folders), dict(Counter(f.file_type for f in files)))

    def _collect(self, root: Path) -> tuple[list[IndexedFile], list[str]]:
        files: list[IndexedFile] = []
        folders: list[str] = []
        for current, directory_names, file_names in self.filesystem.walk(root, self.IGNORED_DIRECTORIES):
            for name in directory_names:
                folders.append((current / name).relative_to(root).as_posix())
            for name in file_names:
                path = current / name
                if path.suffix.lower() in self.EXTENSIONS:
                    files.append(IndexedFile(
                        path=path, relative_path=path.relative_to(root).as_posix(),
                        file_type=self.EXTENSIONS[path.suffix.lower()],
                        size_bytes=self.filesystem.size(path),
                        modified_at=self.filesystem.modified_at(path).isoformat(),
                        sha256=self.filesystem.sha256(path),
                    ))
        return files, folders

    def _store(self, root: Path, files: list[IndexedFile], folders: list[str]) -> None:
        project = str(root)
        self.database.execute("DELETE FROM project_files WHERE project_path=?", (project,))
        self.database.execute("DELETE FROM project_folders WHERE project_path=?", (project,))
        for item in files:
            self.database.execute(
                "INSERT INTO project_files(project_path,relative_path,file_type,size_bytes,modified_at,sha256) VALUES(?,?,?,?,?,?)",
                (project, item.relative_path, item.file_type, item.size_bytes, item.modified_at, item.sha256),
            )
        for folder in folders:
            self.database.execute(
                "INSERT INTO project_folders(project_path,relative_path) VALUES(?,?)",
                (project, folder),
            )
