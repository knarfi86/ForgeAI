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

`ProjectAnalyzer`
→ erstellt strukturelle Basisanalyse

`AIContextProvider`
→ stellt gezielt freigegebene Projektinformationen als Kontext bereit

`OllamaClient`
→ kommuniziert mit den lokalen LLMs

`LLM Analysis / Review`
→ prüft und korrigiert die Analyse

`ForgeBrain`
→ speichert die konsolidierte Analyse

Die genaue technische Aufteilung der späteren Review-Komponente wird erst bei
der Implementierung festgelegt.
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
- `review_max_rounds`: Minimum `1`, Standard `2`, Maximum `7`

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

Vorgesehene Einstellungen:

- `repair_enabled`: `true` oder `false`
- `repair_max_attempts`: Minimum `1`, Standard `2`, Maximum `7`

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

### Geplanter Verantwortungszuschnitt

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
Der tatsächliche Schreibzugriff bleibt zentral kontrolliert.\n\n## Agent Reality Layer

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
### Automatischer Reality-Status

- `AgentRun` bleibt die autoritative Laufzeitinstanz.
- Der Reality Layer bildet den Laufzeitstatus strukturiert ab.
- Runtime-Zustandsänderungen können als `AgentEvent` beobachtet werden.
- Der Orchestrator kann Reality-Beobachtungen optional aufzeichnen.

Diese automatische Zusammenfassung enthält nur aus dem Repository
ableitbare technische Fakten.
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
