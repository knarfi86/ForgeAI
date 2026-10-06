"""Deterministic recovery escalation policy for stagnating AgentRun recovery."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .stagnation_detector import StagnationStatus


class RecoveryEscalationAction(str, Enum):
    """Supported deterministic actions after recovery stagnation."""

    NONE = "none"
    BROADEN_ANALYSIS = "broaden_analysis"
    STOP = "stop"


@dataclass(frozen=True)
class RecoveryEscalationDecision:
    """Recorded escalation decision derived from objective recovery evidence."""

    active: bool = False
    action: RecoveryEscalationAction = RecoveryEscalationAction.NONE
    escalation_round: int = 0
    reason_codes: tuple[str, ...] = ()
    failure_signature: str | None = None
    repeated_paths: tuple[str, ...] = ()
    repair_attempt: int = 0
    remaining_repair_attempts: int = 0
    guidance: tuple[str, ...] = ()

    def as_prompt_context(self) -> dict[str, object]:
        """Return a JSON-safe representation for analyzer/repairer prompts."""
        return {
            "active": self.active,
            "action": self.action.value,
            "escalation_round": self.escalation_round,
            "reason_codes": list(self.reason_codes),
            "failure_signature": self.failure_signature,
            "repeated_paths": list(self.repeated_paths),
            "repair_attempt": self.repair_attempt,
            "remaining_repair_attempts": self.remaining_repair_attempts,
            "guidance": list(self.guidance),
        }


class RecoveryEscalationPolicy:
    """Map StagnationStatus to a deterministic recovery action.

    The policy does not inspect source code, invent dependencies or call an LLM.
    It only decides whether the next recovery analysis must widen its search or
    whether the configured repair budget is exhausted.
    """

    BROADEN_GUIDANCE = (
        "Wiederhole nicht denselben Reparaturplan unverändert.",
        "Prüfe im aktuellen Projektkontext relevante Caller, Imports, Abhängigkeiten und angrenzende Dateien.",
        "Bevorzuge neue Evidence gegenüber Annahmen über die bisherige Ursache.",
        "Wenn die Ursache nicht belegt werden kann, benenne fehlende Evidence statt zu raten.",
        "Eine breitere Analyse darf nur innerhalb bestehender Lese- und Schreibfreigaben arbeiten.",
    )

    def decide(
        self,
        stagnation: StagnationStatus,
        *,
        repair_attempt: int,
        max_repair_attempts: int,
        previous_escalation_round: int = 0,
    ) -> RecoveryEscalationDecision:
        if repair_attempt < 0:
            raise ValueError("repair_attempt darf nicht negativ sein.")
        if max_repair_attempts < 1:
            raise ValueError("max_repair_attempts muss mindestens 1 sein.")
        if previous_escalation_round < 0:
            raise ValueError("previous_escalation_round darf nicht negativ sein.")

        remaining = max(0, max_repair_attempts - repair_attempt)

        if not stagnation.active:
            if repair_attempt > 0 and remaining <= 0:
                return RecoveryEscalationDecision(
                    active=True,
                    action=RecoveryEscalationAction.STOP,
                    escalation_round=previous_escalation_round + 1,
                    reason_codes=("repair_budget_exhausted",),
                    repair_attempt=repair_attempt,
                    remaining_repair_attempts=0,
                    guidance=(
                        "Keine weitere automatische Reparatur starten.",
                        "Den Lauf kontrolliert als fehlgeschlagen beenden und die aufgezeichnete Recovery-Evidence erhalten.",
                    ),
                )
            return RecoveryEscalationDecision(
                repair_attempt=repair_attempt,
                remaining_repair_attempts=remaining,
            )

        round_number = previous_escalation_round + 1
        common_reasons = tuple(stagnation.reason_codes)

        if remaining <= 0:
            return RecoveryEscalationDecision(
                active=True,
                action=RecoveryEscalationAction.STOP,
                escalation_round=round_number,
                reason_codes=common_reasons + ("repair_budget_exhausted",),
                failure_signature=stagnation.error_signature,
                repeated_paths=tuple(stagnation.repeated_paths),
                repair_attempt=repair_attempt,
                remaining_repair_attempts=0,
                guidance=(
                    "Keine weitere automatische Reparatur starten.",
                    "Den Lauf kontrolliert als fehlgeschlagen beenden und die aufgezeichnete Recovery-Evidence erhalten.",
                ),
            )

        return RecoveryEscalationDecision(
            active=True,
            action=RecoveryEscalationAction.BROADEN_ANALYSIS,
            escalation_round=round_number,
            reason_codes=common_reasons + ("stagnation_detected",),
            failure_signature=stagnation.error_signature,
            repeated_paths=tuple(stagnation.repeated_paths),
            repair_attempt=repair_attempt,
            remaining_repair_attempts=remaining,
            guidance=self.BROADEN_GUIDANCE,
        )
