import json
import urllib.error
from io import BytesIO
from unittest.mock import Mock

import pytest

from forgeai.ai.ollama_client import OllamaClient
from forgeai.config import Config


def test_local_url_accepts_only_configured_local_endpoint():
    assert (
        OllamaClient.local_url(Config.LOCAL_OLLAMA_URL)
        == Config.LOCAL_OLLAMA_URL
    )

    assert (
        OllamaClient.local_url(Config.LOCAL_OLLAMA_URL + "/")
        == Config.LOCAL_OLLAMA_URL
    )


def test_local_url_rejects_other_backend():
    with pytest.raises(ValueError, match="ausschließlich die lokale Ollama-API"):
        OllamaClient.local_url("http://example.com")


def test_list_models_returns_model_names(monkeypatch):
    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.read = Mock(
        return_value=json.dumps(
            {
                "models": [
                    {"name": "model-a"},
                    {"name": "model-b"},
                ]
            }
        ).encode("utf-8")
    )

    monkeypatch.setattr(
        "urllib.request.urlopen",
        Mock(return_value=response),
    )

    client = OllamaClient()

    assert client.list_models(Config.LOCAL_OLLAMA_URL) == [
        "model-a",
        "model-b",
    ]


def test_list_models_returns_empty_list_on_connection_error(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        Mock(side_effect=urllib.error.URLError("offline")),
    )

    client = OllamaClient()

    assert client.list_models(Config.LOCAL_OLLAMA_URL) == []


def test_get_model_size_returns_matching_size(monkeypatch):
    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.read = Mock(
        return_value=json.dumps(
            {
                "models": [
                    {"name": "model-a", "size": 12345},
                    {"name": "model-b", "size": 999},
                ]
            }
        ).encode("utf-8")
    )

    monkeypatch.setattr(
        "urllib.request.urlopen",
        Mock(return_value=response),
    )

    client = OllamaClient()

    assert client.get_model_size(
        Config.LOCAL_OLLAMA_URL,
        "model-a",
    ) == 12345


def test_get_model_size_returns_none_for_unknown_model(monkeypatch):
    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.read = Mock(
        return_value=json.dumps(
            {"models": [{"name": "model-a", "size": 12345}]}
        ).encode("utf-8")
    )

    monkeypatch.setattr(
        "urllib.request.urlopen",
        Mock(return_value=response),
    )

    client = OllamaClient()

    assert client.get_model_size(
        Config.LOCAL_OLLAMA_URL,
        "unknown",
    ) is None


def test_get_context_length_reads_model_info(monkeypatch):
    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.read = Mock(
        return_value=json.dumps(
            {
                "model_info": {
                    "some.arch.context_length": 131072,
                }
            }
        ).encode("utf-8")
    )

    monkeypatch.setattr(
        "urllib.request.urlopen",
        Mock(return_value=response),
    )

    client = OllamaClient()

    assert client.get_context_length(
        Config.LOCAL_OLLAMA_URL,
        "model-a",
    ) == 131072


def test_get_context_length_returns_none_when_unavailable(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        Mock(side_effect=urllib.error.URLError("offline")),
    )

    client = OllamaClient()

    assert client.get_context_length(
        Config.LOCAL_OLLAMA_URL,
        "model-a",
    ) is None


def test_recommend_context_length_has_conservative_default(monkeypatch):
    client = OllamaClient()

    monkeypatch.setattr(
        client,
        "get_hardware_info",
        Mock(
            return_value={
                "gpu_vram_total_bytes": None,
                "system_ram_total_bytes": None,
                "system_ram_available_bytes": None,
            }
        ),
    )

    monkeypatch.setattr(
        client,
        "get_model_size",
        Mock(return_value=None),
    )

    result = client.recommend_context_length(
        Config.LOCAL_OLLAMA_URL,
        "model-a",
        131072,
    )

    assert result["context_length"] == 131072
    assert result["recommended_context"] == 8192


def test_stream_chat_passes_num_ctx_to_worker():
    client = OllamaClient()

    worker = client.stream_chat(
        Config.LOCAL_OLLAMA_URL,
        "model-a",
        [{"role": "user", "content": "hello"}],
        num_ctx=32768,
    )

    assert worker.num_ctx == 32768
    assert worker.model == "model-a"


def test_generate_requires_model():
    client = OllamaClient()

    with pytest.raises(ValueError, match="Kein Ollama-Modell"):
        client.generate("hello")
