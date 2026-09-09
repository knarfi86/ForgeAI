# ForgeAI – Current State

## Git

- Branch: `temp/agent-workflow-current`
- Repository: `knarfi86/ForgeAI`
- Die Dokumentation beschreibt den zuletzt geprüften Entwicklungsstand.
- Die exakte Commit-Historie wird durch Git geführt und nicht manuell in dieser Datei gepflegt.

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

Die Dokumentation wurde zuletzt gegen den aktuellen Code des Branches `temp/agent-workflow-current` geprüft.

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


## Projektanalyse

Die aktuelle Projektanalyse ist deterministisch und benötigt grundsätzlich
kein LLM.

`ProjectAnalyzer` wertet lokale Projektinformationen aus, darunter Dateien,
Ordner, Python-Module, Klassen, Funktionen, Imports, Sprachen und
Projektmetadaten.

Die Analyse wird über `ForgeBrain` gespeichert.

### Geplante LLM-Gegenanalyse

Die deterministische Analyse soll künftig durch eine mehrstufige lokale
LLM-Gegenanalyse ergänzt werden.

Geplant ist:

- konfigurierbare Anzahl von Analyse-Runden
- Standardwert: 2 Runden
- Prüfung kann vollständig deaktiviert werden
- technische Obergrenze: 7 Runden
- LLM prüft die Basisanalyse
- erkannte Schwachstellen werden korrigiert
- die korrigierte Analyse wird erneut geprüft
- optional kann ein anderes Modell als unabhängiger Prüfer eingesetzt werden
- am Ende entsteht eine konsolidierte Analyse

Die LLM-Prüfung ersetzt `ProjectAnalyzer` nicht. Sie baut auf dessen
objektiver Analyse auf und ergänzt diese um Interpretation und Gegenprüfung.

Diese Funktion ist derzeit **noch nicht implementiert**.

## Ollama-Architektur

Die Ollama-Kommunikation ist auf `forgeai.ai.ollama_client.OllamaClient`
zentralisiert.

Die früheren `OllamaManager`-Implementierungen wurden entfernt.

Aktuelle produktive Stellen verwenden:

- `forgeai/ai/ollama_client.py`
- `OllamaClient.list_models()`
- `OllamaClient.get_context_length()`
- `OllamaClient.recommend_context_length()`
- `OllamaClient.stream_chat()`
- `OllamaClient.generate()`
- `OllamaClient.analyze_project()`

`WorkspaceManager`, `MainWindow`, `SettingsDialog` und `CodeAgent`
verwenden damit dieselbe zentrale Ollama-Schnittstelle.

## Verifizierter Teststand

Der zuletzt vollständig ausgeführte und verifizierte Testlauf stammt vom
2. September 2026.

- `compileall`: PASS
- `git diff --check`: PASS
- `pytest`: **230/230 PASS**
- Python: 3.11.9
- pytest: 9.1.1

Diese Angaben beschreiben den zuletzt tatsächlich ausgeführten
vollständigen PASS-Testlauf.

Der automatisch synchronisierte Dokumentationsblock kann inzwischen eine
höhere Anzahl gesammelter Tests ausweisen. Diese Zahl beschreibt die aktuell
erkannte Testmenge und ist nicht automatisch ein bestätigter PASS-Lauf.

Die Tests umfassen unter anderem Agent Contracts, Agent State, Agent Planner,
Agent Reviewer, Agent Orchestrator, ModelRouter, OllamaProvider, OllamaClient,
AIContextProvider, WorkspaceManager, WorkspaceTools, FileSystem,
ProjectAnalyzer und FileIndexer.

## Agentenstatus

Der Agentenbereich ist technisch weitgehend implementiert, befindet sich aber
noch in der Integrationsphase.

Die einzelnen Komponenten für Planung, Review, Analyse, Verifikation und
Reparatur existieren und sind durch eigene Tests abgesichert.

Implementiert sind:

