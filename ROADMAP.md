# Roadmap

## Erledigt

### Grundsystem
- Native Desktop-Grundoberfläche mit Chat, Terminal und Projektansicht
- Lokale Ollama-Kommunikation mit Streaming
- Workspace-Persistenz
- Dateindex und schreibgeschützter Dateiviewer
- Projektmodi und Aufgabenmodell
- ForgeBrain-Datenmodell und lokale Projektanalyse

### KI-Kontext
- Explizite KI-Freigaben für Dateien und Verzeichnisse
- Temporäre Session-Freigaben
- Begrenzung des Projektkontexts
- Modellabhängige Kontextbudgetierung
- Berücksichtigung von GPU-VRAM und System-RAM
- Übergabe von `num_ctx` an Ollama

### Änderungsworkflow
- Erkennung von Änderungsanfragen
- Strukturierte KI-Änderungsaktionen
- `ChangePreview` mit Vorschau der geplanten Änderung
- Bestätigungsworkflow vor dem tatsächlichen Schreiben
- Zentraler Schreibschutz über `confirmed=True`
- Unterstützung von `create`, `create_directory` und `replace`
- `replace` akzeptiert nur eindeutige Treffer
- Session-basierte Zugriffsfreigaben für den aktuellen Änderungsworkflow
- Der zuvor aufgetretene Windows-Absturz beim Schreibvorgang ist behoben

## Aktueller Entwicklungsstand

Der grundlegende KI-Änderungsworkflow ist implementiert:

`Anfrage → strukturierte Aktion → ChangePreview → Benutzerbestätigung → Apply → tatsächliches Schreiben`

Der Schwerpunkt liegt jetzt auf Stabilität, Tests, Dokumentationskonsistenz und einer sauberen Trennung der Verantwortlichkeiten.

## Nächste Ausbaustufen

### 1. Änderungsworkflow weiter absichern
- vollständige Tests für `create`
- vollständige Tests für `create_directory`
- vollständige Tests für `replace`
- Tests für nicht freigegebene Pfade
- Tests für Session-Freigaben
- Tests für bestätigte und nicht bestätigte Schreibvorgänge
- Tests für Projektwechsel und das Löschen von Session-Freigaben

### 2. Git- und Änderungsansicht
- detaillierte Git-Änderungsansicht
- verbesserte Diff-Darstellung
- klare Zuordnung zwischen vorgeschlagener und tatsächlich angewendeter Änderung

### 3. Editor
- interaktive Bearbeitung von Projektdateien
- berechtigungsgeprüfte Änderungen
- konsistente Verbindung zwischen Editor, ChangePreview und WorkspaceTools

### 4. ForgeBrain
- detaillierte Benutzeroberfläche zur Pflege und Auswertung des Projektwissens
- bessere Darstellung von Projektstruktur und Abhängigkeiten

### 5. Projektanalyse
- lokale Projektanalyse als optionaler, klar abgegrenzter Prozess
- weitere Optimierung des Analyse-Kontexts
- bessere Kontrolle über Analyseumfang und Kontextbudget

### 6. Kontextbezogene KI-Werkzeuge
- weitere Werkzeuge für Lesen, Suchen und Analysieren
- konsequente Beachtung des jeweiligen Projektmodus
- klare Trennung zwischen Lesezugriff, Änderungsvorschlag und Schreibzugriff

## Entwicklungsregel

Neue Funktionalität wird erst implementiert, nachdem:

1. der aktuelle Projektstand geprüft wurde
2. die relevante Dokumentation geprüft wurde
3. die betroffenen Dateien identifiziert wurden
4. die geplante Änderung festgelegt wurde

Nach einer funktionalen Änderung:

1. testen
2. `docs/CURRENT_STATE.md` aktualisieren
3. relevante Dokumentation aktualisieren
4. `git diff` und `git diff --check` prüfen
5. committen
6. pushen
