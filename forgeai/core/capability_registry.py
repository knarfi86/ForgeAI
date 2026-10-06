from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Mapping


class PluginCategory(str, Enum):
    DEVELOPMENT = "development"
    GAMEDEV = "gamedev"
    IMAGE = "image"
    VIDEO = "video"
    MODEL_3D = "3d"
    AUDIO = "audio"
    TOOLING = "tooling"
    OTHER = "other"


class CapabilityStatus(str, Enum):
    AVAILABLE = "available"
    EXPERIMENTAL = "experimental"
    PLANNED = "planned"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class ResourceRequirements:
    """Declarative resource needs used by the serial capability scheduler."""

    gpu_required: bool = False
    min_vram_mb: int = 0
    min_ram_mb: int = 0
    exclusive_resources: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.min_vram_mb < 0 or self.min_ram_mb < 0:
            raise ValueError("Resource requirements dürfen nicht negativ sein.")


@dataclass(frozen=True)
class PluginFactRequirement:
    """Objective availability requirement resolved through FactService at use time."""

    fact_key: str
    provider_id: str | None = None
    expected_value: object | None = None
    max_age_seconds: float = 30.0

    def __post_init__(self) -> None:
        if not self.fact_key.strip():
            raise ValueError("fact_key darf nicht leer sein.")
        if self.max_age_seconds < 0:
            raise ValueError("max_age_seconds darf nicht negativ sein.")




@dataclass(frozen=True)
class PluginActionSpec:
    """Declarative contract for one concrete executor action."""

    action_id: str
    capability_ids: tuple[str, ...] = ()
    parameter_keys: tuple[str, ...] = ()
    allow_unknown_parameters: bool = False
    description: str = ""

    def __post_init__(self) -> None:
        action_id = self.action_id.strip()
        if not action_id:
            raise ValueError("action_id darf nicht leer sein.")
        object.__setattr__(self, "action_id", action_id)

        for field_name in ("capability_ids", "parameter_keys"):
            values = tuple(str(value).strip() for value in getattr(self, field_name))
            if any(not value for value in values):
                raise ValueError(f"{field_name} enthält leere Werte.")
            if len(values) != len(set(values)):
                raise ValueError(f"{field_name} muss eindeutig sein.")
            object.__setattr__(self, field_name, values)

    def validate_parameters(self, parameters: Mapping[str, object]) -> None:
        if not isinstance(parameters, Mapping):
            raise ValueError("Plugin-Aktionsparameter müssen ein Objekt sein.")
        if self.allow_unknown_parameters:
            return
        unknown = sorted(set(parameters).difference(self.parameter_keys))
        if unknown:
            raise ValueError(
                f"Unbekannte Parameter für Aktion {self.action_id!r}: "
                + ", ".join(unknown)
            )


@dataclass(frozen=True)
class PluginManifest:
    """Declarative description of one optional Forge capability plugin."""

    plugin_id: str
    name: str
    version: str
    category: PluginCategory = PluginCategory.OTHER
    status: CapabilityStatus = CapabilityStatus.AVAILABLE
    capabilities: tuple[str, ...] = ()
    actions: tuple[PluginActionSpec, ...] = ()
    dependencies: tuple[str, ...] = ()
    fact_requirements: tuple[PluginFactRequirement, ...] = ()
    verification_profiles: tuple[str, ...] = ()
    model_roles: tuple[str, ...] = ()
    task_hints: tuple[str, ...] = ()
    project_markers: tuple[str, ...] = ()
    resources: ResourceRequirements = field(default_factory=ResourceRequirements)
    description: str = ""

    def __post_init__(self) -> None:
        plugin_id = self.plugin_id.strip()
        if not plugin_id:
            raise ValueError("plugin_id darf nicht leer sein.")
        if not self.name.strip():
            raise ValueError("Plugin name darf nicht leer sein.")
        if not self.version.strip():
            raise ValueError("Plugin version darf nicht leer sein.")
        if not isinstance(self.category, PluginCategory):
            object.__setattr__(self, "category", PluginCategory(self.category))
        if not isinstance(self.status, CapabilityStatus):
            object.__setattr__(self, "status", CapabilityStatus(self.status))

        for field_name in (
            "capabilities",
            "dependencies",
            "verification_profiles",
            "model_roles",
            "task_hints",
            "project_markers",
        ):
            values = tuple(str(value).strip() for value in getattr(self, field_name))
            if any(not value for value in values):
                raise ValueError(f"{field_name} enthält leere Werte.")
            if len(values) != len(set(values)):
                raise ValueError(f"{field_name} muss eindeutig sein.")
            object.__setattr__(self, field_name, values)

        actions = tuple(self.actions)
        if not all(isinstance(action, PluginActionSpec) for action in actions):
            raise ValueError("actions muss ausschließlich PluginActionSpec enthalten.")
        action_ids = [action.action_id for action in actions]
        if len(action_ids) != len(set(action_ids)):
            raise ValueError("action_id muss innerhalb eines Plugins eindeutig sein.")
        capability_set = set(self.capabilities)
        for action in actions:
            unknown_capabilities = set(action.capability_ids).difference(capability_set)
            if unknown_capabilities:
                raise ValueError(
                    f"Aktion {action.action_id!r} verweist auf nicht deklarierte Capabilities: "
                    + ", ".join(sorted(unknown_capabilities))
                )
        object.__setattr__(self, "actions", actions)

        if plugin_id in self.dependencies:
            raise ValueError("Ein Plugin darf nicht von sich selbst abhängen.")

    def action_spec(self, action_id: str) -> PluginActionSpec:
        normalized = str(action_id).strip()
        for action in self.actions:
            if action.action_id == normalized:
                return action
        raise KeyError(
            f"Plugin {self.plugin_id!r} deklariert keine Aktion {normalized!r}."
        )


