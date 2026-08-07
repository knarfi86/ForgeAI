"""AI coding agent for controlled code suggestions."""

from pathlib import Path

from forgeai.ai.ollama_client import OllamaClient
from forgeai.core.ai_context import AIContextProvider
from forgeai.core.workspace_tools import WorkspaceTools


class CodeAgent:
    """
    Creates coding suggestions using Ollama.

    The agent only proposes changes.
    File modifications must go through WorkspaceTools.
    """

    def __init__(
        self,
        ollama: OllamaClient,
        context_provider: AIContextProvider,
        workspace_tools: WorkspaceTools,
    ):
        self.ollama = ollama
        self.context_provider = context_provider
        self.workspace_tools = workspace_tools

    def analyze_file(
        self,
        project_path: Path,
        file_path: Path,
        request: str,
        model: str | None = None,
    ) -> str:
        """Analyze a file and create a change proposal."""

        content = self.workspace_tools.read_file(file_path)

        context, _ = self.context_provider.build(project_path)

        prompt = f"""
Du bist ein lokaler Coding-Agent.

Regeln:
- Du schreibst keine Dateien direkt.
- Erstelle nur Vorschläge.
- Nutze nur den vorhandenen Kontext.

Projektkontext:
{context}

Datei:
{file_path}

Dateiinhalt:
```text
{content}