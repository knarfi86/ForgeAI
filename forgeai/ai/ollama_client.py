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
        """Return detected GPU and system-memory information."""
        info = {
            "gpu_vram_total_bytes": None,
            "system_ram_total_bytes": None,
            "system_ram_available_bytes": None,
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

            totals = []

            for line in result.stdout.splitlines():
                line = line.strip()
                if line.isdigit():
                    totals.append(int(line) * 1024 * 1024)

            if totals:
                info["gpu_vram_total_bytes"] = max(totals)

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
                info["system_ram_total_bytes"] = int(status.ullTotalPhys)
                info["system_ram_available_bytes"] = int(status.ullAvailPhys)

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
                try:
                    return int(model.get("size"))
                except (TypeError, ValueError):
                    return None

        return None

    def recommend_context_length(
        self,
        base_url: str,
        model_name: str,
        native_context: int | None,
    ) -> dict:
        """Choose a conservative context size from hardware and model requirements."""
        hardware = self.get_hardware_info()

        vram_total = hardware.get("gpu_vram_total_bytes")
        ram_total = hardware.get("system_ram_total_bytes")
        ram_available = hardware.get("system_ram_available_bytes")
        model_size = self.get_model_size(base_url, model_name)

        native = int(native_context or 16_384)

        # Context sizes are powers/standard boundaries supported by Ollama
        # and intentionally conservative for local desktop hardware.
        context_levels = (
            8_192,
            16_384,
            32_768,
            49_152,
            65_536,
            131_072,
            262_144,
        )

        candidates = [value for value in context_levels if value <= native]
        if not candidates:
            candidates = [8_192]

        recommended = candidates[0]
        reason = "safe minimum"

        if vram_total and model_size:
            # Do not assume that every byte of VRAM is available for the model.
            # Keep 15% as a desktop/driver/runtime safety reserve.
            usable_vram = int(vram_total * 0.85)
            ratio = model_size / max(usable_vram, 1)

            if ratio <= 0.50:
                recommended = min(native, 131_072)
                reason = "model leaves substantial VRAM headroom"
            elif ratio <= 0.75:
                recommended = min(native, 65_536)
                reason = "model fits with reasonable VRAM headroom"
            elif ratio <= 1.00:
                recommended = min(native, 32_768)
                reason = "model approximately fits within usable VRAM"
            elif ratio <= 1.40:
                recommended = min(native, 16_384)
                reason = "model requires CPU/GPU offload"
            else:
                recommended = min(native, 8_192)
                reason = "model significantly exceeds usable VRAM"

        # RAM is relevant when the model is larger than the practical GPU
        # budget and therefore needs CPU-side memory.
        if model_size and ram_available:
            ram_safety_reserve = 6 * 1024**3
            usable_ram = max(0, ram_available - ram_safety_reserve)

            if model_size > usable_ram and recommended > 8_192:
                recommended = 8_192
                reason = "model exceeds safe available system RAM"

        # On larger-memory systems, allow more context when the model is
        # substantially smaller than the available resources.
        if model_size and ram_total and vram_total:
            combined_memory = int(vram_total * 0.85) + int(ram_total * 0.70)

            if model_size < combined_memory * 0.35:
                recommended = min(native, max(recommended, 131_072))
                reason = "model is small relative to combined memory"

        recommended = max(
            8_192,
            min(int(recommended), native),
        )

        return {
            "context_length": native,
            "recommended_context": recommended,
            "gpu_vram_total_bytes": vram_total,
            "system_ram_total_bytes": ram_total,
            "system_ram_available_bytes": ram_available,
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
