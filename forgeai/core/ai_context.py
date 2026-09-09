"""Controlled transfer of explicitly approved local files into chat context."""

from collections.abc import Callable
from pathlib import Path

from forgeai.core.filesystem import FileSystem
from forgeai.core.project_relevance import ProjectRelevance
from forgeai.core.workspace_database import WorkspaceDatabase


class AIContextProvider:
    """Reads only persisted, user-approved local project paths for Ollama prompts."""

    CHARS_PER_TOKEN = 4

    def __init__(
        self,
        database: WorkspaceDatabase,
        filesystem: FileSystem,
        accessible_files_provider: Callable[[], list[Path]],
    ):
        self.database = database
        self.filesystem = filesystem
        self.accessible_files_provider = accessible_files_provider
        self.relevance = ProjectRelevance(database, filesystem)

    def build(
        self,
        project_path: Path | None,
        max_context_tokens: int = 8_192,
        max_file_tokens: int | None = None,
        exclude_noise: bool = False,
        request: str | None = None,
    ) -> tuple[str, list[str]]:
        """Build a bounded system-message fragment using a model-dependent token budget."""
        if not project_path:
            return "", []

        root = self.filesystem.resolve(project_path)
        paths = self._granted_files(root)

        if request:
            relevant = self.relevance.find_relevant(
                root,
                request,
                max_results=len(paths),
            )
            relevance_rank = {
                relative_path: index
                for index, relative_path in enumerate(relevant)
            }
            paths.sort(
                key=lambda path: (
                    relevance_rank.get(
                        path.relative_to(root).as_posix(),
                        100_000,
                    ),
                    path.relative_to(root).as_posix().casefold(),
                )
            )

        max_context_chars = max(1, max_context_tokens) * self.CHARS_PER_TOKEN
        effective_file_tokens = max_file_tokens or max(1, max_context_tokens // 2)
        max_file_chars = max(1, effective_file_tokens) * self.CHARS_PER_TOKEN

        chunks: list[str] = []
        included: list[str] = []
        used = 0

        noise_directories = {
            ".git",
            ".venv",
            "venv",
            "__pycache__",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            "node_modules",
            "dist",
            "build",
        }

        for path in paths:
            if not self.filesystem.is_previewable(path):
                continue

            if exclude_noise:
                relative_parts = path.relative_to(root).parts
                if any(part in noise_directories for part in relative_parts):
                    continue

            content = self.filesystem.read_text(path)
            relative = path.relative_to(root).as_posix()
            chunk = (
                f"\n\n--- Datei: {relative} ---\n"
                f"{content[:max_file_chars]}"
            )

            if used + len(chunk) > max_context_chars:
                continue

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
        return [
            path
            for path in self.accessible_files_provider()
            if self.filesystem.is_file(path)
            and (
                path == root
                or root in path.parents
            )
        ]
