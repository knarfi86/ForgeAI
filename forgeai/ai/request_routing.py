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


_TOOL_EXECUTION_COMMAND = re.compile(
    r"^\s*(?:bitte\s+)?(?:prüfe|pruefe|überprüfe|ueberpruefe|"
    r"teste|test|kompiliere|compile|starte)\b",
    re.IGNORECASE,
)

_TOOL_EXECUTION_TARGET = re.compile(
    r"\b(?:syntax\w*|python[-\s]?interpreter|"
    r"interpreter|pytest|python\s+(?:compile|compiler)|kompilier\w*)\b",
    re.IGNORECASE,
)

_TOOL_EXECUTION_PHRASE = re.compile(
    r"\b(?:pytest|tests?|python)\b[\s\S]{0,80}?"
    r"\b(?:ausführen|ausfuehren|starten|laufen\s+lassen|run|execute|kompilieren)\b"
    r"|\b(?:führe|fuehre|starte|run|execute)\b[\s\S]{0,80}?"
    r"\b(?:pytest|tests?|python|compiler|interpreter)\b",
    re.IGNORECASE,
)

_PROJECT_TOOL_TARGET = re.compile(
    r"\b(?:projekt|syntax\w*|pytest|tests?|kompilier\w*)\b",
    re.IGNORECASE,
)


def is_tool_execution_request(request: str) -> bool:
    """Return True for explicit requests to execute a deterministic local tool.

    Analysis words such as ``prüfe`` are ambiguous in normal language.  Forge
    therefore routes them into the Agent/plugin workflow only when the request
    also names an executable target such as Python syntax, pytest, compilation
    or the interpreter.  Pure explanation/architecture requests remain chat
    analysis.
    """
    normalized = request.strip()
    if not normalized:
        return False
    if _TOOL_EXECUTION_PHRASE.search(normalized):
        return True
    return bool(
        _TOOL_EXECUTION_COMMAND.search(normalized)
        and _TOOL_EXECUTION_TARGET.search(normalized)
    )


def tool_execution_requires_project(request: str) -> bool:
    """Return whether the current deterministic tool workflow needs a project.

    The current Python verification profile includes project-source compilation,
    so every executable Python tool action is project-bound for now. A future
    action-specific verification profile may safely re-enable projectless
    interpreter inspection.
    """
    return is_tool_execution_request(request)


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

_BARE_WINDOWS_FILE_PATH = re.compile(
    r'(?<![A-Za-z0-9_])('
    r'[A-Za-z]:[\\/]'
    r'(?:[^<>:"|?*\r\n,;\\/]+[\\/])*'
    r'[^<>:"|?*\r\n,;\\/]*?\.[A-Za-z0-9_-]{1,16}'
    r')(?=$|\s|[.,;!?)}\]])',
    re.IGNORECASE,
)

_BARE_WINDOWS_PATH_START = re.compile(
    r"(?<![A-Za-z0-9_])([A-Za-z]:[\\/])",
    re.IGNORECASE,
)

_PATH_CLAUSE_BOUNDARY = re.compile(
    r"\s+(?=(?:und|oder|bitte|lies|lese|analysiere|analysier|"
    r"untersuche|prüfe|pruefe|überprüfe|ueberpruefe|zeige|erkläre|"
    r"erklaere|öffne|oeffne)\b)",
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
        or _BARE_WINDOWS_PATH_START.search(normalized)
    )


def extract_local_paths(request: str) -> list[str]:
    """Extract explicit absolute Windows paths without touching the filesystem.

    Quoted paths remain the least ambiguous form. Bare file paths may contain
    spaces and are captured through their filename extension. Bare directory
    paths may also contain spaces; common instruction/conjunction words end the
    path instead of the first whitespace character.
    """
    matches: list[tuple[int, str]] = []
    occupied_spans: list[tuple[int, int]] = []

    for match in _QUOTED_WINDOWS_PATH.finditer(request):
        occupied_spans.append(match.span())
        matches.append((match.start(), match.group(1)))

    for match in _BARE_WINDOWS_FILE_PATH.finditer(request):
        if any(span_start <= match.start() < span_end for span_start, span_end in occupied_spans):
            continue
        occupied_spans.append(match.span())
        matches.append((match.start(), match.group(1)))

    for match in _BARE_WINDOWS_PATH_START.finditer(request):
        if any(span_start <= match.start() < span_end for span_start, span_end in occupied_spans):
            continue
        path_start = match.start(1)
        tail = request[path_start:]
        tail = re.split(r"[\r\n,;]", tail, maxsplit=1)[0]
        tail = _PATH_CLAUSE_BOUNDARY.split(tail, maxsplit=1)[0]
        value = tail.strip().rstrip(".,;:!?)']}")
        if value:
            matches.append((path_start, value))

    paths: list[str] = []
    for _, raw in sorted(matches, key=lambda item: item[0]):
        value = raw.strip().rstrip(".,;:!?)']}")
        if value and value not in paths:
            paths.append(value)
    return paths
