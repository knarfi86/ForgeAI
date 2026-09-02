from forgeai.ai.ollama_provider import OllamaProvider


class FakeOllamaClient:
    def __init__(self):
        self.calls = []

    def generate(
        self,
        prompt: str,
        model: str,
        base_url: str | None = None,
        **kwargs,
    ):
        self.calls.append((prompt, model, base_url, kwargs))
        return "antwort"


def test_ollama_provider_forwards_generation():
    client = FakeOllamaClient()
    provider = OllamaProvider(
        client=client,
        base_url="http://localhost:11434",
    )

    result = provider.generate(
        prompt="plane",
        model="qwen3:8b",
    )

    assert result == "antwort"
    assert client.calls == [
        ("plane", "qwen3:8b", "http://localhost:11434", {})
    ]


def test_ollama_provider_uses_configured_base_url():
    client = FakeOllamaClient()
    provider = OllamaProvider(
        client=client,
        base_url="http://localhost:11434",
    )

    provider.generate(
        prompt="review",
        model="qwen2.5-coder:latest",
    )

    assert client.calls[0][2] == "http://localhost:11434"


def test_ollama_provider_forwards_router_kwargs():
    client = FakeOllamaClient()
    provider = OllamaProvider(client=client)

    result = provider.generate(
        prompt="test",
        model="qwen3:8b",
        temperature=0.2,
        num_ctx=16384,
    )

    assert result == "antwort"
    assert client.calls == [
        (
            "test",
            "qwen3:8b",
            "http://localhost:11434",
            {
                "temperature": 0.2,
                "num_ctx": 16384,
            },
        )
    ]
