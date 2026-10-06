from __future__ import annotations

from pathlib import Path
from typing import Iterable

_CORE_PATH = (
    Path(__file__).resolve().parent
    / "prompts"
    / "core"
    / "ROSSA_CORE_IDENTITY.md"
)

_REQUIRED_MARKERS = (
    "# ROSSA Systems",
    "Research Orchestration, Software Synthesis & Automation",
    "Understand. Reason. Build. Verify.",
)


class RossaPromptCoreError(RuntimeError):
    """Raised when the ROSSA core identity cannot be loaded safely."""


def core_identity_path() -> Path:
    """Return the canonical ROSSA core identity file."""
    return _CORE_PATH


def load_core_identity() -> str:
    """Load and validate the canonical ROSSA core identity."""
    try:
        content = _CORE_PATH.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RossaPromptCoreError(
            f"ROSSA core identity could not be read: {_CORE_PATH}"
        ) from exc

    missing = [marker for marker in _REQUIRED_MARKERS if marker not in content]
    if missing:
        raise RossaPromptCoreError(
            "ROSSA core identity is incomplete or invalid. "
            f"Missing markers: {missing}"
        )

    return content


def compose_system_prompt(
    *parts: str | None,
    include_core: bool = True,
) -> str:
    """
    Compose one system prompt from the stable ROSSA core plus role/policy layers.

    Ordering is intentional:
    1. Core identity
    2. Operating policy / role instructions supplied by the caller
    3. Optional personality or task-specific presentation layers

    Empty parts are ignored.
    """
    sections: list[str] = []

    if include_core:
        sections.append(load_core_identity())

    sections.extend(_clean_parts(parts))
    return "\n\n".join(sections).strip()


def _clean_parts(parts: Iterable[str | None]) -> list[str]:
    cleaned: list[str] = []
    for part in parts:
        if part is None:
            continue
        text = str(part).strip()
        if text:
            cleaned.append(text)
    return cleaned
