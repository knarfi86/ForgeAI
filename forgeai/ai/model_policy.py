"""Primary-model policy and model-adapter contracts for ForgeAI.

The core policy deliberately prefers one primary model for coherent agent runs.
Specialists are opt-in and may only be used when a caller explicitly declares
that a specialist is required. Forge contracts stay model-independent; adapters
may tune prompts/options, but they must not redefine success, evidence, or safety.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class ModelTarget:
    """Provider/model pair selected for an LLM call."""

    provider: str
    model: str

    def __post_init__(self) -> None:
        provider = self.provider.strip().lower()
        model = self.model.strip()
        if not provider:
            raise ValueError("Providername darf nicht leer sein.")
        if not model:
            raise ValueError("Modellname darf nicht leer sein.")
        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "model", model)


@dataclass(frozen=True)
class ModelProfile:
    """Stable model metadata used by routing and future benchmarking."""

    provider: str
    model: str
    adapter_id: str = "identity"
    preferred_roles: tuple[str, ...] = ()
    specialist: bool = False
    native_context: int | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        target = ModelTarget(self.provider, self.model)
        adapter_id = self.adapter_id.strip().lower()
        if not adapter_id:
            raise ValueError("adapter_id darf nicht leer sein.")
        if self.native_context is not None and int(self.native_context) <= 0:
            raise ValueError("native_context muss positiv sein.")
        roles = tuple(dict.fromkeys(role.strip().lower() for role in self.preferred_roles if role.strip()))
        object.__setattr__(self, "provider", target.provider)
        object.__setattr__(self, "model", target.model)
        object.__setattr__(self, "adapter_id", adapter_id)
        object.__setattr__(self, "preferred_roles", roles)
        if self.native_context is not None:
            object.__setattr__(self, "native_context", int(self.native_context))

    @property
    def target(self) -> ModelTarget:
        return ModelTarget(self.provider, self.model)


@dataclass(frozen=True)
class ModelDecision:
    """Explainable result of one model-selection decision."""

    role: str
    target: ModelTarget
    source: str
    reason: str
    specialist_required: bool = False


class ModelAdapter(Protocol):
    """Model-specific tuning that may not change Forge's core contracts."""

    adapter_id: str

    def adapt_prompt(self, *, role: str, prompt: str, profile: ModelProfile) -> str:
        ...

    def adapt_options(
        self,
        *,
        role: str,
        options: dict[str, Any],
        profile: ModelProfile,
    ) -> dict[str, Any]:
        ...


class IdentityModelAdapter:
    """Default adapter: preserve the Forge contract exactly as supplied."""

    adapter_id = "identity"

    def adapt_prompt(self, *, role: str, prompt: str, profile: ModelProfile) -> str:
        return prompt

    def adapt_options(
        self,
        *,
        role: str,
        options: dict[str, Any],
        profile: ModelProfile,
    ) -> dict[str, Any]:
        return dict(options)


class PrimaryModelPolicy:
    """Prefer one primary model and use specialists only on explicit demand."""

    def __init__(self, primary: ModelProfile) -> None:
        self._primary = primary
        self._profiles: dict[ModelTarget, ModelProfile] = {primary.target: primary}
        self._specialists: dict[str, ModelTarget] = {}
        self._history: list[ModelDecision] = []
        self._active_target = primary.target

    @property
    def primary_profile(self) -> ModelProfile:
        return self._primary

    @property
    def primary_target(self) -> ModelTarget:
        return self._primary.target

    @property
    def active_target(self) -> ModelTarget:
        return self._active_target

    def set_primary(self, profile: ModelProfile) -> None:
        self._primary = profile
        self._profiles[profile.target] = profile
        self._active_target = profile.target

    def register_profile(self, profile: ModelProfile) -> None:
        self._profiles[profile.target] = profile

    def profile_for(self, target: ModelTarget) -> ModelProfile:
        return self._profiles.get(
            target,
            ModelProfile(provider=target.provider, model=target.model),
        )

    def register_specialist(self, role: str, profile: ModelProfile) -> None:
        normalized_role = role.strip().lower()
        if not normalized_role:
            raise ValueError("Modellrolle darf nicht leer sein.")
        if not profile.specialist:
            profile = ModelProfile(
                provider=profile.provider,
                model=profile.model,
                adapter_id=profile.adapter_id,
                preferred_roles=profile.preferred_roles,
                specialist=True,
                native_context=profile.native_context,
                notes=profile.notes,
            )
        self._profiles[profile.target] = profile
        self._specialists[normalized_role] = profile.target

    def resolve(self, role: str, *, specialist_required: bool = False) -> ModelDecision:
        normalized_role = role.strip().lower()
        if not normalized_role:
            raise ValueError("Modellrolle darf nicht leer sein.")

        if specialist_required:
            target = self._specialists.get(normalized_role)
            if target is None:
                raise LookupError(
                    f"Für die Modellrolle {normalized_role!r} ist kein freigegebener Spezialist registriert."
                )
            decision = ModelDecision(
                role=normalized_role,
                target=target,
                source="specialist",
                reason="Spezialist wurde für diese Aufgabe explizit angefordert.",
                specialist_required=True,
            )
        else:
            decision = ModelDecision(
                role=normalized_role,
                target=self.primary_target,
                source="primary",
                reason="Primärmodell wird bevorzugt, um Modellwechsel und Kontextverluste zu vermeiden.",
                specialist_required=False,
            )

        self._active_target = decision.target
        self._history.append(decision)
        return decision

    def return_to_primary(self) -> None:
        self._active_target = self.primary_target

    def decisions(self) -> tuple[ModelDecision, ...]:
        return tuple(self._history)

    def specialist_target(self, role: str) -> ModelTarget | None:
        return self._specialists.get(role.strip().lower())
