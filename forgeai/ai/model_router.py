"""Provider-agnostic model routing for ForgeAI."""

from __future__ import annotations

from typing import Any, Protocol

from .model_policy import (
    IdentityModelAdapter,
    ModelAdapter,
    ModelDecision,
    ModelProfile,
    ModelTarget,
    PrimaryModelPolicy,
)


MODEL_ROLES = (
    "meta_planner",
    "planner",
    "reviewer",
    "coder",
    "repairer",
    "advisor",
)


class ModelProvider(Protocol):
    """Minimal interface required by ModelRouter."""

    def generate(self, prompt: str, model: str, **kwargs: Any) -> str:
        """Generate a non-streaming model response."""
        ...


class ModelRouter:
    """Resolve ForgeAI roles while preferring one coherent primary model."""

    def __init__(
        self,
        providers: dict[str, ModelProvider] | None = None,
        routes: dict[str, ModelTarget] | None = None,
        policy: PrimaryModelPolicy | None = None,
    ) -> None:
        self._providers = dict(providers or {})
        self._routes = dict(routes or {})
        self._policy = policy
        self._adapters: dict[str, ModelAdapter] = {
            "identity": IdentityModelAdapter(),
        }
        self._legacy_decisions: list[ModelDecision] = []

    def register_provider(self, name: str, provider: ModelProvider) -> None:
        normalized = name.strip().lower()
        if not normalized:
            raise ValueError("Providername darf nicht leer sein.")
        self._providers[normalized] = provider

    def register_adapter(self, adapter: ModelAdapter) -> None:
        adapter_id = str(adapter.adapter_id).strip().lower()
        if not adapter_id:
            raise ValueError("adapter_id darf nicht leer sein.")
        self._adapters[adapter_id] = adapter

    def set_primary(
        self,
        provider: str,
        model: str,
        *,
        adapter_id: str = "identity",
        native_context: int | None = None,
        notes: str = "",
    ) -> None:
        profile = ModelProfile(
            provider=provider,
            model=model,
            adapter_id=adapter_id,
            native_context=native_context,
            notes=notes,
        )
        if self._policy is None:
            self._policy = PrimaryModelPolicy(profile)
        else:
            self._policy.set_primary(profile)

    def register_specialist(
        self,
        role: str,
        provider: str,
        model: str,
        *,
        adapter_id: str = "identity",
        native_context: int | None = None,
        notes: str = "",
    ) -> None:
        self._validate_role(role)
        if self._policy is None:
            raise RuntimeError("Vor einem Spezialisten muss ein Primärmodell konfiguriert sein.")
        profile = ModelProfile(
            provider=provider,
            model=model,
            adapter_id=adapter_id,
            preferred_roles=(role,),
            specialist=True,
            native_context=native_context,
            notes=notes,
        )
        self._policy.register_specialist(role, profile)

    def set_route(self, role: str, provider: str, model: str) -> None:
        """Legacy/manual override kept for compatibility and explicit routing."""
        normalized_role = self._validate_role(role)
        target = ModelTarget(provider=provider, model=model)
        self._routes[normalized_role] = target

    def resolve_decision(
        self,
        role: str,
        *,
        specialist_required: bool = False,
    ) -> ModelDecision:
        normalized_role = self._validate_role(role)

        target = self._routes.get(normalized_role)
        if target is not None:
            decision = ModelDecision(
                role=normalized_role,
                target=target,
                source="explicit",
                reason="Explizite Legacy-/Benutzerroute überschreibt die Primärmodell-Policy.",
                specialist_required=specialist_required,
            )
            self._legacy_decisions.append(decision)
            return decision

        if self._policy is None:
            raise ValueError(
                f"Für die Modellrolle {normalized_role!r} ist kein Modell konfiguriert; weder explizite Route noch Primärmodell vorhanden."
            )

        return self._policy.resolve(
            normalized_role,
            specialist_required=specialist_required,
        )

    def resolve(self, role: str, *, specialist_required: bool = False) -> ModelTarget:
        return self.resolve_decision(
            role,
            specialist_required=specialist_required,
        ).target

    def provider_for(self, role: str, *, specialist_required: bool = False) -> ModelProvider:
        target = self.resolve(role, specialist_required=specialist_required)
        return self._provider_for_target(target)

    def generate(
        self,
        role: str,
        prompt: str,
        *,
        specialist_required: bool = False,
        **kwargs: Any,
    ) -> str:
        decision = self.resolve_decision(
            role,
            specialist_required=specialist_required,
        )
        target = decision.target
        provider = self._provider_for_target(target)
        profile = self._profile_for_target(target)
        adapter = self._adapters.get(profile.adapter_id)
        if adapter is None:
            raise RuntimeError(
                f"Der ModelAdapter {profile.adapter_id!r} ist nicht registriert."
            )

        adapted_prompt = adapter.adapt_prompt(
            role=decision.role,
            prompt=prompt,
            profile=profile,
        )
        adapted_options = adapter.adapt_options(
            role=decision.role,
            options=kwargs,
            profile=profile,
        )

        try:
            return provider.generate(
                prompt=adapted_prompt,
                model=target.model,
                **adapted_options,
            )
        finally:
            if specialist_required and self._policy is not None:
                self._policy.return_to_primary()

    def routes(self) -> dict[str, ModelTarget]:
        return dict(self._routes)

    def providers(self) -> tuple[str, ...]:
        return tuple(sorted(self._providers))

    def primary_target(self) -> ModelTarget | None:
        return self._policy.primary_target if self._policy is not None else None

    def active_target(self) -> ModelTarget | None:
        return self._policy.active_target if self._policy is not None else None

    def decisions(self) -> tuple[ModelDecision, ...]:
        policy_decisions = self._policy.decisions() if self._policy is not None else ()
        return tuple(self._legacy_decisions) + policy_decisions

    def _profile_for_target(self, target: ModelTarget) -> ModelProfile:
        if self._policy is None:
            return ModelProfile(provider=target.provider, model=target.model)
        return self._policy.profile_for(target)

    def _provider_for_target(self, target: ModelTarget) -> ModelProvider:
        provider = self._providers.get(target.provider)
        if provider is None:
            raise RuntimeError(
                f"Der konfigurierte Provider {target.provider!r} ist nicht registriert."
            )
        return provider

    @staticmethod
    def _validate_role(role: str) -> str:
        normalized_role = role.strip().lower()
        if normalized_role not in MODEL_ROLES:
            raise ValueError(f"Unbekannte Modellrolle: {role!r}.")
        return normalized_role
