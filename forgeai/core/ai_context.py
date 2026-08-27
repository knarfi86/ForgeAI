"""Controlled transfer of explicitly approved local files into chat context."""

from pathlib import Path

from forgeai.core.file_indexer import FileIndexer
from forgeai.core.filesystem import FileSystem
from forgeai.core.workspace_database import WorkspaceDatabase


class AIContextProvider:
    """Reads only persisted, user-approved local project paths for Ollama prompts."""

    CHARS_PER_TOKEN = 4

    def __init__(self, database: WorkspaceDatabase, filesystem: FileSystem):
        self.database = database
        self.filesystem = filesystem

    def build(
        self,
        project_path: Path | None,
        max_context_tokens: int = 8_192,
        max_file_tokens: int | None = None,
    ) -> tuple[str, list[str]]:
        """Build a bounded system-message fragment using a model-dependent token budget."""
        if not project_path:
            return "", []

        root = self.filesystem.resolve(project_path)
        paths = self._granted_files(root)

        max_context_chars = max(1, max_context_tokens) * self.CHARS_PER_TOKEN
        effective_file_tokens = max_file_tokens or max(1, max_context_tokens // 2)
        max_file_chars = max(1, effective_file_tokens) * self.CHARS_PER_TOKEN

        chunks: list[str] = []
        included: list[str] = []
        used = 0

        for path in paths:
            if not self.filesystem.is_previewable(path):
                continue

            content = self.filesystem.read_text(path)
            relative = path.relative_to(root).as_posix()
            chunk = (
                f"\n\n--- Datei: {relative} ---\n"
                f"{content[:max_file_chars]}"
            )

            if used + len(chunk) > max_context_chars:
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
            if row["grant_type"] == "file":
                candidates = [target] if self.filesystem.is_file(target) else []
            elif not self.filesystem.is_directory(target):
                candidates = []
            else:
                try:
                    candidates = [
                        directory / name
                        for directory, _, names in self.filesystem.walk(target, FileIndexer.IGNORED_DIRECTORIES)
                        for name in names
                    ]
                except FileNotFoundError:
                    candidates = []
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
