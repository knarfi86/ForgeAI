"""Controlled transfer of explicitly approved local files into chat context."""

from pathlib import Path

from forgeai.core.file_indexer import FileIndexer
from forgeai.core.filesystem import FileSystem
from forgeai.core.workspace_database import WorkspaceDatabase


class AIContextProvider:
    """Reads only persisted, user-approved local project paths for Ollama prompts."""

    MAX_CONTEXT_CHARS = 48_000
    MAX_FILE_CHARS = 12_000

    def __init__(self, database: WorkspaceDatabase, filesystem: FileSystem):
        self.database = database
        self.filesystem = filesystem

    def build(self, project_path: Path | None) -> tuple[str, list[str]]:
        """Build a bounded system-message fragment from granted text files only."""
        if not project_path:
            return "", []
        root = self.filesystem.resolve(project_path)
        paths = self._granted_files(root)
        chunks: list[str] = []
        included: list[str] = []
        used = 0
        for path in paths:
            if not self.filesystem.is_previewable(path):
                continue
            content = self.filesystem.read_text(path)
            relative = path.relative_to(root).as_posix()
            chunk = f"\n\n--- Datei: {relative} ---\n{content[:self.MAX_FILE_CHARS]}"
            if used + len(chunk) > self.MAX_CONTEXT_CHARS:
                break
            chunks.append(chunk)
            included.append(relative)
            used += len(chunk)
        if not chunks:
            return "", []
        header = (
            "Folgende Dateien wurden vom Benutzer explizit für lokalen Projektkontext "
            "freigegeben. Nutze nur diesen Kontext und behaupte keinen Zugriff auf andere Dateien:"
        )
        return header + "".join(chunks), included

    def _granted_files(self, root: Path) -> list[Path]:
        rows = self.database.fetchall(
            "SELECT relative_path, grant_type FROM ai_access_grants WHERE project_path=? ORDER BY created_at",
            (str(root),),
        )
        result: list[Path] = []
        seen: set[Path] = set()
        for row in rows:
            target = self._inside_root(root, row["relative_path"])
            candidates = [target] if row["grant_type"] == "file" else [
                directory / name
                for directory, _, names in self.filesystem.walk(target, FileIndexer.IGNORED_DIRECTORIES)
                for name in names
            ]
            for candidate in candidates:
                if self.filesystem.is_file(candidate) and candidate not in seen:
                    seen.add(candidate)
                    result.append(candidate)
        return result

    def _inside_root(self, root: Path, relative_path: str) -> Path:
        candidate = self.filesystem.resolve(root / relative_path)
        if candidate != root and root not in candidate.parents:
            raise ValueError("Ungültige KI-Freigabe außerhalb des Projekts.")
        return candidate
