from forgeai.ai.model_router import MODEL_ROLES, ModelRouter, ModelTarget


class FakeProvider:
    def __init__(self):
        self.calls = []

    def generate(self, prompt: str, model: str, **kwargs):
        self.calls.append((prompt, model, kwargs))
        return f"{model}: {prompt}"


def test_model_roles_are_complete():
    assert MODEL_ROLES == (
        "meta_planner",
        "planner",
        "reviewer",
        "coder",
        "repairer",
        "advisor",
    )


def test_set_and_resolve_route():
    router = ModelRouter()

    router.set_route("planner", "ollama", "qwen2.5-coder:latest")

    assert router.resolve("planner") == ModelTarget(
        provider="ollama",
        model="qwen2.5-coder:latest",
    )


def test_role_and_provider_names_are_normalized():
    router = ModelRouter()

    router.set_route(" PLANNER ", " Ollama ", "qwen3:8b")

    assert router.resolve("planner") == ModelTarget(
        provider="ollama",
        model="qwen3:8b",
    )


def test_generate_uses_selected_provider_and_model():
    provider = FakeProvider()
    router = ModelRouter(providers={"ollama": provider})

    router.set_route("coder", "ollama", "qwen2.5-coder:latest")

    result = router.generate("coder", "teste", temperature=0.2)

    assert result == "qwen2.5-coder:latest: teste"
    assert provider.calls == [
        ("teste", "qwen2.5-coder:latest", {"temperature": 0.2})
    ]


def test_provider_for_returns_registered_provider():
    provider = FakeProvider()
    router = ModelRouter(providers={"openai": provider})

    router.set_route("meta_planner", "openai", "gpt")

    assert router.provider_for("meta_planner") is provider


def test_unknown_role_is_rejected():
    router = ModelRouter()

    try:
        router.set_route("unknown", "ollama", "model")
    except ValueError as error:
        assert "Unbekannte Modellrolle" in str(error)
    else:
        raise AssertionError("Expected ValueError")


def test_missing_route_is_rejected():
    router = ModelRouter()

    try:
        router.resolve("reviewer")
    except ValueError as error:
        assert "kein Modell konfiguriert" in str(error)
    else:
        raise AssertionError("Expected ValueError")


def test_missing_provider_is_rejected():
    router = ModelRouter()
    router.set_route("repairer", "ollama", "qwen3:8b")

    try:
        router.generate("repairer", "repariere")
    except RuntimeError as error:
        assert "nicht registriert" in str(error)
    else:
        raise AssertionError("Expected RuntimeError")


def test_empty_provider_and_model_are_rejected():
    router = ModelRouter()

    for provider, model in [
        ("", "model"),
        ("ollama", ""),
    ]:
        try:
            router.set_route("coder", provider, model)
        except ValueError:
            pass
        else:
            raise AssertionError("Expected ValueError")


def test_routes_returns_copy():
    router = ModelRouter()
    router.set_route("planner", "ollama", "qwen3:8b")

    routes = router.routes()
    routes["planner"] = ModelTarget("openai", "gpt")

    assert router.resolve("planner") == ModelTarget(
        provider="ollama",
        model="qwen3:8b",
    )
