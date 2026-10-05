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
        _CONTENT_CREATION.search(normalized)
        and not _EXPLICIT_SAVE.search(normalized)
        and not _EXPLICIT_EDIT.search(normalized)
    ):
        return False

    return True