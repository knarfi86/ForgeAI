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


## Projektanalyse

ForgeAI besitzt zwei Analyseebenen:

### 1. Deterministische lokale Analyse

`ProjectAnalyzer` analysiert das Projekt ohne LLM. Dabei werden lokale,
reproduzierbare Informationen aus dem Dateisystem und dem Python-AST gewonnen.

Erfasst werden unter anderem:

- Dateien und Ordner
- Programmiersprachen
- Python-Module
- Klassen
- Funktionen und Methoden
- Imports und Modulstruktur
- Git-Repository-Informationen
- offene Aufgaben aus der Projektdokumentation

Diese Analyse bildet die objektive strukturelle Grundlage und wird von
`ForgeBrain` persistent gespeichert.

### 2. LLM-Gegenanalyse

Die deterministische Analyse kann anschließend von einem lokalen LLM geprüft
und fachlich bewertet werden.

Die geplante Gegenanalyse arbeitet in konfigurierbaren Runden:

1. ForgeAI erstellt die lokale Basisanalyse.
2. Ein LLM prüft die Analyse und sucht nach fehlenden, widersprüchlichen oder
   falsch bewerteten Punkten.
3. Die Analyse wird anhand der Rückmeldung korrigiert.
4. In weiteren Runden wird die überarbeitete Analyse erneut geprüft.
5. Optional kann nach einer oder mehreren Runden ein anderes Modell als
   unabhängiger Prüfer eingesetzt werden.
6. Am Ende wird aus Basisanalyse und Gegenprüfungen eine konsolidierte
   Projektanalyse erstellt.

Die Anzahl der Analyse-Runden soll über die Einstellungen konfigurierbar sein.
Der Standardwert beträgt zwei Runden. Die Prüfung kann vollständig deaktiviert werden. Als technische Obergrenze sind sieben Runden vorgesehen.

Ein Modellwechsel zwischen den Runden ist ausdrücklich vorgesehen, damit die
Analyse nicht ausschließlich von einer einzigen Modellperspektive abhängt.

Die LLM-Gegenanalyse ersetzt die deterministische Analyse nicht. Sie ergänzt
sie. Dadurch bleiben objektiv aus dem Projekt ableitbare Fakten von der
interpretierenden Bewertung des LLM getrennt.

### Geplante Analysearchitektur

ProjectAnalyzer
→ erstellt die deterministische strukturelle Basisanalyse

AIContextProvider
→ stellt gezielt freigegebene Projektinformationen als Kontext bereit

OllamaClient
→ kommuniziert mit den lokalen LLMs

AnalysisReview
→ prüft die Basisanalyse, erkennt Schwachstellen und formuliert Korrekturen

AnalysisOrchestrator
→ steuert die konfigurierbaren Analyse-Runden, übergibt die korrigierte Analyse an die nächste Runde und kann zwischen den Runden unterschiedliche Modelle einsetzen

ForgeBrain
→ speichert die konsolidierte Analyse

Die genaue technische Aufteilung der späteren Review- und Orchestrierungs-
Komponenten wird erst bei der Implementierung festgelegt. Die Architektur
soll jedoch sicherstellen, dass deterministische Fakten, LLM-Bewertungen,
Korrekturen und die finale Konsolidierung getrennt nachvollziehbar bleiben.

## Agenten-Workflow: Planung, Prüfung, Ausführung und Reparatur

Der zukünftige Coding-Agent arbeitet nicht als ungeprüfter Einzelschritt, sondern
als kontrollierter mehrstufiger Prozess.

Der verbindliche Ablauf ist:

`PLAN`
→ `REVIEW (optional)`
→ `REVISE`
→ `USER APPROVAL`
→ `EXECUTE`
→ `TEST`
→ `ANALYZE`
→ `REPAIR (optional)`
→ `REVIEW`
→ `EXECUTE`
→ `TEST`
→ ...

### Planungs- und Review-Schleife

Der Planner erstellt aus der Benutzeranforderung einen konkreten Änderungsplan.

Die optionale Review-Komponente prüft den Plan unabhängig vom eigentlichen
Schreibvorgang. Bewertet werden insbesondere:

