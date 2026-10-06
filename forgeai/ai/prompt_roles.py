from __future__ import annotations

import re
from pathlib import Path

_ROLE_ROOT = Path(__file__).resolve().parent / "prompts" / "roles"
_ROLE_ID = re.compile(r"^[a-z0-9_]+$")


class RossaRolePromptError(RuntimeError):
    """Raised when a ROSSA role prompt cannot be loaded safely."""


def role_prompt_path(role_id: str) -> Path:
    normalized = str(role_id).strip().lower()
    if not normalized or not _ROLE_ID.fullmatch(normalized):
        raise ValueError(f"Ungültige ROSSA-Rollen-ID: {role_id!r}")
    return _ROLE_ROOT / f"{normalized}.md"


def load_role_prompt(role_id: str) -> str:
    path = role_prompt_path(role_id)
    try:
        content = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RossaRolePromptError(
            f"ROSSA-Rollenprompt konnte nicht gelesen werden: {path}"
        ) from exc

    if not content:
        raise RossaRolePromptError(
            f"ROSSA-Rollenprompt ist leer: {path}"
        )

    return content