- `ModelRouter`
- `AgentState` und `AgentRun`
- `AgentTask`, `AgentPlan` und `ReviewResult`
- `AgentPlanner`
- `AgentReviewer`
- `AgentOrchestrator`
- `AgentVerificationWorker`
- `AgentAnalyzer`
- `AgentRepairer`
- `AgentRecoveryWorker`
- `ANALYZING`-Zustand
- `REPAIRING`-Zustand
- Reparaturplan-Review
- erneute Reparaturversuche nach `REVISE`
- Abbruch bei `REJECT`
- übergang eines akzeptierten Reparaturplans zur Benutzerfreigabe
- Begrenzung der Reparaturversuche über `AgentRun`
- optionaler externer Planner als rein beratende Quelle

Aktuelle Standardwerte in `AgentRun` sind:

- `max_review_rounds = 3`
- `max_repair_attempts = 3`

### Status der Integration

Implementiert und getestet sind die einzelnen Agenten- und
Recovery-Komponenten.

Teilintegriert ist die vollständige End-to-End-Verkettung des Agentenplans
mit dem bestehenden ChangePreview-, Apply- und Test-Workflow.

Damit gilt:

- **Agent-Komponenten:** implementiert
- **Recovery-Komponenten:** implementiert
- **End-to-End-Agentenworkflow:** teilweise integriert


## Dokumentationsregel

Bei jedem funktionalen Commit wird geprüft, ob folgende Dokumente an den
aktuellen Entwicklungsstand angepasst werden müssen:

- `docs/CURRENT_STATE.md`
- `ARCHITECTURE.md`
- `ROADMAP.md`
- `docs/AGENT_REALITY_MODEL.md`

Dokumentation und betroffener Code werden vor dem Commit gemeinsam geprüft.
`CURRENT_STATE.md` beschreibt den zuletzt geprüften Stand; die Commit-Historie
selbst bleibt Aufgabe von Git.

## Agent Reality Model

`docs/AGENT_REALITY_MODEL.md` definiert die konzeptionelle Grundlage für die
modellunabhängige Agentenrealität.

`AgentRun` ist dabei als zentraler Laufzeitanker für Task, State und History
festgelegt. Der geplante Reality Layer verbindet diese Informationen mit
Context, Knowledge, Authority, Observation, Evidence und Verification, ohne
die bestehenden Verantwortlichkeiten in einem God Object zusammenzuführen.

### Implementierter Reality-Layer-Kern

Der erste technische Schnitt des Agent Reality Layers ist implementiert:

- `forgeai/core/agent_reality.py`
- `tests/core/test_agent_reality.py`

Der Kern enthält strukturierte Dataclasses für Identity, Task, Run, Context,
Knowledge, Memory, Capability, Authority, Observation, Evidence, Uncertainty,
Decision, Action, Verification und Event sowie die zugehörigen Enums.

Der Implementierungsstand ist durch 4 Unit-Tests abgesichert.

`AgentRun` bleibt der autoritative Laufzeitanker. `AgentReality` ist eine
Integrations- und Snapshot-Struktur und übernimmt nicht die Zuständigkeiten
von `WorkspaceManager`, `ForgeBrain`, `FileSystem`, `WorkspaceTools` oder
Verification.

Die Anbindung an die bestehenden Laufzeitkomponenten erfolgt in einem
separaten Integrationsschritt.

### Reality-Layer-Projektion von AgentRun

`RunReality.from_agent_run()` erzeugt eine strukturierte Reality-Projektion
aus dem autoritativen `AgentRun`.

Die Projektion übernimmt:
- aktuellen `AgentState`
- Review-, Execution- und Repair-Zähler
- maximale Review- und Repair-Runden
- History
- Metadata
- Revision Context

History, Metadata und Revision Context werden für die Projektion kopiert.
Die Reality-Projektion verändert dadurch den ursprünglichen `AgentRun` nicht.

Die bestehende Ownership bleibt erhalten:
`AgentRun` ist weiterhin autoritativ für den Laufzeitstatus.

### AgentTask- und AgentRun-Projection

Der Reality Layer kann nun sowohl `AgentTask` als auch `AgentRun` strukturiert
abbilden.

`TaskReality.from_agent_task()` erzeugt eine Projection aus dem autoritativen
`AgentTask`.

`RunReality.from_agent_run()` erzeugt eine Projection aus dem autoritativen
`AgentRun`.