- technische Eignung des vorgeschlagenen Lösungswegs
- Übereinstimmung mit der Benutzeranforderung
- betroffene Komponenten und Abhängigkeiten
- mögliche Nebenwirkungen
- Sicherheits- und Berechtigungsaspekte
- Vollständigkeit der vorgesehenen Tests

Eine Review kann folgende Entscheidungen liefern:

- `APPROVE`
- `REVISE`
- `REJECT`

Bei `REVISE` wird der Plan überarbeitet und erneut geprüft.

### Review-Konfiguration

Die Prüfung ist vollständig konfigurierbar und kann deaktiviert werden.

Vorgesehene Einstellungen:

- `review_enabled`: `true` oder `false`
- `max_review_rounds`: aktueller Standard `3`

Das Maximum von sieben Runden ist eine technische Sicherheitsgrenze gegen
Endlosschleifen. Die tatsächliche Anzahl der Runden endet früher, sobald
`APPROVE` erreicht wird.

Die Rundenzahl wird nicht fest im Code verdrahtet.

### Ausführung und Verifikation

Nach einer erforderlichen Benutzerbestätigung wird der finale Plan ausgeführt.

Die eigentliche Änderung erfolgt weiterhin ausschließlich über den bestehenden
kontrollierten Änderungsworkflow:

`ChangePreview`
→ Benutzerbestätigung
→ `WorkspaceTools.apply(..., confirmed=True)`
→ `FileSystem`

Nach der Ausführung folgt die Verifikation.

Tests sind unabhängig von der LLM-Review. Ein erfolgreicher Testlauf beweist,
dass die konkrete Implementierung die geprüften Tests besteht, ersetzt aber
nicht die fachliche oder architektonische Prüfung des Lösungswegs.

### Reparaturschleife

Schlagen Tests fehl, kann ForgeAI optional einen Reparaturzyklus starten.

Dabei werden Testergebnis und Fehlerursache analysiert. Daraus entsteht ein
neuer Reparaturvorschlag, der vor der erneuten Ausführung wiederum geprüft
werden kann.

Vorgesehene bzw. teilweise umgesetzte Einstellungen:

- `repair_enabled`: über den Workflow steuerbar
- `max_repair_attempts`: aktuell `3` in `AgentRun`

Eine vollständig externe Konfiguration mit frei wählbarer Grenze bis sieben
Versuchen bleibt eine weitere Ausbaustufe.

Auch hier gilt: Das Maximum von sieben ist eine Sicherheitsgrenze. Der Zyklus
endet früher, wenn die Tests erfolgreich sind oder keine sinnvolle Reparatur
mehr möglich ist.

### Unabhängigkeit der Schleifen

Review, Repair und Test bilden drei getrennte Verantwortlichkeiten:

- **Review** bewertet den Lösungsweg und dessen Qualität.
- **Repair** reagiert auf konkrete Verifikationsfehler.
- **Test** bewertet die tatsächlich ausgeführte Implementierung.

Dadurch kann beispielsweise die LLM-Review deaktiviert werden, während die
automatische Testausführung weiterhin aktiv bleibt.

Ebenso kann die automatische Reparatur deaktiviert werden, ohne die Tests
abzuschalten.

### Nachvollziehbarkeit

Jeder Agentenlauf soll mindestens folgende Kennungen und Zustände nachvollziehbar
speichern:

- `task_id`
- `review_round`
- `execution_round`
- `repair_attempt`
- `git_commit`
- Teststatus

Vorgesehene Teststatus:

- `PASS`
- `FAIL`
- `ERROR`
- `SKIPPED`
- `BLOCKED`

Die Rohdaten der Testausführung sollen für spätere Analyse und Reparatur
erhalten bleiben.

### Verantwortungszuschnitt

`Planner`
→ erstellt den Änderungsplan

`Review`
→ bewertet den Plan und fordert bei Bedarf eine Überarbeitung

`Approval`
→ erhält die explizite Benutzerfreigabe

`Executor`
→ erzeugt bzw. verarbeitet die Änderungsvorschläge

`Verifier`
→ führt reproduzierbare Prüfungen und Tests aus

`Repair`
→ analysiert Fehler und erzeugt einen neuen Reparaturvorschlag

