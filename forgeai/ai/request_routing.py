"""Conservative routing between a chat answer and a project file change.

Creating *content* is not the same operation as creating *a file*. Keep this
classifier independent of Qt so it can be regression-tested without a GUI.
"""

from __future__ import annotations

import re


_CHANGE_VERB = re.compile(
    r"\b(?:ändere|aendere|bearbeite|ersetze|ergänze|ergaenze|"
    r"füge|fuege|schreibe|erstelle|anlege|lösche|loesche|"
    r"verschiebe|rename|umbenenne|implementiere|repariere|behebe|"
    r"überarbeite|ueberarbeite|aktualisiere)\b",
    re.IGNORECASE,
)

_EXPLICIT_EDIT = re.compile(
    r"\b(?:ändere|aendere|bearbeite|ersetze|ergänze|ergaenze|"
    r"füge|fuege|lösche|loesche|verschiebe|rename|umbenenne|"
    r"implementiere|repariere|behebe|aktualisiere)\b",
    re.IGNORECASE,
)

_CONTENT_CREATION = re.compile(
    r"\b(?:erstelle|schreibe|formuliere|generiere|entwirf)\s+"
    r"(?:(?:mir|bitte)\s+)*(?:(?:ein|eine|einen|den|die|das)\s+)?"
    r"(?:(?:flux|bild|video|text2image|image|wan|sdxl)[-\s]?)?"
    r"(?:prompt|text|geschichte|beschreibung|idee|liste|anleitung|"
    r"zusammenfassung|antwort|konzept|beispiel|brief|e-?mail)\b",
    re.IGNORECASE,
)

_EXPLICIT_SAVE = re.compile(
    r"\b(?:speicher\w*|abspeicher\w*|ablegen|abspeichern|"
    r"als\s+datei|(?:in|unter)\s+(?:der|die|das|eine|einer)\s+datei|"
    r"lege\s+(?:ihn|sie|es|den\s+prompt)\s+(?:in|unter)\b|"
    r"(?:ins|im)\s+projekt\s+(?:schreiben|speichern|einfügen)|"
    r"datei\s+(?:erstellen|anlegen))\b",
    re.IGNORECASE,
)


def is_project_change_request(request: str) -> bool:
    """Return True only for a likely request to modify project files.

    An explicit save instruction overrides content-only wording. For instance,
    'Erstelle einen Prompt und speichere ihn als Datei' is a file operation,
    while 'Erstelle einen Prompt für eine Frau' is a normal chat request.
    """
    normalized = request.strip()
    if not normalized or _CHANGE_VERB.search(normalized) is None:
        return False

    if (
        (_CONTENT_CREATION.search(normalized) or _PROMPT_CREATION.search(normalized))
        and not _EXPLICIT_SAVE.search(normalized)
        and not _EXPLICIT_EDIT.search(normalized)
    ):
        return False

    return True

_PROMPT_CREATION = re.compile(
    r"^\s*(?:bitte\s+)?(?:erstelle|schreibe|formuliere|generiere|gib|"
    r"mach|entwirf|verfasse|brauche|benötige|benoetige)\b\s+"
    r"(?:(?:mir|bitte)\s+)*(?:(?:ein(?:en|e|es)?|den|die|das)\s+)?"
    r"(?:(?:gleichen|selben|letzten|vorherigen|neuen|weiteren|"
    r"erotischen|ausführlichen|detaillierten)\s+)?"
    r"(?:(?:flux|wan|bild|video|sdxl|comfyui)[-\s]?)?"
    r"(?:prompt|prompts|bildprompt|video-?prompt|flux-?prompt|wan-?prompt)\b"
    r"|^\s*(?:bitte\s+)?(?:ein(?:en|e|es)?\s+)?"
    r"(?:(?:flux|wan|bild|video|sdxl|comfyui)[-\s]?)?"
    r"(?:prompt|prompts|bildprompt|video-?prompt|flux-?prompt|wan-?prompt)\b"
    r"[\s\S]{0,70}?\b(?:für|fuer|zu|erstellen|formulieren|schreiben)\b",
    re.IGNORECASE,
)

_PRIOR_PROMPT_REFERENCE = re.compile(
    r"\b(?:vorherige[rsnm]?|vorige[rsnm]?|letzte[rsnm]?|"
    r"gleiche[rsnm]?|selbe[rsnm]?|vorhin|zuvor|oben|wie eben|"
    r"bereits|nochmal|nochmals|diesen|bestehenden|"
    r"überarbeite|ueberarbeite|ergänze|ergaenze)\b",
    re.IGNORECASE,
)


def is_creative_prompt_request(request: str) -> bool:
    """Detect explicit requests for a text prompt rather than project edits."""
    return bool(_PROMPT_CREATION.search(request)) and not is_project_change_request(request)


def is_standalone_prompt_request(request: str) -> bool:
    """New prompt with no dependency on an earlier chat turn."""
    return is_creative_prompt_request(request) and not _PRIOR_PROMPT_REFERENCE.search(request)


_LOCAL_READ_REQUEST = re.compile(
    r"\b(?:lies|lese|öffne|oeffne|analysiere|analysier|untersuche|prüfe|pruefe|"
    r"überprüfe|ueberpruefe|zeige|erkläre|erklaere|fasse|durchsuche)\b"
    r"[\s\S]{0,100}?\b(?:datei|dateien|ordner|verzeichnis|pfad|projekt|log|json|"
    r"quellcode|code|inhalt)\b",
    re.IGNORECASE,
)

_QUOTED_WINDOWS_PATH = re.compile(
    r"[\"']([A-Za-z]:[\\/][^\"']+)[\"']",
    re.IGNORECASE,
)

_BARE_WINDOWS_PATH = re.compile(
    r"(?<![A-Za-z0-9_])([A-Za-z]:[\\/][^\s,;]+)",
    re.IGNORECASE,
)


def is_local_read_request(request: str) -> bool:
    """Return True when the user explicitly asks Forge to inspect local content.

    General conversation and knowledge questions must stay projectless-capable.
    """
    normalized = request.strip()
    if not normalized:
        return False
    return bool(
        _LOCAL_READ_REQUEST.search(normalized)
        or _QUOTED_WINDOWS_PATH.search(normalized)
        or _BARE_WINDOWS_PATH.search(normalized)
    )


def extract_local_paths(request: str) -> list[str]:
    """Extract explicit absolute Windows paths without touching the filesystem."""
    matches: list[tuple[int, str]] = []
    quoted_spans: list[tuple[int, int]] = []
    for match in _QUOTED_WINDOWS_PATH.finditer(request):
        quoted_spans.append(match.span())
        matches.append((match.start(), match.group(1)))
    for match in _BARE_WINDOWS_PATH.finditer(request):
        if any(start <= match.start() < end for start, end in quoted_spans):
            continue
        matches.append((match.start(), match.group(1)))
    paths: list[str] = []
    for _, raw in sorted(matches, key=lambda item: item[0]):
        value = raw.strip().rstrip(".,;:!?)']}")
        if value and value not in paths:
            paths.append(value)
    return paths
