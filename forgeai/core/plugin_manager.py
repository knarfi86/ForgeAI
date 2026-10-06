from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Iterable, Mapping

from .capability_registry import (
    CapabilityMatch,
    CapabilityRegistry,
    CapabilityStatus,
    PluginManifest,
)
from .fact_evidence_provider import (
    FactContext,
    FactProvider,
    FactQuery,
    FactRecord,
    FactService,
    FactStatus,
)
from .verification_framework import (
    VerificationProfile,
    VerificationProvider,
    VerificationRegistry,
)


class CapabilityAuthorization(str, Enum):
    ALLOWED = "allowed"
    MANUAL_ONLY = "manual_only"
    DISABLED = "disabled"
    UNAVAILABLE = "unavailable"


@dataclass
class PluginPreferences:
    enabled: bool = True
    autonomous: bool = False
    project_overrides: dict[str, bool] = field(default_factory=dict)

    def autonomous_for(self, project_path: str | Path | None) -> bool:
        if project_path is None:
            return self.autonomous
        key = str(Path(project_path))
        return self.project_overrides.get(key, self.autonomous)


@dataclass(frozen=True)
class PluginAvailability:
    plugin_id: str
    available: bool
    reason_codes: tuple[str, ...] = ()
    fact_ids: tuple[str, ...] = ()
    details: tuple[str, ...] = ()
    fact_records: tuple[FactRecord, ...] = field(default=(), repr=False)


@dataclass(frozen=True)
class CapabilitySelection:
    plugin_id: str
    capability_ids: tuple[str, ...]
    reasons: tuple[str, ...]
    authorization: CapabilityAuthorization


@dataclass(frozen=True)
class CapabilityPlanStep:
    order: int
    plugin_id: str
    capability_ids: tuple[str, ...]
    reasons: tuple[str, ...]
    action_id: str | None = None
    parameters: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class CapabilityExecutionPlan:
    request_text: str
    project_path: str | None
    steps: tuple[CapabilityPlanStep, ...]
    blocked: tuple[CapabilitySelection, ...] = ()
    execution_mode: str = "serial"

    @property
    def verification_profiles(self) -> tuple[str, ...]:
        # Filled by PluginManager.verification_profiles_for() because the plan
        # itself intentionally does not retain registry state.
        return ()


@dataclass(frozen=True)
class CapabilityExecutionContext:
    task_id: str
    execution_round: int
    project_path: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)


PluginExecutor = Callable[[CapabilityExecutionContext, CapabilityPlanStep], object]


