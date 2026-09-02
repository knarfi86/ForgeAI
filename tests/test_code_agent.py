from pathlib import Path
from unittest.mock import Mock

from forgeai.ai.code_agent import CodeAgent


def test_analyze_file_reads_file_builds_context_and_calls_ollama():
    ollama = Mock()
    context_provider = Mock()
    workspace_tools = Mock()

    workspace_tools.read_file.return_value = "print('hello')"
    context_provider.build.return_value = (
        "--- Datei: main.py ---\nprint('hello')",
        ["main.py"],
    )
    ollama.generate.return_value = "Vorschlag"

    agent = CodeAgent(
        ollama=ollama,
        context_provider=context_provider,
        workspace_tools=workspace_tools,
    )

    project = Path("C:/project")
    file_path = project / "main.py"

    result = agent.analyze_file(
        project,
        file_path,
        "Verbessere den Code",
        model="test-model",
    )

    assert result == "Vorschlag"

    workspace_tools.read_file.assert_called_once_with(file_path)
    context_provider.build.assert_called_once_with(project)

    ollama.generate.assert_called_once()

    prompt = ollama.generate.call_args.kwargs["prompt"]

    assert "Verbessere den Code" in prompt
    assert "print('hello')" in prompt
    assert "test-model" not in prompt


def test_analyze_file_passes_model_to_ollama():
    ollama = Mock()
    context_provider = Mock()
    workspace_tools = Mock()

    workspace_tools.read_file.return_value = "content"
    context_provider.build.return_value = ("context", [])
    ollama.generate.return_value = "response"

    agent = CodeAgent(
        ollama=ollama,
        context_provider=context_provider,
        workspace_tools=workspace_tools,
    )

    agent.analyze_file(
        Path("C:/project"),
        Path("C:/project/main.py"),
        "request",
        model="qwen-test",
    )

    assert ollama.generate.call_args.kwargs["model"] == "qwen-test"


def test_analyze_file_returns_fallback_when_ollama_returns_none():
    ollama = Mock()
    context_provider = Mock()
    workspace_tools = Mock()

    workspace_tools.read_file.return_value = "content"
    context_provider.build.return_value = ("context", [])
    ollama.generate.return_value = None

    agent = CodeAgent(
        ollama=ollama,
        context_provider=context_provider,
        workspace_tools=workspace_tools,
    )

    result = agent.analyze_file(
        Path("C:/project"),
        Path("C:/project/main.py"),
        "request",
    )

    assert result == "Ollama hat keine Antwort zurückgegeben."


def test_code_agent_does_not_write_files_directly():
    ollama = Mock()
    context_provider = Mock()
    workspace_tools = Mock()

    workspace_tools.read_file.return_value = "content"
    context_provider.build.return_value = ("context", [])
    ollama.generate.return_value = "response"

    agent = CodeAgent(
        ollama=ollama,
        context_provider=context_provider,
        workspace_tools=workspace_tools,
    )

    agent.analyze_file(
        Path("C:/project"),
        Path("C:/project/main.py"),
        "request",
    )

    assert not hasattr(agent, "write_file")
    assert not hasattr(agent, "apply")
    workspace_tools.apply.assert_not_called()
