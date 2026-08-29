import json
import urllib.error
import urllib.request
import subprocess

from PySide6.QtCore import QThread, Signal

from forgeai.config import Config


class OllamaStreamWorker(QThread):
    token_received = Signal(str)
    completed = Signal()
    failed = Signal(str)

    def __init__(self, base_url: str, model: str, messages: list[dict], response_format: dict | str | None = None):
        super().__init__()
        self.base_url = base_url
        self.model, self.messages = model, messages
        self.response_format = response_format
        self.content = ""

    def run(self) -> None:
        payload = {"model": self.model, "messages": self.messages, "stream": True}
        if self.response_format is not None:
            payload["format"] = self.response_format
        if getattr(self, "num_ctx", None) is not None:
            payload["options"] = {"num_ctx": int(self.num_ctx)}

        request = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                for raw_line in response:
                    item = json.loads(raw_line)
                    content = item.get("message", {}).get("content", "")
                    if content:
                        self.content += content
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

    def load_model(self, base_url: str, model_name: str) -> dict:
        try:
            with urllib.request.urlopen(f"{self.local_url(base_url)}/api/models/{model_name}", timeout=3) as response:
                return json.load(response)
        except (urllib.error.URLError, json.JSONDecodeError, ValueError):
            return {}

    def get_hardware_info(self) -> dict:
        """Return detected NVIDIA VRAM and system RAM in bytes."""
        info = {
            "gpu_vram_bytes": None,
            "system_ram_bytes": None,
        }

        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=memory.total",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=3,
                check=True,
            )
            values = []
            for line in result.stdout.splitlines():
                line = line.strip()
                if line.isdigit():
                    values.append(int(line) * 1024 * 1024)
            if values:
                info["gpu_vram_bytes"] = max(values)
        except (OSError, subprocess.SubprocessError, ValueError):
            pass

        try:
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = MEMORYSTATUSEX()
            status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                info["system_ram_bytes"] = int(status.ullTotalPhys)
        except (AttributeError, OSError, TypeError):
            pass

        return info

    def get_model_size(self, base_url: str, model_name: str) -> int | None:
        """Return the installed model size in bytes when Ollama reports it."""
        try:
            with urllib.request.urlopen(
                f"{self.local_url(base_url)}/api/tags",
                timeout=5,
            ) as response:
                data = json.load(response)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
            return None

        for model in data.get("models", []):
            if model.get("name") == model_name:
                size = model.get("size")
                try:
                    return int(size) if size is not None else None
                except (TypeError, ValueError):
                    return None

        return None

    def recommend_context_length(
        self,
        base_url: str,
        model_name: str,
        native_context: int | None,
    ) -> dict:
        """Calculate a conservative context size from model size and detected hardware."""
        hardware = self.get_hardware_info()
        vram = hardware.get("gpu_vram_bytes")
        ram = hardware.get("system_ram_bytes")
        model_size = self.get_model_size(base_url, model_name)

        if native_context is None:
            native_context = 32_768

        recommended = min(native_context, 32_768)
        reason = "conservative default"

        if vram and model_size:
            ratio = model_size / vram

            if ratio <= 0.60:
                recommended = min(native_context, 65_536)
                reason = "model comfortably fits in detected VRAM"
            elif ratio <= 0.85:
                recommended = min(native_context, 49_152)
                reason = "model fits with limited VRAM headroom"
            elif ratio <= 1.05:
                recommended = min(native_context, 32_768)
                reason = "model approximately fills detected VRAM"
            elif ratio <= 1.60:
                recommended = min(native_context, 16_384)
                reason = "model exceeds VRAM; conservative CPU/GPU offload context"
            else:
                recommended = min(native_context, 8_192)
                reason = "model greatly exceeds VRAM; safe starting context"

        # A very small RAM system should not receive an aggressive context
        # when the model already needs CPU/GPU offloading.
        if ram and model_size and model_size > ram and recommended > 8_192:
            recommended = 8_192
            reason = "model exceeds system RAM; reduced context"

        # Keep the value positive and reasonable.
        recommended = max(8_192, int(recommended))

        return {
            "context_length": int(native_context),
            "recommended_context": recommended,
            "gpu_vram_bytes": vram,
            "system_ram_bytes": ram,
            "model_size_bytes": model_size,
            "reason": reason,
        }

    def get_context_length(self, base_url: str, model_name: str) -> int | None:
        """Return the context length advertised by Ollama for a model."""
        try:
            request = urllib.request.Request(
                f"{self.local_url(base_url)}/api/show",
                data=json.dumps({"model": model_name}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            with urllib.request.urlopen(request, timeout=5) as response:
                data = json.load(response)

        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
            return None

        model_info = data.get("model_info", {})
        if not isinstance(model_info, dict):
            return None

        for key, value in model_info.items():
            if str(key).lower().endswith(".context_length"):
                try:
                    return int(value)
                except (TypeError, ValueError):
                    return None

        return None


    def stream_chat(
        self,
        base_url: str,
        model: str,
        messages: list[dict],
        response_format: dict | str | None = None,
        num_ctx: int | None = None,
    ) -> OllamaStreamWorker:
        worker = OllamaStreamWorker(base_url, model, messages, response_format)

        if num_ctx is not None:
            worker.num_ctx = int(num_ctx)

        return worker

    def generate(
        self,
        prompt: str,
        model: str | None = None,
        base_url: str | None = None,
    ) -> str:
        if not model:
            raise ValueError("Kein Ollama-Modell angegeben.")

        target_url = base_url if base_url is not None else Config.LOCAL_OLLAMA_URL
        request = urllib.request.Request(
            f"{self.local_url(target_url)}/api/chat",
            data=json.dumps(
                {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                }
            ).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                data = json.load(response)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            raise RuntimeError(
                f"Ollama-Verbindung fehlgeschlagen: {error}"
            ) from error

        return data.get("message", {}).get("content", "").strip()

    def connect(self, base_url: str) -> None:
        """Establish a connection to the Ollama backend."""
        try:
            response = urllib.request.urlopen(f"{self.local_url(base_url)}", timeout=3)
            if response.getcode() == 200:
                self.logger.info("Ollama-Verbindung erfolgreich hergestellt.")
            else:
                raise ConnectionError(f"Ungültige Antwort: {response.getcode()}")
        except urllib.error.URLError as error:
            self.logger.error(f"Fehler beim Herstellen der Ollama-Verbindung: {error}")

    def analyze_project(self, base_url: str, project_path: str) -> dict:
        try:
            with urllib.request.urlopen(f"{self.local_url(base_url)}/api/analyze?path={project_path}", timeout=30) as response:
                return json.load(response)
        except (urllib.error.URLError, json.JSONDecodeError, ValueError):
            return {}