`WorkspaceTools`
→ erzeugt und verarbeitet kontrollierte Änderungsvorschauen

`FileSystem`
→ führt ausschließlich autorisierte tatsächliche Schreibvorgänge aus

Der Planner, Reviewer und Repairer dürfen nicht direkt Projektdateien schreiben.
Der tatsächliche Schreibzugriff bleibt zentral kontrolliert.

## Agent Reality Layer

### Implementierungsstatus

Der Reality Layer ist als technische Integrationsschicht teilweise umgesetzt.
Die Projektionen von `AgentTask` und `AgentRun` sowie die Zustandsereignisse
sind implementiert. Die vollständige Anbindung aller Agent-, Context-,
Knowledge-, Authority- und Verification-Komponenten bleibt ein separater
Integrationsschritt.

Der Agent Reality Layer stellt eine modellunabhängige strukturierte Sicht auf
Task, Laufzeitstatus, Kontext, Wissen, Berechtigungen, Beobachtungen,
Evidenz, Entscheidungen, Aktionen und Verifikation bereit.

Der Layer ist eine Integrationsschicht und kein God Object. AgentRun bleibt
der zentrale Laufzeitanker. Autoritative Zuständigkeiten verbleiben bei den
bestehenden Komponenten wie WorkspaceManager, ForgeBrain, FileSystem,
WorkspaceTools und den Verification-Komponenten.

Die erste technische Implementierung befindet sich in
`forgeai/core/agent_reality.py` und ist durch
`tests/core/test_agent_reality.py` abgesichert.

## AgentRun und RunReality

<!-- FORGE:AUTO:ARCHITECTURE:START -->
### Automatische Änderungsübersicht

#### Aktuell betroffene Dateien

- `docs/CAPABILITY_PLUGINS.md`
- `docs/PLUGIN_CAPABILITY_FRAMEWORK.md`
- `forgeai/ai/agent_orchestrator.py`
- `forgeai/core/plugin_manager.py`
- `.rossa_install_backups/capability_execution_gate_v1_0_20261006-140412/docs/CAPABILITY_PLUGINS.md`
- `.rossa_install_backups/capability_execution_gate_v1_0_20261006-140412/docs/PLUGIN_CAPABILITY_FRAMEWORK.md`
- `.rossa_install_backups/capability_execution_gate_v1_0_20261006-140412/forgeai/ai/agent_orchestrator.py`
- `.rossa_install_backups/capability_execution_gate_v1_0_20261006-140412/forgeai/core/plugin_manager.py`
- `forgeai/core/capability_execution_gate.py`
- `tests/test_capability_execution_gate.py`

#### Letzte relevante Commits

- `f78041f (HEAD -> temp/agent-workflow-current, origin/temp/agent-workflow-current) feat: integrate capability context into agent planning`
- `1c1b1b8 feat: establish ROSSA agent and capability foundation`
- `fa174bd feat: add recovery context refresh and failure fingerprints`
- `90b645c fix: improve request routing and reviewer handling`
- `e259349 fix: stabilize Ollama integration and clean repository`

Diese Übersicht dokumentiert nur den aktuell sichtbaren Entwicklungsstand.
Architekturentscheidungen und Begründungen bleiben in den manuell
gepflegten Abschnitten von ARCHITECTURE.md erhalten.
<!-- FORGE:AUTO:ARCHITECTURE:END -->

`AgentRun` bleibt der autoritative Laufzeitanker des Agentenworkflows.

`RunReality` stellt davon eine strukturierte Projection für den Agent Reality
Layer bereit. Die Projection wird über `RunReality.from_agent_run()` erzeugt.

Die Verantwortung wird nicht verschoben:

- `AgentRun` besitzt den tatsächlichen Laufzeitstatus.
- `RunReality` repräsentiert diesen Status innerhalb der Reality-Struktur.
- Änderungen an einer Projection dürfen den autoritativen `AgentRun` nicht
  verändern.

Damit bleibt der Reality Layer eine Integrationsschicht und wird nicht zur
zweiten Zustandsverwaltung.

## AgentTask, AgentRun und AgentReality

Der Reality Layer bildet die beiden zentralen Laufzeitobjekte über dedizierte
Projection-Methoden ab:

