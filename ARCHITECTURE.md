# Architektur

ForgeAI ist eine native PySide6-Desktopanwendung. `main.py` erstellt die Qt-Anwendung, `ForgeAIApplication` initialisiert Konfiguration, Logging und die SQLite-Datenbank. `MainWindow` ist die UI-Komposition: Es verbindet Widgets mit fachlichen Diensten, ohne Index- oder Persistenzlogik selbst zu enthalten.

## Kernmodule

| Modul | Verantwortung |
|---|---|
| `WorkspaceManager` | aktives Projekt, Öffnen/Schließen, Favoriten, Projektmodus und KI-Freigaben |
| `FileIndexer` | rekursive Metadatenindexierung unterstützter Textdateien und Ordner |
| `WorkspaceDatabase` | SQLite-Schema für Workspace, Index, Aufgaben und Wissen |
| `TaskManager` | Erstellen, Abfragen und Abschließen lokaler Aufgaben |
| `ForgeBrain` | dauerhaftes, KI-unabhängiges Projektwissen |
| `FileViewer` | schreibgeschützte Text- und Codeansicht mit leichter Hervorhebung |
| `FileSystem` | zentraler kontrollierter Zugriff auf lokale Projektdateien |
| `WorkspaceTools` | Lese-, Such- und Änderungswerkzeuge einschließlich `ChangePreview` |
| `AIContextProvider` | Aufbau des begrenzten, freigegebenen Projektkontexts |
| `OllamaClient` | lokale Kommunikation mit Ollama und Kontextbudgetierung |

`Database` bleibt die kleine, allgemeine SQLite-Basis für Chatverlauf und Einstellungen. `WorkspaceDatabase` erweitert diese Basis, statt die bestehende Chat-Persistenz zu ersetzen.

## Sicherheit und Projektmodi

`ProjectMode` definiert:

- `READ_ONLY`
- `PROPOSE`
- `WRITE_WITH_CONFIRMATION`
- `AUTO_WRITE`

Der aktuelle Test- und Entwicklungsworkflow verwendet `WRITE_WITH_CONFIRMATION`.

Der Modus wird pro aktivem Projekt gespeichert.

Schreibende Dateioperationen werden zentral über `FileSystem` geschützt. Schreiben, Umbenennen, Löschen und Verzeichnisoperationen benötigen eine explizite Bestätigung über `confirmed=True`.

## Änderungsworkflow

KI-Änderungen werden nicht unmittelbar geschrieben.

Der Ablauf ist:

1. Der Benutzer stellt eine Änderungsanfrage.
2. `MainWindow` erkennt die Anfrage als Action.
3. Das Modell liefert strukturierte Änderungsaktionen.
4. `change_actions.py` verarbeitet die Aktionen.
5. `WorkspaceTools` erzeugt daraus `ChangePreview`-Objekte.
6. Jede Änderung wird zunächst als Vorschau mit Unified Diff dargestellt.
7. Der Benutzer bestätigt oder verwirft die Änderung.
8. Nur eine bestätigte Änderung wird über `WorkspaceTools.apply(..., confirmed=True)` angewendet.
9. `FileSystem` führt den tatsächlichen Schreibvorgang aus.

Aktuell unterstützte Änderungsaktionen:

- `create`
- `create_directory`
- `replace`

`replace` wird nur akzeptiert, wenn der gesuchte Text exakt einmal vorhanden ist.

Aktuelles Verhalten:

- 0 Treffer → Fehler
- 1 Treffer → Änderungsvorschau
- mehr als 1 Treffer → Fehler

Mehrdeutige Ersetzungen werden nicht automatisch angewendet.

## Lokale Daten

Anwendungsdaten liegen in `%USERPROFILE%\.forgeai`.

Dazu gehören unter anderem:

- SQLite-Datenbank
- Chatverlauf und Einstellungen
- Logs
- Workspace-Zustand
- KI-Freigaben
- Aufgaben
- ForgeBrain-Projektwissen

Projektdateien bleiben lokal auf dem Rechner des Benutzers.

## Workspace und Selbstanalyse

`WorkspaceManager` erzeugt beim Öffnen eines lokalen Projektordners einen Workspace, aktualisiert die Liste zuletzt geöffneter Projekte und indexiert die zulässigen Dateitypen.

Der Index speichert pro Datei relativen Pfad, Sprache, Größe, Änderungsdatum und SHA-256-Hash in SQLite.

`ProjectAnalyzer` liest die bekannten Projektdokumente lokal und analysiert Python-Quellen mit dem Python-Standardmodul `ast`.

Die dauerhafte ForgeBrain-Analyse enthält Dateien, Ordner, Module, Klassen, Importe, den Abhängigkeitsgraphen, Sprachen, Git-Status, Dokumente und offene Aufgaben.

Öffnet ForgeAI seinen eigenen Projektordner, wird diese Analyse automatisch erstellt und als Selbstanalyse markiert.

## KI-Freigaben

`ai_access_grants` speichert pro Projekt explizit freigegebene Dateien und Ordner.

`ProjectPanel` ermöglicht Freigabe und Widerruf direkt aus dem Dateibaum; eine Dialogbestätigung ist erforderlich.

`WorkspaceManager` unterstützt zusätzlich temporäre Session-Freigaben. Diese gelten nur für die aktuelle Projektsitzung und werden beim Schließen des Projekts entfernt.

`AIContextProvider` löst die Freigaben auf, liest ausschließlich zugelassene lokale Dateien und begrenzt den übertragenen Kontext.

## KI-Kontext

`AIContextProvider` baut den Projektkontext ausschließlich aus explizit freigegebenen lokalen Dateien auf.

Der Kontext wird abhängig vom verfügbaren Modellkontext begrenzt.

Analyseanfragen können einen speziell begrenzten Projektkontext verwenden und typische Noise-Verzeichnisse ausschließen.

## KI-Kommunikation

`MainWindow.send_message` übergibt Chatnachrichten an `OllamaClient.stream_chat`.

Der daraus erzeugte `OllamaStreamWorker` sendet einen JSON-POST an die feste lokale Ollama-Route `http://localhost:11434/api/chat` und verarbeitet den NDJSON-Stream.

`OllamaClient` lehnt jeden anderen Endpunkt ab; die URL-Einstellung ist schreibgeschützt.

Es gibt keine Cloud-Client-Bibliothek und keinen alternativen Antwortpfad.

## Kontextbudgetierung

`OllamaClient` ermittelt den nativen Kontext des verwendeten Modells und berücksichtigt bei der Berechnung des empfohlenen Kontextbudgets:

- Modellgröße
- GPU-VRAM
- verfügbaren System-RAM
- native Modell-Kontextgröße

Der berechnete Wert wird als `num_ctx` an die lokale Ollama-API übergeben.

## Architekturprinzip

Die Verantwortlichkeiten sind bewusst getrennt:

`MainWindow`
→ erkennt Benutzerabsicht und steuert den UI-Workflow

`change_actions.py`
→ verarbeitet strukturierte KI-Aktionen

`WorkspaceTools`
→ erzeugt und verarbeitet Änderungsvorschauen

`WorkspaceManager`
→ verwaltet Projektzustand und KI-Freigaben

`AIContextProvider`
→ stellt ausschließlich freigegebenen Projektkontext bereit

`FileSystem`
→ kontrolliert den tatsächlichen Dateizugriff

`OllamaClient`
→ kommuniziert ausschließlich mit der lokalen Ollama-Instanz

Dadurch sind KI-Vorschlag, Benutzerbestätigung, Freigabeprüfung und tatsächlicher Schreibzugriff voneinander getrennt.