`AgentReality.from_task_and_run()` verbindet beide Projektionen mit einer
`AgentIdentity` zu einer gemeinsamen Reality-Sicht.

Dabei bleibt `AgentTask` bzw. `AgentRun` jeweils die autoritative Quelle.
Die erzeugten Reality-Objekte sind Projektionen und verändern die
Ausgangsobjekte nicht.

`TaskReality.project_path` behält die Semantik von `AgentTask.project_path`
bei und bleibt daher optional (`str | None`).

### AgentOrchestrator-Reality-Anbindung

`AgentOrchestrator` kann optional eine `AgentReality`-Instanz erhalten.
Nach relevanten Zustandsübergängen wird der autoritative `AgentRun` an
`AgentReality.record_run_state()` übergeben und dadurch als `AgentEvent`
aufgezeichnet.

Damit bleibt `AgentRun` die Runtime Authority, während der Reality Layer
eine zeitliche Beobachtung der Workflow-Zustände führt.

### Reality-Layer-Event-Projektion

<!-- FORGE:AUTO:CURRENT_STATE:START -->
### Automatisch synchronisierter Arbeitsstand

#### Aktuell geänderte Dateien

- `forgeai/core/ai_context.py`
- `forgeai/ui/main_window.py`
- `tests/test_ai_context.py`

#### Teststand

- Pytest-Testfaelle: **250**

#### Aktueller Plan

- [ ] vollständige End-to-End-Verbindung von AgentPlan zu ChangePreview
- [ ] vollständige automatische Ausführung nach akzeptiertem Plan
- [ ] vollständige Rückkopplung von Testresultaten in den Orchestrator
- [ ] vollständige Recovery-Ausführung über mehrere Reparaturrunden
- [ ] persistente Nachvollziehbarkeit von `task_id`, `review_round`, `execution_round`, `repair_attempt` und `git_commit`
- [ ] Speicherung vollständiger Roh-Testberichte
- [ ] UI für Review-, Test- und Reparaturverlauf
- [ ] gezielte Unterstützung unterschiedlicher Modelle für getrennte Review-Runden
- [ ] vollständige ForgeBrain-Anbindung des Agentenverlaufs

#### Agentenstatus

- `AgentRun`: **implementiert**
- `AgentPlanner`: **implementiert**
- `AgentReviewer`: **implementiert**
- `AgentOrchestrator`: **implementiert**
- `AgentVerificationWorker`: **implementiert**
- `AgentAnalyzer`: **implementiert**
- `AgentRepairer`: **implementiert**
- `AgentRecoveryWorker`: **implementiert**
- `AgentReality`: **implementiert**
- `Plan -> Review -> Approval`: **integriert**
- `Approval -> Execute -> Test`: **teilintegriert**
- `Test -> Analyze -> Repair -> Review`: **integriert im Recovery-Pfad**
- `vollstaendiger End-to-End-Agentenworkflow`: **teilintegriert**
- `AgentReality-Anbindung`: **teilintegriert**

#### Letzte relevante Commits

- `68b9865 (HEAD -> temp/agent-workflow-current, origin/temp/agent-workflow-current) refactor: centralize AI access and add project structure context`
- `09eaa4d fix: improve analysis routing and project context relevance`
- `b71de7a test: protect analysis from change preview pipeline`
- `923a4c1 fix: stabilize agent no-op and verification recovery`
- `5af2d92 feat: add project test runner detection`

Dieser Abschnitt wird automatisch aus dem lokalen Git- und Teststand
sowie aus der aktuellen ROADMAP.md erzeugt.
Manuell gepflegte Dokumentation außerhalb dieses Blocks bleibt erhalten.
<!-- FORGE:AUTO:CURRENT_STATE:END -->

`AgentReality.record_run_state()` kann den aktuellen autoritativen
`AgentRun`-Zustand als `AgentEvent` in der Reality-Sicht erfassen.

Dabei werden Task-ID, Run-ID, Phase, vorheriger und aktueller Zustand sowie
die aktuellen Review-, Execution- und Repair-Zähler festgehalten.

Die Event-Historie ist Teil der Reality-Sicht und ersetzt nicht die
autoritative `AgentRun`-History.
