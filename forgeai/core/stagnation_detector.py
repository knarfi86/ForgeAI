"""Deterministic recovery stagnation detection for AgentRun history."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence


@dataclass(frozen=True)
class StagnationStatus:
    """Deterministic observation of repeated failed recovery attempts.

    The status is evidence, not an escalation decision. RecoveryEscalation may
    consume it later, but this module never changes an AgentRun state.
    """

    active: bool = False
    error_signature: str | None = None
    same_error_count: int = 0
    repeated_paths: tuple[str, ...] = ()
    same_target_count: int = 0
    reason_codes: tuple[str, ...] = ()
    detected_after_repair_attempt: int = 0


class StagnationDetector:
    """Evaluate repair/verification history without an LLM or domain rules."""

    def __init__(
        self,
        *,
        same_error_threshold: int = 2,
        same_target_threshold: int = 2,
    ) -> None:
        if same_error_threshold < 2:
            raise ValueError("same_error_threshold muss mindestens 2 sein.")
        if same_target_threshold < 2:
            raise ValueError("same_target_threshold muss mindestens 2 sein.")
        self.same_error_threshold = same_error_threshold
        self.same_target_threshold = same_target_threshold

    def evaluate(
        self,
        verification_history: Sequence[Any],
        repair_history: Sequence[Any],
    ) -> StagnationStatus:
        """Return a deterministic status derived only from recorded evidence."""

        latest_signature, same_error_count = self._same_failure_count(
            verification_history
        )
        repeated_paths, same_target_count = self._same_target_count(
            repair_history
        )

        reasons: list[str] = []
        if latest_signature and same_error_count >= self.same_error_threshold:
            reasons.append("repeated_failure")
        if repeated_paths and same_target_count >= self.same_target_threshold:
            reasons.append("repeated_target")

        active = (
            "repeated_failure" in reasons
            and "repeated_target" in reasons
        )

        last_attempt = 0
        if repair_history:
            try:
                last_attempt = int(getattr(repair_history[-1], "repair_attempt", 0))
            except (TypeError, ValueError):
                last_attempt = 0

        return StagnationStatus(
            active=active,
            error_signature=latest_signature,
            same_error_count=same_error_count,
            repeated_paths=repeated_paths,
            same_target_count=same_target_count,
            reason_codes=tuple(reasons),
            detected_after_repair_attempt=last_attempt if active else 0,
        )

    @staticmethod
    def _same_failure_count(
        verification_history: Sequence[Any],
    ) -> tuple[str | None, int]:
        if not verification_history:
            return None, 0

        latest = verification_history[-1]
        if bool(getattr(latest, "success", False)):
            return None, 0

        signature = getattr(latest, "failure_fingerprint", None)
        if not isinstance(signature, str) or not signature:
            return None, 0

        count = 0
        for entry in reversed(verification_history):
            if bool(getattr(entry, "success", False)):
                break
            if getattr(entry, "failure_fingerprint", None) != signature:
                break
            count += 1

        return signature, count

    @staticmethod
    def _same_target_count(
        repair_history: Sequence[Any],
    ) -> tuple[tuple[str, ...], int]:
        if not repair_history:
            return (), 0

        latest_paths = tuple(getattr(repair_history[-1], "planned_paths", ()) or ())
        if not latest_paths:
            return (), 0

        count = 0
        for entry in reversed(repair_history):
            paths = tuple(getattr(entry, "planned_paths", ()) or ())
            if paths != latest_paths:
                break
            count += 1

        return latest_paths, count