class PluginManager:
    """Authorization, availability and strictly serial capability coordination."""

    def __init__(
        self,
        registry: CapabilityRegistry | None = None,
        *,
        fact_service: FactService | None = None,
        verification_registry: VerificationRegistry | None = None,
    ) -> None:
        self.registry = registry or CapabilityRegistry()
        self.fact_service = fact_service
        self.verification_registry = verification_registry
        self._preferences: dict[str, PluginPreferences] = {}
        self._executors: dict[str, PluginExecutor] = {}

    def register_plugin(
        self,
        manifest: PluginManifest,
        *,
        executor: PluginExecutor | None = None,
        fact_providers: Iterable[FactProvider] = (),
        verification_providers: Iterable[VerificationProvider] = (),
        verification_profiles: Iterable[VerificationProfile] = (),
        replace: bool = False,
    ) -> None:
        fact_providers = tuple(fact_providers)
        verification_providers = tuple(verification_providers)
        verification_profiles = tuple(verification_profiles)

        registered_ids = {item.plugin_id for item in self.registry.list_manifests()}
        if manifest.plugin_id in registered_ids and not replace:
            raise ValueError(f"Plugin bereits registriert: {manifest.plugin_id}")
        if executor is not None and manifest.plugin_id in self._executors and not replace:
            raise ValueError(f"PluginExecutor bereits registriert: {manifest.plugin_id}")
        if fact_providers and self.fact_service is None:
            raise RuntimeError("FactProvider benötigen einen konfigurierten FactService.")
        if (verification_providers or verification_profiles) and self.verification_registry is None:
            raise RuntimeError(
                "Verification-Komponenten benötigen eine konfigurierte VerificationRegistry."
            )

        provided_profile_ids = {profile.profile_id for profile in verification_profiles}
        undeclared = provided_profile_ids.difference(manifest.verification_profiles)
        if undeclared:
            raise ValueError(
                "Plugin registriert nicht deklarierte Verification-Profile: "
                + ", ".join(sorted(undeclared))
            )

        # Register external hooks first after all cross-registry preconditions have
        # been checked. Manifest registration is then deterministic and cannot
        # leave an unusable plugin visible because a required registry was absent.
        if self.fact_service is not None:
            for provider in fact_providers:
                self.fact_service.registry.register_provider(provider, replace=replace)
        if self.verification_registry is not None:
            for provider in verification_providers:
                self.verification_registry.register_provider(provider, replace=replace)
            for profile in verification_profiles:
                self.verification_registry.register_profile(profile, replace=replace)

        self.registry.register(manifest, replace=replace)
        self._preferences.setdefault(manifest.plugin_id, PluginPreferences())
        if executor is not None:
            self._executors[manifest.plugin_id] = executor

    def preferences(self, plugin_id: str) -> PluginPreferences:
        self.registry.get(plugin_id)
        return self._preferences.setdefault(plugin_id, PluginPreferences())

    def set_enabled(self, plugin_id: str, enabled: bool) -> None:
        self.preferences(plugin_id).enabled = bool(enabled)

    def set_autonomous(self, plugin_id: str, autonomous: bool) -> None:
        self.preferences(plugin_id).autonomous = bool(autonomous)

    def set_project_autonomous(
        self,
        plugin_id: str,
        project_path: str | Path,
        allowed: bool,
    ) -> None:
        self.preferences(plugin_id).project_overrides[str(Path(project_path))] = bool(allowed)

    def clear_project_override(self, plugin_id: str, project_path: str | Path) -> None:
        self.preferences(plugin_id).project_overrides.pop(str(Path(project_path)), None)

    def authorization_for(
        self,
        plugin_id: str,
        *,
        project_path: str | Path | None = None,
    ) -> CapabilityAuthorization:
        manifest = self.registry.get(plugin_id)
        if manifest.status in {CapabilityStatus.PLANNED, CapabilityStatus.UNAVAILABLE}:
            return CapabilityAuthorization.UNAVAILABLE

        prefs = self.preferences(plugin_id)
        if not prefs.enabled:
            return CapabilityAuthorization.DISABLED
        if not prefs.autonomous_for(project_path):
            return CapabilityAuthorization.MANUAL_ONLY
        return CapabilityAuthorization.ALLOWED

    def evaluate_availability(
        self,
        plugin_id: str,
        context: CapabilityExecutionContext,
    ) -> PluginAvailability:
        manifest = self.registry.get(plugin_id)
        reason_codes: list[str] = []
        fact_ids: list[str] = []
        details: list[str] = []
        fact_records: list[FactRecord] = []

        for dependency in manifest.dependencies:
            if dependency not in {item.plugin_id for item in self.registry.list_manifests()}:
                reason_codes.append(f"dependency_not_registered:{dependency}")
                continue
            if not self.preferences(dependency).enabled:
                reason_codes.append(f"dependency_disabled:{dependency}")

        if manifest.fact_requirements:
            if self.fact_service is None:
                reason_codes.append("fact_service_missing")
            else:
                fact_context = FactContext(
                    task_id=context.task_id,
                    execution_round=context.execution_round,
                    project_path=context.project_path,
                    metadata=dict(context.metadata),
                )
                for requirement in manifest.fact_requirements:
                    resolution = self.fact_service.resolve(
                        FactQuery(
                            fact_key=requirement.fact_key,
                            provider_id=requirement.provider_id,
                            max_age_seconds=requirement.max_age_seconds,
                        ),
                        fact_context,
                    )
                    record = resolution.record
                    fact_ids.append(record.fact_id)
                    fact_records.append(record)
                    if record.summary:
                        details.append(record.summary)
                    if record.status != FactStatus.OBSERVED:
                        reason_codes.append(
                            f"fact_not_observed:{requirement.fact_key}:{record.status.value}"
                        )
                        continue
                    if (
                        requirement.expected_value is not None
                        and record.value != requirement.expected_value
                    ):
                        reason_codes.append(f"fact_value_mismatch:{requirement.fact_key}")

        return PluginAvailability(
            plugin_id=plugin_id,
            available=not reason_codes,
            reason_codes=tuple(reason_codes),
            fact_ids=tuple(fact_ids),
            details=tuple(dict.fromkeys(details)),
            fact_records=tuple(fact_records),
        )

    def select_for_request(
        self,
        request_text: str,
        *,
        project_path: str | Path | None = None,
        observed_project_markers: Iterable[str] = (),
        explicit_capabilities: Iterable[str] = (),
    ) -> tuple[CapabilitySelection, ...]:
        matches = self.registry.match_request(
            request_text,
            observed_project_markers=observed_project_markers,
            explicit_capabilities=explicit_capabilities,
        )
        selections: list[CapabilitySelection] = []
        for match in matches:
            authorization = self.authorization_for(
                match.plugin_id,
                project_path=project_path,
            )
            selections.append(
                CapabilitySelection(
                    plugin_id=match.plugin_id,
                    capability_ids=match.capability_ids,
                    reasons=match.reasons,
                    authorization=authorization,
                )
            )
        return tuple(selections)

    def build_execution_plan(
        self,
        request_text: str,
        *,
        project_path: str | Path | None = None,
        observed_project_markers: Iterable[str] = (),
        explicit_capabilities: Iterable[str] = (),
    ) -> CapabilityExecutionPlan:
        selections = self.select_for_request(
            request_text,
            project_path=project_path,
            observed_project_markers=observed_project_markers,
            explicit_capabilities=explicit_capabilities,
        )
        allowed_by_id = {
            item.plugin_id: item
            for item in selections
            if item.authorization == CapabilityAuthorization.ALLOWED
        }
        blocked_by_id = {
            item.plugin_id: item
            for item in selections
            if item.authorization != CapabilityAuthorization.ALLOWED
        }
        registered_ids = {item.plugin_id for item in self.registry.list_manifests()}

        resolving: set[str] = set()
        resolved: set[str] = set()

        def ensure_dependencies(plugin_id: str) -> bool:
            if plugin_id in resolved:
                return plugin_id in allowed_by_id
            if plugin_id in resolving:
                raise ValueError("Zyklische Plugin-Abhängigkeit erkannt.")
            resolving.add(plugin_id)
            manifest = self.registry.get(plugin_id)
            ok = True

            for dependency in manifest.dependencies:
                if dependency not in registered_ids:
                    blocked_by_id[plugin_id] = CapabilitySelection(
                        plugin_id=plugin_id,
                        capability_ids=allowed_by_id[plugin_id].capability_ids,
                        reasons=(
                            *allowed_by_id[plugin_id].reasons,
                            f"dependency_not_registered:{dependency}",
                        ),
                        authorization=CapabilityAuthorization.UNAVAILABLE,
                    )
                    ok = False
                    break

                dependency_auth = self.authorization_for(
                    dependency,
                    project_path=project_path,
                )
                if dependency_auth != CapabilityAuthorization.ALLOWED:
                    dep_manifest = self.registry.get(dependency)
                    blocked_by_id[dependency] = CapabilitySelection(
                        plugin_id=dependency,
                        capability_ids=dep_manifest.capabilities,
                        reasons=(f"dependency_of:{plugin_id}",),
                        authorization=dependency_auth,
                    )
                    blocked_by_id[plugin_id] = CapabilitySelection(
                        plugin_id=plugin_id,
                        capability_ids=allowed_by_id[plugin_id].capability_ids,
                        reasons=(
                            *allowed_by_id[plugin_id].reasons,
                            f"dependency_blocked:{dependency}",
                        ),
                        authorization=CapabilityAuthorization.UNAVAILABLE,
                    )
                    ok = False
                    break

                if dependency not in allowed_by_id:
                    dep_manifest = self.registry.get(dependency)
                    allowed_by_id[dependency] = CapabilitySelection(
                        plugin_id=dependency,
                        capability_ids=dep_manifest.capabilities,
                        reasons=(f"dependency_of:{plugin_id}",),
                        authorization=CapabilityAuthorization.ALLOWED,
                    )
                if not ensure_dependencies(dependency):
                    blocked_by_id[plugin_id] = CapabilitySelection(
                        plugin_id=plugin_id,
                        capability_ids=allowed_by_id[plugin_id].capability_ids,
                        reasons=(
                            *allowed_by_id[plugin_id].reasons,
                            f"dependency_unavailable:{dependency}",
                        ),
                        authorization=CapabilityAuthorization.UNAVAILABLE,
                    )
                    ok = False
                    break

            resolving.remove(plugin_id)
            resolved.add(plugin_id)
            if not ok:
                allowed_by_id.pop(plugin_id, None)
            return ok

        for plugin_id in tuple(allowed_by_id):
            if plugin_id in allowed_by_id:
                ensure_dependencies(plugin_id)

        selected_ids = set(allowed_by_id)
        ordered_ids = self._dependency_order(selected_ids)
        steps = tuple(
            CapabilityPlanStep(
                order=index,
                plugin_id=plugin_id,
                capability_ids=allowed_by_id[plugin_id].capability_ids,
                reasons=allowed_by_id[plugin_id].reasons,
            )
            for index, plugin_id in enumerate(ordered_ids, start=1)
        )
        return CapabilityExecutionPlan(
            request_text=request_text,
            project_path=str(Path(project_path)) if project_path is not None else None,
            steps=steps,
            blocked=tuple(blocked_by_id[key] for key in sorted(blocked_by_id)),
            execution_mode="serial",
        )

    def build_action_execution_plan(
        self,
        request_text: str,
        plugin_actions: Iterable[Mapping[str, object]],
        *,
        project_path: str | Path | None = None,
    ) -> CapabilityExecutionPlan:
        """Build a deterministic execution plan from explicit AgentPlan actions.

        Manual-only plugins remain selectable here because the later execution
        gate can accept a one-shot user approval. Disabled/planned/unavailable
        plugins remain blocked. Version 1 deliberately permits one action per
        plugin so execution and approval stay unambiguous.
        """

        requests: dict[str, tuple[str, Mapping[str, object]]] = {}
        blocked: dict[str, CapabilitySelection] = {}

        for raw in plugin_actions:
            if not isinstance(raw, Mapping):
                raise ValueError("plugin_actions muss Objekte enthalten.")
            plugin_id = str(raw.get("plugin_id", "")).strip()
            action_id = str(raw.get("action", "")).strip()
            parameters = raw.get("parameters", {})
            if not plugin_id:
                raise ValueError("Plugin-Aktion benötigt plugin_id.")
            if not action_id:
                raise ValueError("Plugin-Aktion benötigt action.")
            if plugin_id in requests:
                raise ValueError(
                    f"Plugin {plugin_id!r} darf pro Plan nur eine Aktion besitzen."
                )
            if not isinstance(parameters, Mapping):
                raise ValueError("Plugin-Aktionsparameter müssen ein Objekt sein.")

            manifest = self.registry.get(plugin_id)
            spec = manifest.action_spec(action_id)
            spec.validate_parameters(parameters)
            requests[plugin_id] = (action_id, dict(parameters))

        selected_ids: set[str] = set()
        for plugin_id, (action_id, _) in requests.items():
            manifest = self.registry.get(plugin_id)
            authorization = self.authorization_for(plugin_id, project_path=project_path)
            if authorization in {
                CapabilityAuthorization.ALLOWED,
                CapabilityAuthorization.MANUAL_ONLY,
            }:
                selected_ids.add(plugin_id)
                continue
            blocked[plugin_id] = CapabilitySelection(
                plugin_id=plugin_id,
                capability_ids=manifest.action_spec(action_id).capability_ids or manifest.capabilities,
                reasons=(f"plugin_action:{action_id}",),
                authorization=authorization,
            )

        # Explicit action plans never hide dependency execution from the user.
        # Every dependency must itself be a visible plugin_action.
        for plugin_id in tuple(selected_ids):
            manifest = self.registry.get(plugin_id)
            for dependency in manifest.dependencies:
                if dependency not in requests:
                    selected_ids.discard(plugin_id)
                    action_id, _ = requests[plugin_id]
                    blocked[plugin_id] = CapabilitySelection(
                        plugin_id=plugin_id,
                        capability_ids=manifest.action_spec(action_id).capability_ids or manifest.capabilities,
                        reasons=(
                            f"plugin_action:{action_id}",
                            f"dependency_action_required:{dependency}",
                        ),
                        authorization=CapabilityAuthorization.UNAVAILABLE,
                    )
                    break
                dependency_auth = self.authorization_for(
                    dependency, project_path=project_path
                )
                if dependency_auth not in {
                    CapabilityAuthorization.ALLOWED,
                    CapabilityAuthorization.MANUAL_ONLY,
                }:
                    selected_ids.discard(plugin_id)
                    action_id, _ = requests[plugin_id]
                    blocked[plugin_id] = CapabilitySelection(
                        plugin_id=plugin_id,
                        capability_ids=manifest.action_spec(action_id).capability_ids or manifest.capabilities,
                        reasons=(
                            f"plugin_action:{action_id}",
                            f"dependency_blocked:{dependency}",
                        ),
                        authorization=CapabilityAuthorization.UNAVAILABLE,
                    )
                    break

        changed = True
        while changed:
            changed = False
            for plugin_id in tuple(selected_ids):
                manifest = self.registry.get(plugin_id)
                missing = [
                    dependency
                    for dependency in manifest.dependencies
                    if dependency not in selected_ids
                ]
                if not missing:
                    continue
                selected_ids.discard(plugin_id)
                action_id, _ = requests[plugin_id]
                blocked[plugin_id] = CapabilitySelection(
                    plugin_id=plugin_id,
                    capability_ids=manifest.action_spec(action_id).capability_ids or manifest.capabilities,
                    reasons=(
                        f"plugin_action:{action_id}",
                        f"dependency_blocked:{missing[0]}",
                    ),
                    authorization=CapabilityAuthorization.UNAVAILABLE,
                )
                changed = True

        ordered_ids = self._dependency_order(selected_ids)
        steps: list[CapabilityPlanStep] = []
        for index, plugin_id in enumerate(ordered_ids, start=1):
            action_id, parameters = requests[plugin_id]
            manifest = self.registry.get(plugin_id)
            spec = manifest.action_spec(action_id)
            steps.append(
                CapabilityPlanStep(
                    order=index,
                    plugin_id=plugin_id,
                    capability_ids=spec.capability_ids or manifest.capabilities,
                    reasons=(f"plugin_action:{action_id}",),
                    action_id=action_id,
                    parameters=dict(parameters),
                )
            )

        return CapabilityExecutionPlan(
            request_text=request_text,
            project_path=str(Path(project_path)) if project_path is not None else None,
            steps=tuple(steps),
            blocked=tuple(blocked[key] for key in sorted(blocked)),
            execution_mode="serial",
        )

    def has_executor(self, plugin_id: str) -> bool:
        """Return whether a concrete executor is registered for the plugin."""
        self.registry.get(plugin_id)
        return plugin_id in self._executors

    def preflight_execution(
        self,
        plan: CapabilityExecutionPlan,
        context: CapabilityExecutionContext,
    ):
        """Run the mandatory deterministic gate for a real plugin execution."""
        from .capability_execution_gate import CapabilityExecutionGate

        return CapabilityExecutionGate(self).evaluate(plan, context)

    def validate_plan(
        self,
        plan: CapabilityExecutionPlan,
        context: CapabilityExecutionContext,
    ) -> tuple[PluginAvailability, ...]:
        return tuple(
            self.evaluate_availability(step.plugin_id, context)
            for step in plan.steps
        )

    def execute_serial(
        self,
        plan: CapabilityExecutionPlan,
        context: CapabilityExecutionContext,
    ) -> tuple[object, ...]:
        """Execute plugin steps serially after the mandatory execution gate.

        Callers cannot bypass authorization/runtime/verification preflight by
        invoking this method directly. Core file changes do not use this API.
        """
        gate = self.preflight_execution(plan, context)
        if not gate.ready:
            raise RuntimeError(
                "Capability Execution Gate blockiert die Plugin-Ausführung: "
                + ", ".join(gate.reason_codes)
            )

        results: list[object] = []
        for step in plan.steps:
            # The gate has already proved that every executor exists. Keep the
            # lookup defensive in case the registry is mutated concurrently.
            try:
                executor = self._executors[step.plugin_id]
            except KeyError as exc:
                raise RuntimeError(
                    f"Für Plugin {step.plugin_id!r} ist kein Executor registriert."
                ) from exc
            result = executor(context, step)
            failed = False
            detail = ""
            if isinstance(result, Mapping):
                failed = result.get("success") is False
                detail = str(result.get("output", ""))
            elif getattr(result, "success", None) is False:
                failed = True
                detail = str(getattr(result, "output", ""))
            if failed:
                action_text = f"/{step.action_id}" if step.action_id else ""
                raise RuntimeError(
                    f"Plugin-Aktion {step.plugin_id}{action_text} ist fehlgeschlagen"
                    + (f": {detail}" if detail else ".")
                )
            results.append(result)
        return tuple(results)

    def planning_snapshot(
        self,
        plan: CapabilityExecutionPlan,
        *,
        project_path: str | Path | None = None,
    ) -> Mapping[str, object]:
        """Return deterministic capability facts for planner/reviewer prompts.

        This snapshot describes optional plugin/tool capabilities. It does not
        remove or restrict the core agent's ordinary reasoning and file-planning
        abilities. Runtime availability is intentionally not claimed here; fact
        requirements are validated immediately before actual plugin execution.
        """
        selected_by_id = {step.plugin_id: step for step in plan.steps}
        blocked_by_id = {item.plugin_id: item for item in plan.blocked}
        entries: list[Mapping[str, object]] = []

        for manifest in self.registry.list_manifests():
            authorization = self.authorization_for(
                manifest.plugin_id,
                project_path=project_path,
            )
            selected = selected_by_id.get(manifest.plugin_id)
            blocked = blocked_by_id.get(manifest.plugin_id)
            reasons: tuple[str, ...] = ()
            if selected is not None:
                reasons = selected.reasons
            elif blocked is not None:
                reasons = blocked.reasons

            entries.append(
                {
                    "plugin_id": manifest.plugin_id,
                    "name": manifest.name,
                    "version": manifest.version,
                    "category": manifest.category.value,
                    "status": manifest.status.value,
                    "authorization": authorization.value,
                    "matched": selected is not None or blocked is not None,
                    "selected_for_execution": selected is not None,
                    "capabilities": manifest.capabilities,
                    "dependencies": manifest.dependencies,
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
                    "reasons": reasons,
                    "verification_profiles": manifest.verification_profiles,
                    "model_roles": manifest.model_roles,
                    "description": manifest.description,
                    "runtime_availability": "not_checked",
                }
            )

        return {
            "scope": "optional_plugin_capabilities",
            "request_text": plan.request_text,
            "project_path": plan.project_path,
            "execution_mode": plan.execution_mode,
            "core_file_planning_unaffected": True,
            "runtime_availability_note": (
                "not_checked means runtime facts must be validated before plugin execution"
            ),
            "plugins": tuple(entries),
        }

    def verification_profiles_for(self, plan: CapabilityExecutionPlan) -> tuple[str, ...]:
        profiles: list[str] = []
        for step in plan.steps:
            manifest = self.registry.get(step.plugin_id)
            profiles.extend(manifest.verification_profiles)
        return tuple(dict.fromkeys(profiles))

    def model_roles_for(self, plan: CapabilityExecutionPlan) -> tuple[str, ...]:
        roles: list[str] = []
        for step in plan.steps:
            roles.extend(self.registry.get(step.plugin_id).model_roles)
        return tuple(dict.fromkeys(roles))

    def snapshot(self, *, project_path: str | Path | None = None) -> tuple[Mapping[str, object], ...]:
        rows: list[Mapping[str, object]] = []
        for manifest in self.registry.list_manifests():
            prefs = self.preferences(manifest.plugin_id)
            rows.append(
                {
                    "plugin_id": manifest.plugin_id,
                    "name": manifest.name,
                    "version": manifest.version,
                    "category": manifest.category.value,
                    "status": manifest.status.value,
                    "enabled": prefs.enabled,
                    "autonomous": prefs.autonomous,
                    "project_autonomous": prefs.autonomous_for(project_path),
                    "capabilities": manifest.capabilities,
                    "actions": tuple(action.action_id for action in manifest.actions),
                    "verification_profiles": manifest.verification_profiles,
                    "model_roles": manifest.model_roles,
                    "resources": manifest.resources,
                    "description": manifest.description,
                }
            )
        return tuple(rows)

    def export_preferences(self) -> dict[str, object]:
        return {
            plugin_id: {
                "enabled": prefs.enabled,
                "autonomous": prefs.autonomous,
                "project_overrides": dict(prefs.project_overrides),
            }
            for plugin_id, prefs in sorted(self._preferences.items())
        }

    def import_preferences(self, payload: Mapping[str, object]) -> None:
        for plugin_id, raw in payload.items():
            if plugin_id not in {item.plugin_id for item in self.registry.list_manifests()}:
                continue
            if not isinstance(raw, Mapping):
                continue
            prefs = self.preferences(plugin_id)
            prefs.enabled = bool(raw.get("enabled", prefs.enabled))
            prefs.autonomous = bool(raw.get("autonomous", prefs.autonomous))
            overrides = raw.get("project_overrides", {})
            if isinstance(overrides, Mapping):
                prefs.project_overrides = {
                    str(path): bool(value) for path, value in overrides.items()
                }

    def _dependency_order(self, selected_ids: set[str]) -> tuple[str, ...]:
        ordered: list[str] = []
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(plugin_id: str) -> None:
            if plugin_id in visited:
                return
            if plugin_id in visiting:
                raise ValueError("Zyklische Plugin-Abhängigkeit erkannt.")
            visiting.add(plugin_id)
            manifest = self.registry.get(plugin_id)
            for dependency in manifest.dependencies:
                if dependency in selected_ids:
                    visit(dependency)
            visiting.remove(plugin_id)
            visited.add(plugin_id)
            ordered.append(plugin_id)

        for plugin_id in sorted(selected_ids):
            visit(plugin_id)
        return tuple(ordered)
