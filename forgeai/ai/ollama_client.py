import json
import urllib.error
import urllib.request

from PySide6.QtCore import QThread, Signal

from forgeai.config import Config


class OllamaStreamWorker(QThread):
    token_received = Signal(str)
    completed = Signal()
    failed = Signal(str)

    def __init__(self, base_url: str, model: str, messages: list[dict]):
        super().__init__()
        self.base_url = OllamaClient.local_url(base_url)
        self.model, self.messages = model, messages

    def run(self) -> None:
        request = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=json.dumps({"model": self.model, "messages": self.messages, "stream": True}).encode(),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                for raw_line in response:
                    item = json.loads(raw_line)
                    if content := item.get("message", {}).get("content"):
                        self.token_received.emit(content)
            self.completed.emit()
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            self.failed.emit(f"Ollama-Verbindung fehlgeschlagen: {error}")


class OllamaClient:
    """Client for ForgeAI's fixed, local Ollama backend only."""

    @staticmethod
    def local_url(base_url: str) -> str:
        """Return the supported local endpoint or reject every other backend."""
        normalized = base_url.rstrip("/")
        if normalized != Config.LOCAL_OLLAMA_URL:
            raise ValueError(
                "ForgeAI akzeptiert ausschließlich die lokale Ollama-API unter "
                f"{Config.LOCAL_OLLAMA_URL}."
            )
        return Config.LOCAL_OLLAMA_URL

    def list_models(self, base_url: str) -> list[str]:
        try:
            with urllib.request.urlopen(f"{self.local_url(base_url)}/api/tags", timeout=3) as response:
                return [model["name"] for model in json.load(response).get("models", [])]
        except (urllib.error.URLError, json.JSONDecodeError, ValueError):
            return []

    def stream_chat(self, base_url: str, model: str, messages: list[dict]) -> OllamaStreamWorker:
        return OllamaStreamWorker(base_url, model, messages)
