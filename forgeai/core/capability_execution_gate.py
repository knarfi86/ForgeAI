from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping

from .fact_evidence_provider import FactRecord
from .plugin_manager import (
    CapabilityAuthorization,
    CapabilityExecutionContext,
    CapabilityExecutionPlan,
    PluginManager,
)


class CapabilityGateDecision(str, Enum):
    """Outcome of the deterministic pre-execution capability gate."""

    NOT_REQUIRED = "not_required"
    READY = "ready"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class CapabilityGateCheck:
    plugin_id: str
    authorization: CapabilityAuthorization
    available: bool
    status: str
    action_id: str | None = None
    manual_approval_used: bool = False
    reason_codes: tuple[str, ...] = ()
    fact_ids: tuple[str, ...] = ()
    verification_profiles: tuple[str, ...] = ()


@dataclass(frozen=True)
class CapabilityExecutionGateResult:
    decision: CapabilityGateDecision
    checks: tuple[CapabilityGateCheck, ...] = ()
    verification_profiles: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()
    fact_records: tuple[FactRecord, ...] = field(default=(), repr=False)

    @property
    def ready(self) -> bool:
        return self.decision in {
            CapabilityGateDecision.NOT_REQUIRED,
            CapabilityGateDecision.READY,
        }

    def as_dict(self) -> Mapping[str, object]:
        return {
            "decision": self.decision.value,
            "ready": self.ready,
            "reason_codes": self.reason_codes,
            "verification_profiles": self.verification_profiles,
            "checks": tuple(
                {
                    "plugin_id": check.plugin_id,
                    "authorization": check.authorization.value,
                    "available": check.available,
                    "status": check.status,
                    "action_id": check.action_id,
                    "manual_approval_used": check.manual_approval_used,
                    "reason_codes": check.reason_codes,
                    "fact_ids": check.fact_ids,
                    "verification_profiles": check.verification_profiles,
                }
                for check in self.checks
            ),
        }


class CapabilityExecutionGate:
    """Final deterministic barrier before a real plugin executor may run.

    The gate applies only to optional plugin/tool execution. It deliberately does
    not restrict ROSSA's core reasoning or ordinary file-change workflow.
    """

    def __init__(self, manager: PluginManager) -> None:
        if not isinstance(manager, PluginManager):
            raise TypeError("manager muss PluginManager sein.")
        self.manager = manager

    def evaluate(
        self,
        plan: CapabilityExecutionPlan,
        context: CapabilityExecutionContext,
    ) -> CapabilityExecutionGateResult:
        if not isinstance(plan, CapabilityExecutionPlan):
            raise TypeError("plan muss CapabilityExecutionPlan sein.")
        if not isinstance(context, CapabilityExecutionContext):
            raise TypeError("context muss CapabilityExecutionContext sein.")

        if not plan.steps:
            return CapabilityExecutionGateResult(
                decision=CapabilityGateDecision.NOT_REQUIRED,
                reason_codes=("no_plugin_execution_steps",),
            )

        global_reasons: list[str] = []
        if plan.execution_mode != "serial":
            global_reasons.append(f"unsupported_execution_mode:{plan.execution_mode}")

        plan_ids = [step.plugin_id for step in plan.steps]
        plan_positions = {plugin_id: index for index, plugin_id in enumerate(plan_ids)}
        checks: list[CapabilityGateCheck] = []
        profiles: list[str] = []
        fact_records: list[FactRecord] = []
        approved_raw = context.metadata.get("approved_plugin_ids", ())
        if isinstance(approved_raw, str):
            approved_plugin_ids = {approved_raw}
        else:
            try:
                approved_plugin_ids = {str(item) for item in approved_raw}
            except TypeError:
                approved_plugin_ids = set()

        for step in plan.steps:
            manifest = self.manager.registry.get(step.plugin_id)
            authorization = self.manager.authorization_for(
                step.plugin_id,
                project_path=context.project_path,
            )
            reasons: list[str] = []
            manual_approval_used = (
                authorization == CapabilityAuthorization.MANUAL_ONLY
                and step.plugin_id in approved_plugin_ids
            )
            authorization_ready = (
                authorization == CapabilityAuthorization.ALLOWED
                or manual_approval_used
            )

            if not authorization_ready:
                reasons.append(f"authorization:{authorization.value}")

            if step.action_id is not None:
                try:
                    action_spec = manifest.action_spec(step.action_id)
                    action_spec.validate_parameters(step.parameters)
                except (KeyError, ValueError) as error:
                    reasons.append(f"action_invalid:{error}")

            if not self.manager.has_executor(step.plugin_id):
                reasons.append("executor_missing")

            for dependency in manifest.dependencies:
                if dependency not in plan_positions:
                    reasons.append(f"dependency_not_in_plan:{dependency}")
                elif plan_positions[dependency] >= plan_positions[step.plugin_id]:
                    reasons.append(f"dependency_order_invalid:{dependency}")

            availability = None
            if authorization_ready:
                availability = self.manager.evaluate_availability(
                    step.plugin_id,
                    context,
                )
                if not availability.available:
                    reasons.extend(availability.reason_codes)
                fact_records.extend(availability.fact_records)

            verification_profiles = tuple(manifest.verification_profiles)
            profiles.extend(verification_profiles)
            if verification_profiles:
                if self.manager.verification_registry is None:
                    reasons.append("verification_registry_missing")
                else:
                    for profile_id in verification_profiles:
                        try:
                            self.manager.verification_registry.get_profile(profile_id)
                        except KeyError:
                            reasons.append(f"verification_profile_missing:{profile_id}")

            checks.append(
                CapabilityGateCheck(
                    plugin_id=step.plugin_id,
                    authorization=authorization,
                    available=not reasons,
                    status=manifest.status.value,
                    action_id=step.action_id,
                    manual_approval_used=manual_approval_used,
                    reason_codes=tuple(dict.fromkeys(reasons)),
                    fact_ids=(availability.fact_ids if availability is not None else ()),
                    verification_profiles=verification_profiles,
                )
            )

        blocked = [check for check in checks if not check.available]
        if blocked:
            for check in blocked:
                global_reasons.extend(
                    f"{check.plugin_id}:{reason}" for reason in check.reason_codes
                )

        unique_facts: dict[str, FactRecord] = {}
        for record in fact_records:
            unique_facts[record.fact_id] = record

        decision = (
            CapabilityGateDecision.BLOCKED
            if global_reasons
            else CapabilityGateDecision.READY
        )
        return CapabilityExecutionGateResult(
            decision=decision,
            checks=tuple(checks),
            verification_profiles=tuple(dict.fromkeys(profiles)),
            reason_codes=tuple(dict.fromkeys(global_reasons)),
            fact_records=tuple(unique_facts.values()),
        )
