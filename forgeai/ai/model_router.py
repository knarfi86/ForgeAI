"""Provider-agnostic model routing for ForgeAI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


MODEL_ROLES = (
    "meta_planner",
    "planner",
    "reviewer",
    "coder",
    "repairer",
    "advisor",
)


@dataclass(frozen=True)
class ModelTarget:
    """Selected provider/model pair for an agent role."""

    provider: str
    model: str


class ModelProvider(Protocol):
    """Minimal interface required by ModelRouter."""

    def generate(self, prompt: str, model: str, **kwargs: Any) -> str:
        """Generate a non-streaming model response."""
        ...


class ModelRouter:
    """Resolve ForgeAI agent roles to configured model providers."""

    def __init__(
        self,
        providers: dict[str, ModelProvider] | None = None,
        routes: dict[str, ModelTarget] | None = None,
    ) -> None:
        self._providers = dict(providers or {})
        self._routes = dict(routes or {})

    def register_provider(self, name: str, provider: ModelProvider) -> None:
        normalized = name.strip().lower()
        if not normalized:
            raise ValueError("Providername darf nicht leer sein.")
        self._providers[normalized] = provider

    def set_route(self, role: str, provider: str, model: str) -> None:
        normalized_role = role.strip().lower()
        normalized_provider = provider.strip().lower()
        normalized_model = model.strip()

        if normalized_role not in MODEL_ROLES:
            raise ValueError(f"Unbekannte Modellrolle: {role!r}.")
        if not normalized_provider:
            raise ValueError("Providername darf nicht leer sein.")
        if not normalized_model:
            raise ValueError("Modellname darf nicht leer sein.")

        self._routes[normalized_role] = ModelTarget(
            provider=normalized_provider,
            model=normalized_model,
        )

    def resolve(self, role: str) -> ModelTarget:
        normalized_role = role.strip().lower()

        if normalized_role not in MODEL_ROLES:
            raise ValueError(f"Unbekannte Modellrolle: {role!r}.")

        target = self._routes.get(normalized_role)
        if target is None:
            raise ValueError(
                f"Für die Modellrolle {normalized_role!r} ist kein Modell konfiguriert."
            )

        return target

    def provider_for(self, role: str) -> ModelProvider:
        target = self.resolve(role)
        provider = self._providers.get(target.provider)

        if provider is None:
            raise RuntimeError(
                f"Der konfigurierte Provider {target.provider!r} ist nicht registriert."
            )

        return provider

    def generate(self, role: str, prompt: str, **kwargs: Any) -> str:
        target = self.resolve(role)
        provider = self.provider_for(role)
        return provider.generate(
            prompt=prompt,
            model=target.model,
            **kwargs,
        )

    def routes(self) -> dict[str, ModelTarget]:
        return dict(self._routes)

    def providers(self) -> tuple[str, ...]:
        return tuple(sorted(self._providers))
