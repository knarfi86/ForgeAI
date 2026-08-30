# ForgeAI – Current State

## Git

- Branch: `forgeai-dev`
- Referenz-Commit: `6794ede`
- Commit: `Remove temporary backup files`
- Repository: `knarfi86/ForgeAI`

## Aktueller Funktionsstand

ForgeAI ist eine lokale Windows-Desktopanwendung auf Basis von PySide6 und Ollama.

Aktuell implementiert sind:

- lokale Ollama-Kommunikation
- Chat mit Streaming
- Projektöffnung und lokale Projektanalyse
- Projektdateiindex
- KI-Freigaben für Dateien und Ordner
- Session-basierte temporäre KI-Freigaben
- Erkennung von Änderungsanfragen
- strukturierte Änderungsaktionen des Modells
- Erzeugung von `ChangePreview`-Objekten
- Anzeige von Änderungsvorschlägen
- bestätigtes Anwenden von Änderungen
- zentraler Schreibschutz über `confirmed=True`
- eindeutige Prüfung bei `replace`-Operationen
- modellabhängige Kontextbudgetierung
- Erkennung von GPU-VRAM und System-RAM
- Übergabe von `num_ctx` an Ollama
- begrenzter Projektkontext für das lokale Modell

Der zuvor aufgetretene Windows-Absturz beim Schreibvorgang ist behoben. Er gilt derzeit nicht als offenes Problem.

## Änderungsworkflow

Der aktuelle Ablauf ist:

1. Benutzer stellt eine Änderungsanfrage.
2. `MainWindow` erkennt die Anfrage als Action.
3. Das Modell liefert strukturierte Änderungsaktionen.
4. `extract_change_previews()` verarbeitet die Aktionen.
5. `WorkspaceTools` erzeugt daraus `ChangePreview`-Objekte.
6. Die Vorschauen werden in der UI als ausstehende Änderungen gespeichert.
7. Die UI zeigt den Änderungsvorschlag.
8. Erst nach expliziter Benutzerbestätigung wird die Änderung angewendet.
9. `_apply_change_previews()` ruft `WorkspaceTools.apply(..., confirmed=True)` auf.
10. `WorkspaceTools` übergibt die bestätigte Änderung an `FileSystem`.
11. `FileSystem` erlaubt schreibende Operationen nur mit `confirmed=True`.

Damit sind Änderungsvorschlag und tatsächlicher Schreibzugriff voneinander getrennt.

## Unterstützte KI-Änderungsaktionen

Aktuell unterstützt `change_actions.py`:

- `create`
- `create_directory`
- `replace`

Bei `replace` müssen `old` und `new` als Text angegeben werden.

Eine `replace`-Operation wird nur akzeptiert, wenn der gesuchte Text exakt einmal in der Datei vorkommt.

Aktuelles Verhalten:

- 0 Treffer → Fehler
- 1 Treffer → Änderungsvorschau
- mehr als 1 Treffer → Fehler

Mehrdeutige Änderungen werden damit nicht automatisch angewendet.

## KI-Freigaben

KI-Lesefreigaben werden projektbezogen gespeichert.

Es gibt:

- persistente Freigaben für Dateien
- persistente Freigaben für Verzeichnisse
- temporäre Session-Freigaben

`AIContextProvider` liest ausschließlich freigegebene lokale Dateien und begrenzt den übertragenen Kontext.

Die Session-Freigaben werden beim Schließen des Projekts gelöscht.

## Projektmodi

Aktuell existieren:

- `READ_ONLY`
- `PROPOSE`
- `WRITE_WITH_CONFIRMATION`
- `AUTO_WRITE`

Der aktuelle Test- und Entwicklungsworkflow verwendet:

`WRITE_WITH_CONFIRMATION`

`AUTO_WRITE` ist vorhanden, aber nicht Bestandteil des normalen bestätigungspflichtigen Workflows.

## Kontext und Ollama

ForgeAI ermittelt den vom Modell gemeldeten nativen Kontext und berechnet abhängig von:

- Modellgröße
- GPU-VRAM
- verfügbarem System-RAM
- nativer Modell-Kontextgröße

einen konservativen empfohlenen Kontextwert.

Der berechnete Wert wird als `num_ctx` an die lokale Ollama-API übergeben.

Der Projektkontext wird durch `AIContextProvider` begrenzt und nur aus explizit freigegebenen Dateien aufgebaut.

## Dokumentationsstand

Die Dokumentation wurde zuletzt gegen den aktuellen Code von `forgeai-dev` geprüft.

Aktuell synchronisiert:

- `ARCHITECTURE.md`
- `ROADMAP.md`
- `docs/CURRENT_STATE.md`

`README.md` beschreibt weiterhin den allgemeinen Projektumfang und wird bei relevanten funktionalen Änderungen auf Konsistenz geprüft.

## Wichtige Dateien

- `forgeai/ui/main_window.py`
  - UI
  - Action-Erkennung
  - ChangePreview-Verarbeitung
  - Bestätigungsworkflow
  - Aufbau des Modellkontexts

- `forgeai/ai/change_actions.py`
  - Verarbeitung strukturierter KI-Änderungsaktionen
  - Erzeugung von Change Previews

- `forgeai/core/workspace_tools.py`
  - Datei-Lese-, Such- und Änderungsoperationen
  - `ChangePreview`
  - Apply-Logik

- `forgeai/core/filesystem.py`
  - zentraler Dateizugriff
  - Schreibschutz durch `confirmed=True`

- `forgeai/core/workspace_manager.py`
  - aktives Projekt
  - Projektmodus
  - persistente KI-Freigaben
  - Session-Freigaben

- `forgeai/core/ai_context.py`
  - Aufbau des begrenzten Projektkontexts
  - Auflösung expliziter KI-Freigaben

- `forgeai/ai/ollama_client.py`
  - lokale Ollama-Kommunikation
  - Hardware-Erkennung
  - Modellgröße
  - Kontextlänge
  - Kontextbudgetierung
  - `num_ctx`

## Entwicklungsregeln

Vor jeder Codeänderung:

1. aktuelle Dokumentation prüfen
2. aktuellen Code prüfen
3. Abweichungen feststellen
4. geplante Änderung festlegen
5. erst danach Code ändern

Nach jeder funktionalen Änderung:

1. testen
2. `CURRENT_STATE.md` aktualisieren
3. relevante Dokumentation aktualisieren
4. `git diff` prüfen
5. committen
6. pushen

## Aktueller nächster Arbeitsschritt

Vor der nächsten funktionalen Codeänderung:

1. `ARCHITECTURE.md` aktualisieren
2. `ROADMAP.md` aktualisieren
3. `README.md` auf relevante Abweichungen prüfen
4. Dokumentations-Diff prüfen
5. Dokumentationsänderungen committen

Erst danach wird die nächste technische Änderung am Code begonnen.

Der zuvor behobene Windows-Absturz ist abgeschlossen und wird nicht erneut als offenes Problem behandelt, solange er nicht wieder auftritt.
