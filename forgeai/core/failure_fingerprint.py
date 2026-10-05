"""Deterministic failure identities without an LLM or runner dependency."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class FailureFingerprint:
    """Versioned identity of normalized diagnostic output, not a verdict."""

    signature: str
    normalized_output: str

    @classmethod
    def from_output(cls, output: str) -> FailureFingerprint:
        text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", output)
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        def quoted_path(match: re.Match) -> str:
            quote, path = match.group(1), match.group(2)
            name = path.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
            return f"{quote}<PATH>/{name}{quote}"

        # Keep the filename. Different workspaces must not change identity,
        # but main.py and combat.py must remain distinguishable.
        text = re.sub(r'''(["'])((?:[A-Za-z]:[\\/]|/|\\\\)[^"'\n]+)\1''', quoted_path, text)

        def absolute_path(match: re.Match) -> str:
            name = match.group().replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
            return f"<PATH>/{name}"

        text = re.sub(
            r'''(?<![\w.<>])(?:[A-Za-z]:[\\/]|\\\\|/)[^\s'"<>:,;()]+''',
            absolute_path,
            text,
        )
        text = re.sub(r"\bline\s+\d+\b", "line <N>", text, flags=re.IGNORECASE)
        text = re.sub(
            r"(\b[\w.-]+\.(?:py|pyw|cpp|c|h|hpp|cs|js|ts|tsx|jsx|java|rs|go|lua)):\d+(?::\d+)?",
            r"\1:<N>",
            text,
        )
        text = re.sub(
            r"(\b(?:at|address|pointer)\s*(?:[=:]\s*)?)0x[0-9a-fA-F]+\b",
            r"\1<ADDR>",
            text,
        )
        text = re.sub(
            r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?\b",
            "<TIME>",
            text,
        )
        text = re.sub(r"\bin\s+\d+(?:\.\d+)?\s*(?:seconds?|secs?|s)\b", "in <TIME>", text)
        text = re.sub(r"\b\d+ passed\b", "<N> passed", text)

        lines = []
        for line in text.splitlines():
            line = line.strip()
            if line and not re.fullmatch(r"[.FsEx]+(?:\s+\[\s*\d+%\])?", line):
                lines.append(line)
        normalized = "\n".join(lines) or "<NO_TEST_OUTPUT>"
        digest = hashlib.sha256(("v1\n" + normalized).encode("utf-8")).hexdigest()[:16]
        return cls(signature=f"E-v1-{digest}", normalized_output=normalized)