`TaskReality.from_agent_task()`

`RunReality.from_agent_run()`

`AgentReality.from_task_and_run()`

`AgentTask` und `AgentRun` bleiben dabei die autoritativen Quellen.
`AgentReality` übernimmt keine Ownership des bestehenden Task- oder
Laufzeitstatus.

Die Projection ist bewusst getrennt von den Ausgangsobjekten. Kopierte
Metadata-, History- und Revision-Context-Strukturen verhindern, dass eine
Änderung an der Reality-Sicht den autoritativen Agentenlauf verändert.

## AgentRun State Events

Der Reality Layer kann Zustandsübergänge des `AgentRun` als `AgentEvent`
abbilden.

`AgentReality.record_run_state()` erzeugt dabei eine Reality-Repräsentation
des aktuellen Laufzeitzustands. Die Methode verändert den `AgentRun` nicht.

Damit bleibt die Verantwortungsverteilung erhalten:

`AgentRun` verwaltet den autoritativen Zustand.

`AgentReality` stellt eine strukturierte Sicht auf diesen Zustand bereit.

`AgentEvent` dokumentiert den beobachteten Zustand innerhalb dieser Sicht.

<!-- FORGE:RECOVERY_FOUNDATION:START -->
## Recovery-Grundgerüst: aktueller Kontext und Fehlersignaturen

Vor jedem Recovery-Lauf werden Workspace-Index, vorhandene Reality-Evidence
und der tatsächlich an Analyzer/Repairer übergebene Projektkontext erneuert.
Dateifreigaben und das bestehende Kontextbudget bleiben maßgeblich.
Ein fehlgeschlagener Refresh beendet den Lauf, statt alten Kontext zu nutzen.

Der Orchestrator erfasst Verifikationsergebnisse als unveränderliche
`VerificationRecord`-Einträge in `AgentRun.verification_history`.
Fehlgeschlagene Ergebnisse erhalten eine deterministische, versionierte
`FailureFingerprint`-Signatur. Die bestehende Zustands-History bleibt erhalten.

`AgentRun.repair_history` verbindet abgeschlossene Reparaturversuche mit der
vorherigen Fehlersignatur, Analyse, Reparaturplan und dem danach beobachteten
Verifikationsergebnis. `StagnationDetector` wertet diese Evidence zusammen mit
`verification_history` deterministisch aus und erzeugt einen
`StagnationStatus`.

`RecoveryEscalationPolicy` konsumiert diesen Status ohne LLM. Bei aktiver
Stagnation und verbleibendem Repair-Budget fordert sie eine breitere Analyse
auf Basis des aktuellen freigegebenen Projektkontexts. Bei einem fehlgeschlagenen Repair mit erschöpftem Budget
beendet der Orchestrator den Lauf kontrolliert als `FAILED`. Die aktuelle
Entscheidung und ihre History liegen im autoritativen `AgentRun` und werden in
`RunReality` projiziert. Ein eigener Dependency-Scanner, Redesign/Replanning
und dauerhafte Run-Persistenz sind noch nicht implementiert. Details und
nachgewiesene Grenzen: `docs/RECOVERY_FOUNDATION.md`.
<!-- FORGE:RECOVERY_FOUNDATION:END -->

<!-- FORGE:CORE_TRUTH_PLUGIN_PRINCIPLES:START -->
## Core-Prinzipien: Evidence, Script-first Truth und Capability-Plugins

ForgeAI behandelt objektiv prüfbare Zustände nicht als LLM-Wissen. Alles, was
über Dateisystem, Git, Tests, Compiler, lokale APIs, Prozesse oder andere
Werkzeuge direkt ermittelt werden kann, wird durch deterministische Provider
abgefragt und als Evidence bzw. Fact geführt. LLMs dürfen diese Evidence
interpretieren, aber nicht durch Erinnerung oder Behauptung ersetzen.

Für widersprüchliche Informationen gilt grundsätzlich:

`direkte aktuelle Tool-Evidence`
→ `aktuelle persistierte Evidence`
→ `Forge Reality/State`
→ `LLM-Inferenz`
→ `Erinnerung/Historie`