@dataclass(frozen=True)
class CapabilityMatch:
    plugin_id: str
    capability_ids: tuple[str, ...]
    reasons: tuple[str, ...]


class CapabilityRegistry:
    """Registry and deterministic request matcher for plugin capabilities.

    The registry never enables plugins and never executes tools. It only knows
    what registered manifests advertise. Authorization remains PluginManager's
    responsibility.
    """

    def __init__(self) -> None:
        self._manifests: dict[str, PluginManifest] = {}

    def register(self, manifest: PluginManifest, *, replace: bool = False) -> None:
        if manifest.plugin_id in self._manifests and not replace:
            raise ValueError(f"Plugin bereits registriert: {manifest.plugin_id}")
        self._manifests[manifest.plugin_id] = manifest

    def get(self, plugin_id: str) -> PluginManifest:
        try:
            return self._manifests[plugin_id]
        except KeyError as exc:
            raise KeyError(f"Plugin nicht registriert: {plugin_id}") from exc

    def list_manifests(self) -> tuple[PluginManifest, ...]:
        return tuple(self._manifests[key] for key in sorted(self._manifests))

    def providers_for_capability(self, capability_id: str) -> tuple[PluginManifest, ...]:
        return tuple(
            manifest
            for manifest in self.list_manifests()
            if capability_id in manifest.capabilities
        )

    def match_request(
        self,
        request_text: str,
        *,
        observed_project_markers: Iterable[str] = (),
        explicit_capabilities: Iterable[str] = (),
    ) -> tuple[CapabilityMatch, ...]:
        """Return deterministic candidates from manifest hints and explicit needs.

        This is intentionally conservative. Later semantic planning may add
        explicit capability IDs, but the final mapping to concrete plugins stays
        deterministic here.
        """

        text = request_text.casefold()
        explicit = tuple(dict.fromkeys(str(item).strip() for item in explicit_capabilities if str(item).strip()))
        observed_markers = {str(item).strip() for item in observed_project_markers if str(item).strip()}
        matches: list[CapabilityMatch] = []

        for manifest in self.list_manifests():
            reasons: list[str] = []
            capabilities: list[str] = []

            for capability in explicit:
                if capability in manifest.capabilities:
                    capabilities.append(capability)
                    reasons.append(f"explicit:{capability}")

            for hint in manifest.task_hints:
                if hint.casefold() in text:
                    reasons.append(f"task_hint:{hint}")
                    capabilities.extend(manifest.capabilities)
                    break

            for marker in manifest.project_markers:
                if marker in observed_markers:
                    reasons.append(f"project_marker:{marker}")
                    capabilities.extend(manifest.capabilities)
                    break

            if reasons:
                matches.append(
                    CapabilityMatch(
                        plugin_id=manifest.plugin_id,
                        capability_ids=tuple(dict.fromkeys(capabilities or manifest.capabilities)),
                        reasons=tuple(dict.fromkeys(reasons)),
                    )
                )

        return tuple(matches)

    def manifest_snapshot(self) -> tuple[Mapping[str, object], ...]:
        return tuple(
            {
                "plugin_id": manifest.plugin_id,
                "name": manifest.name,
                "version": manifest.version,
                "category": manifest.category.value,
                "status": manifest.status.value,
                "capabilities": manifest.capabilities,
                "actions": tuple(
                    {
                        "action_id": action.action_id,
                        "capability_ids": action.capability_ids,
                        "parameter_keys": action.parameter_keys,
                        "allow_unknown_parameters": action.allow_unknown_parameters,
                        "description": action.description,
                    }
                    for action in manifest.actions
                ),
                "verification_profiles": manifest.verification_profiles,
                "model_roles": manifest.model_roles,
                "resources": {
                    "gpu_required": manifest.resources.gpu_required,
                    "min_vram_mb": manifest.resources.min_vram_mb,
                    "min_ram_mb": manifest.resources.min_ram_mb,
                    "exclusive_resources": manifest.resources.exclusive_resources,
                },
            }
            for manifest in self.list_manifests()
        )
