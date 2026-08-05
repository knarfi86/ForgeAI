# Aufgabenverwaltung

Aufgaben werden vollständig lokal in SQLite gespeichert und immer einem Projekt zugeordnet.

| Feld | Beschreibung |
|---|---|
| Titel | Kurzbezeichnung der Aufgabe |
| Beschreibung | Freitext zur Aufgabe |
| Priorität | `LOW`, `MEDIUM`, `HIGH` oder `CRITICAL` |
| Status | `TODO`, `IN_PROGRESS`, `BLOCKED` oder `DONE` |
| Betroffene Dateien | JSON-Liste relativer Dateipfade |
| Erstellt am | Zeitstempel der Anlage |
| Abgeschlossen am | Zeitstempel bei Status `DONE` |

Die aktuelle Oberfläche erlaubt das Anlegen und Abschließen von Aufgaben über **Werkzeuge → Aufgaben**. Die weiteren Statuswerte und betroffenen Dateien sind bereits Teil des Datenmodells für die nächste UI-Ausbaustufe.