Niedrigere Ebenen dürfen höhere Ebenen nicht überschreiben. Historische Fakten
müssen vor zustandsabhängigen Entscheidungen auf Freshness geprüft werden.

Der Core bleibt fachneutral. Sprach-, Engine- und Medienfähigkeiten werden
schrittweise als aktivierbare Capability-Plugins angebunden. Plugins liefern
Tools, Adapter, Verification-Profile und Fachwissen, unterliegen aber weiterhin
den zentralen Authority-, Evidence-, Verification-, Recovery-, Stagnations- und
Completion-Regeln.

Ein Plugin darf insbesondere keine direkte Schreib- oder Completion-Hoheit
übernehmen und keine objektiv prüfbaren Zustände durch LLM-Aussagen ersetzen.

Das Zielprinzip lautet: **Forge darf sich erinnern, aber es muss nachsehen.**

Details: `docs/CORE_PRINCIPLES.md` und `docs/CAPABILITY_PLUGINS.md`.
<!-- FORGE:CORE_TRUTH_PLUGIN_PRINCIPLES:END -->


<!-- FORGE:COMPLETION_GATE:START -->
## CompletionGate: technische Wahrheit und Auftragserfüllung

Der Orchestrator führt einen technisch erfolgreichen Verifikationslauf durch das
fachneutrale `CompletionGate`, statt technische Test-Evidence implizit mit
vollständiger Auftragserfüllung gleichzusetzen.

Vier Evidence-Klassen sind im Core definiert: `technical`, `runtime`, `visual`
und `semantic`. Technische, Runtime- und visuelle Aussagen zählen nur als
beobachtete Facts. Semantische Inferenz ist zulässig, muss jedoch reale
Fact-Evidence-IDs referenzieren. Das Gate selbst führt keine LLM-Aufrufe und
keine fachlichen Tests aus.

Fehlende Required Evidence erzeugt den transienten Zustand
`COMPLETION_CHECKING`. Erst belegte Ergebnisse führen zu den finalen Outcomes
`COMPLETED`, `PARTIALLY_COMPLETED` oder `FAILED`.

Der aktuelle bestehende Agentenworkflow verwendet zunächst nur `technical` als
Required Category. Das implementierte Verification-Framework kann weitere Kategorien
pro Aufgabe oder Capability-Plugin aktivieren, ohne die Completion-Policy zu
umgehen.

`AgentRun` ist autoritativ für `completion_evidence`, `completion_decision` und
`completion_history`; `RunReality` bleibt eine davon abgeleitete Projection.

Details: `docs/COMPLETION_GATE.md`.
<!-- FORGE:COMPLETION_GATE:END -->

<!-- FORGE:VERIFICATION_FRAMEWORK:START -->
## Generisches Verification Framework

Der Forge-Core besitzt eine fachneutrale Registry-/Profile-Schicht für reale
Prüfungen. `VerificationRegistry` registriert Provider und benannte
`VerificationProfile`; `VerificationEngine` führt die Profile aus und erzeugt
strukturierte `VerificationReport`-Objekte.

Objektive Provider für `technical`, `runtime` und `visual` dürfen ausschließlich
`FACT`-Evidence liefern. Provider-Ausfälle gelten als `UNKNOWN`, nicht als
impliziter Erfolg. Reports sind an `task_id` und `execution_round` gebunden und
werden vom Orchestrator bei veraltetem oder falschem Laufbezug abgelehnt.

Ein erforderliches Verification-Profile erweitert deterministisch die Required
Categories des `CompletionGate`. `AgentRun` historisiert angeforderte Profile
und Reports; `RunReality` projiziert diesen Zustand.

Der Core enthält dabei keine fachlichen Checker. Python, Unreal, Blender,
ComfyUI, Bild, Video oder Audio liefern später eigene Provider/Profile über die
Capability-Schicht.

Details: `docs/VERIFICATION_FRAMEWORK.md`.
<!-- FORGE:VERIFICATION_FRAMEWORK:END -->


<!-- FORGE:FACT_EVIDENCE_PROVIDER:START -->
## Zentraler Fact-/Evidence-Provider

