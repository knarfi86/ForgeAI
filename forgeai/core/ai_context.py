"""Controlled transfer of explicitly approved local files into chat context."""

from collections.abc import Callable
from pathlib import Path

from forgeai.core.filesystem import FileSystem
from forgeai.core.project_relevance import ProjectRelevance
from forgeai.core.workspace_database import WorkspaceDatabase


class AIContextProvider:
    """Build bounded Ollama context from project metadata and approved file contents."""

    CHARS_PER_TOKEN = 4

    def __init__(
        self,
        database: WorkspaceDatabase,
        filesystem: FileSystem,
        accessible_files_provider: Callable[[], list[Path]],
        structure_provider: Callable[[Path], dict] | None = None,
    ):
        self.database = database
        self.filesystem = filesystem
        self.accessible_files_provider = accessible_files_provider
        self.structure_provider = structure_provider
        self.relevance = ProjectRelevance(database, filesystem)

    def build(
        self,
        project_path: Path | None,
        max_context_tokens: int = 8_192,
        max_file_tokens: int | None = None,
        exclude_noise: bool = False,
        request: str | None = None,
        include_structure: bool = False,
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
        effective_file_tokens = (
            max_file_tokens or max(1, max_context_tokens // 2)
        )
        max_file_chars = max(1, effective_file_tokens) * self.CHARS_PER_TOKEN

        structure_context = ""
        used = 0

        if include_structure and self.structure_provider is not None:
            structure = self.structure_provider(root)
            structure_text = self._format_structure(structure)

            max_structure_chars = min(
                max_context_chars,
                max(4_000, max_context_chars // 4),
            )
            structure_text = structure_text[:max_structure_chars]

            structure_context = (
                "--- PROJEKTSTRUKTUR (AUTOMATISCH ERMITTELTE METADATEN) ---\n"
                "Die folgende Struktur wurde lokal aus Projektmetadaten ermittelt. "
                "Sie enth?lt keinen automatisch freigegebenen Dateiinhalt.\n"
                f"{structure_text}"
            )
            used = len(structure_context)

        file_chunks: list[str] = []
        included: list[str] = []

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

            file_chunks.append(chunk)
            included.append(relative)
            used += len(chunk)

        if not structure_context and not file_chunks:
            return "", []

        parts: list[str] = []

        if structure_context:
            parts.append(structure_context)

        if file_chunks:
            parts.append(
                "--- FREIGEGEBENE DATEI-INHALTE ---\n"
                "Die folgenden Datei-Inhalte wurden vom Benutzer ausdr?cklich "
                "f?r den lokalen KI-Kontext freigegeben. "
                "Nur diese Datei-Inhalte d?rfen als tats?chlich gelesener Inhalt "
                "behandelt werden. Die Projektstruktur oben ist davon getrennt."
            )
            parts.extend(file_chunks)

        return "\n\n".join(parts), included

    def _format_structure(self, structure: dict) -> str:
        import json

        return json.dumps(
            structure,
            ensure_ascii=False,
            indent=2,
        )

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
