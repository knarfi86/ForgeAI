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


## Mehrstufige Projektanalyse

### Geplant

Die bestehende deterministische Projektanalyse soll um eine lokale LLM-
Gegenanalyse erweitert werden.

Ziel ist eine Analyse, bei der das LLM nicht die objektive Projektanalyse
ersetzt, sondern sie überprüft, Schwachstellen erkennt und Verbesserungen
vorschlägt.

Geplant:

- [ ] LLM-Gegenanalyse auf Basis der deterministischen `ProjectAnalyzer`-Analyse
- [ ] konfigurierbare Anzahl von Analyse-Runden
- [ ] Standardwert: 2 Runden
- [ ] vollständige Deaktivierung der Prüfung
- [ ] technische Obergrenze: 7 Runden
- [ ] LLM prüft und korrigiert die vorherige Analyse
- [ ] Übergabe der korrigierten Analyse an die nächste Runde
- [ ] optionaler Modellwechsel zwischen Analyse-Runden
- [ ] unabhängige Prüfung durch ein zweites Modell
- [ ] Konsolidierung der Ergebnisse zu einer finalen Analyse
- [ ] Speicherung der finalen Analyse über `ForgeBrain`
- [ ] Anzeige des Analyseverlaufs bzw. des finalen Ergebnisses in der UI
- [ ] Einstellungen für Rundenzahl und verwendete Prüfmodelle

### Zielbild

Die Analyse soll nach dem Prinzip arbeiten:

`ForgeAI Basisanalyse`
→ LLM Prüfung
→ Korrektur
→ erneute Prüfung
→ weitere Korrektur
→ optional anderes Modell
→ konsolidierte Analyse

Die Anzahl der Runden soll nicht fest im Code verdrahtet werden. Der Benutzer soll sie über das Einstellungsmenü bestimmen können.
Die Prüfung muss außerdem vollständig deaktivierbar sein.

Die Möglichkeit, zwischen den Runden ein anderes Modell einzusetzen, soll
bewusst unterstützt werden. Unterschiedliche Modelle können unterschiedliche
Schwachstellen erkennen und reduzieren dadurch das Risiko, dass ein einzelnes
Modell seine eigene fehlerhafte Interpretation mehrfach bestätigt.

Die deterministische Analyse bleibt dabei die faktische Grundlage. Das LLM
liefert zusätzliche Interpretation, Prüfung und Verbesserung.

## Mehrstufiger Coding-Agent

### Zielbild

Der Coding-Agent soll Änderungen nicht nur generieren, sondern deren Lösungsweg
kritisch prüfen, die Umsetzung verifizieren und bei Fehlern gezielt reparieren.

Der geplante Ablauf lautet:

`PLAN`
→ `REVIEW`
→ `REVISE`
→ `USER APPROVAL`
→ `EXECUTE`
→ `TEST`
→ `ANALYZE`
→ `REPAIR`
→ `REVIEW`
→ `EXECUTE`
→ `TEST`
→ ...

### Review

Die Review-Schleife ist optional.

Konfiguration:

- `review_enabled`: Standard `true`
- `review_max_rounds`: Standard `2`
- Minimum: `1`
- Maximum: `7`

Die Schleife endet vorzeitig, sobald der Plan akzeptiert wurde.

Die Review prüft insbesondere Architektur, Anforderungen, Nebenwirkungen,
Berechtigungen und Testabdeckung.

### Repair

Die Reparaturschleife ist ebenfalls optional.

Konfiguration:

- `repair_enabled`: Standard `true`
- `repair_max_attempts`: Standard `2`
- Minimum: `1`
- Maximum: `7`

Die Reparatur startet nur aufgrund eines konkreten Verifikationsergebnisses.

### Tests

Tests bleiben unabhängig von Review und Repair.

ForgeAI soll mindestens folgende Zustände unterscheiden:

- `PASS`
- `FAIL`
- `ERROR`
- `SKIPPED`
- `BLOCKED`

Review darf deaktiviert werden, ohne die Tests zu deaktivieren.
Repair darf ebenfalls unabhängig von den Tests aktiviert oder deaktiviert
werden.

### Geplante Komponenten

- [ ] Planner für strukturierte Änderungspläne
- [ ] Review-Komponente für kritische Gegenprüfung
- [ ] konfigurierbare Review-Runden bis maximal 7
- [ ] vollständige Deaktivierung der Review
- [ ] Benutzerfreigabe zwischen Plan und Ausführung
- [ ] standardisierter Verifikationslauf
- [ ] Fehleranalyse nach fehlgeschlagenen Tests
- [ ] Repair-Komponente
- [ ] konfigurierbare Repair-Versuche bis maximal 7
- [ ] vollständige Deaktivierung der automatischen Reparatur
- [ ] erneute Review nach Reparatur
- [ ] Speicherung von `task_id`, `review_round`, `execution_round`,
      `repair_attempt` und `git_commit`
- [ ] Speicherung der Roh-Testberichte
- [ ] UI für Review-, Test- und Reparaturverlauf
- [ ] Unterstützung unterschiedlicher Modelle für getrennte Review-Runden

Die Rundengrenzen werden als Konfiguration umgesetzt und nicht fest in die
einzelnen Agent-Komponenten eingebaut.