Der Forge-Core besitzt jetzt eine fachneutrale Truth-Schicht aus `FactRegistry`,
`FactService`, `FactQuery`, `FactObservation` und persistierbaren `FactRecord`-Objekten.

Objektive Zustände dürfen nur von registrierten maschinellen Quellen stammen:
Script, API, Dateisystem, Repository, Datenbank, Runtime oder Tool. LLM, Memory
und Chat sind bewusst keine zulässigen `FactSourceType`-Werte.

Der `FactService` kontrolliert Freshness und Provenance zentral. Positive Facts
dürfen nur innerhalb eines expliziten Freshness-Budgets und nur im identischen
Task-/Execution-/Projektkontext wiederverwendet werden. `UNKNOWN` und `ERROR`
werden nicht als frische Wahrheit gecacht. Ein Wechsel der `execution_round`
erzwingt einen neuen Beobachtungskontext.

Negative Aussagen sind ebenfalls evidence-pflichtig: `ABSENT` gilt nur dann als
Fact, wenn der Provider eine vollständige negative Prüfung als
`authoritative_absence` bestätigt. Partielles „nicht gefunden“ wird zu
`UNKNOWN` herabgestuft.

Der `AgentOrchestrator` stellt `resolve_fact(...)` als zentralen Einstieg bereit.
Frisch beobachtete Facts werden in `AgentRun.fact_history` historisiert und von
`RunReality` projiziert.

Der FactService führt keine beliebigen LLM-generierten Shell-Kommandos aus.
Konkrete Tools und Scripts werden von registrierten Core- oder
Capability-Providern gekapselt.

Details: `docs/FACT_EVIDENCE_PROVIDER.md`.
<!-- FORGE:FACT_EVIDENCE_PROVIDER:END -->

<!-- FORGE:PLUGIN_CAPABILITY_FRAMEWORK:START -->
## PluginManager und CapabilityRegistry

Der Forge-Core besitzt eine generische Plugin-/Capability-Schicht.
`CapabilityRegistry` registriert deklarative `PluginManifest`-Objekte;
`PluginManager` verwaltet Aktivierung, autonome Nutzung, Projektfreigaben,
Abhängigkeiten, Fact-Anforderungen und Executor.

Forge darf passende Plugins automatisch auswählen, aber niemals abgeschaltete
oder nur manuell erlaubte Plugins selbst freischalten. Blockierte Kandidaten
bleiben im `CapabilityExecutionPlan` sichtbar.

Capability-Pläne werden strikt seriell ausgeführt. Die erste Architektur besitzt
bewusst keine Parallel-Ausführung, damit insbesondere GPU-intensive Tools nicht
unkontrolliert gleichzeitig Ressourcen belegen.

Plugin-Verfügbarkeit wird bei objektiven Anforderungen über den zentralen
`FactService` geprüft. Plugins können Fact-Provider sowie Verification-Provider
und -Profile registrieren; Authority und Completion bleiben dennoch im Core.

`AgentRun.capability_plans` ist die autoritative Laufhistorie der automatischen
Capability-Auswahl; `RunReality` projiziert sie.

Die UI unter `Werkzeuge -> Plugins & Fähigkeiten` erlaubt Benutzerkontrolle über
Aktivierung, autonome Nutzung und projektspezifische Auto-Freigabe.

`model_roles` werden deklarativ erfasst. Die PrimaryModelPolicy wählt inzwischen
standardmäßig das konfigurierte Primärmodell; automatische Specialist-Auswahl
aus diesen Rollen bleibt ein separater Folgeschritt.

Details: `docs/PLUGIN_CAPABILITY_FRAMEWORK.md`.
<!-- FORGE:PLUGIN_CAPABILITY_FRAMEWORK:END -->

<!-- FORGE:PYTHON_REFERENCE_PLUGIN:START -->
## Python als erstes reales Capability-Plugin

Das Built-in-Plugin `python` ist die Referenzimplementierung für die
Capability-Architektur. Es wird beim Composition Root über
`register_builtin_plugins(...)` registriert und bleibt vollständig den
Core-Regeln für Authority, Facts, Verification und serielle Ausführung
untergeordnet.

Der Plugin-Fact-Provider `python.environment` beobachtet Interpreter, Version,
pytest-Verfügbarkeit und Projektmarker ausschließlich über Dateisystem und
Subprozesse. Die Plugin-Verfügbarkeit hängt vom beobachteten Fact
`python.available = true` ab.

Das Verification-Profile `python-source` enthält die Required Checks
`python-interpreter` und `python-compile`. Die Syntaxprüfung wird mit dem real
ausgewählten Interpreter über `py_compile` ausgeführt. Das Plugin selbst darf
keine Completion-Entscheidung treffen.

Der Executor akzeptiert nur die expliziten Aktionen `inspect`, `compile` und
`test`; ohne explizite Aktion gilt `inspect`. Beliebige Shell-/Python-Kommandos
werden nicht aus LLM-Text übernommen.

Die Plugin-UI zeigt zusätzlich einen evidence-basierten Status (`Bereit` /
`Nicht verfügbar`) aus den Fact-Anforderungen. Aktivierung und autonome Nutzung
bleiben getrennte Benutzerfreigaben.

`model_roles = (coding, reasoning)` bleibt deklarativ. Die PrimaryModelPolicy
verwendet standardmäßig das Primärmodell; ein Spezialmodell wird daraus noch
nicht automatisch ausgewählt.

Details: `docs/PYTHON_PLUGIN.md`.
<!-- FORGE:PYTHON_REFERENCE_PLUGIN:END -->

<!-- FORGE:PROJECTLESS_CHAT_ACCESS:START -->
## Projektloser Chat und lokale Read-Authority

Forge trennt drei Request-Klassen mit unterschiedlicher Authority:

1. normaler Chat ohne lokalen Dateizugriff,
2. explizites lokales Lesen,
3. projektgebundene Dateiänderung.

Normaler Chat benötigt kein geöffnetes Projekt. Eine Änderung darf dagegen erst
in den Agentenworkflow gelangen, wenn ein Projekt geöffnet oder neu erstellt
wurde. `WorkspaceTools` bleibt unabhängig von Lesefreigaben strikt auf den
aktiven Projektroot begrenzt.

Für lokales Lesen außerhalb des Projektkontexts existiert eine eigenständige
Read-Authority. Persistente Datei-/Ordnerfreigaben werden in
`ai_external_access_grants` gespeichert. Optional kann der Benutzer globalen
Lesezugriff aktivieren. Global bedeutet: konkrete lokale Pfade dürfen ohne neue
Freigaberückfrage gelesen werden; es bedeutet weder Disk-Scan noch Schreibrecht.

`AIContextProvider` nimmt externe Inhalte nur als konkrete `extra_paths` des
aktuellen Requests auf. Eine vorhandene Freigabe führt nicht automatisch dazu,
dass externe Inhalte in jeden Chat einfließen.

UI: `Werkzeuge -> KI-Lesefreigaben`.

Details: `docs/PROJECTLESS_CHAT_ACCESS.md`.
<!-- FORGE:PROJECTLESS_CHAT_ACCESS:END -->

<!-- FORGE:MODEL_POLICY:START -->
## Primary-first Modellarchitektur

Forge besitzt eine modellunabhängige Core-Logik und behandelt Rollen nicht als
Grund für automatische Modellwechsel. `PrimaryModelPolicy` hält ein
Primärmodell über zusammenhängende Agentenarbeit stabil. Neue AgentWorker
konfigurieren deshalb nur noch ein Primärmodell statt separater Planner-,
Reviewer-, Advisor- und Repairer-Routen.

`ModelProfile` beschreibt Modellmetadaten. `ModelAdapter` ist die einzige
vorgesehene Grenze für spätere modellspezifische Prompt-/Optionsanpassungen;
Adapter dürfen Authority, Evidence, Verification, Completion oder Recovery nie
verändern.

Spezialisten sind opt-in: sie müssen registriert und für die konkrete Rolle
explizit angefordert werden. Nach einem Spezialistenaufruf kehrt die Policy zum
Primärmodell zurück. Explizite Legacy-/Benutzerrouten bleiben kompatibel und
überschreiben die Policy bewusst.

Details: `docs/MODEL_POLICY.md`.
<!-- FORGE:MODEL_POLICY:END -->
