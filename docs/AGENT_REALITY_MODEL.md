# ForgeAI – Agent Reality Model

## Zweck

Dieses Dokument hält die Ergebnisse der Untersuchung von Luna/LLM-Agenten und deren Übertragung auf ForgeAI fest.

Ziel ist **nicht**, eine Persona wie `Luna.py` zu bauen. Das Ziel ist ein modellunabhängiges, strukturiertes Verständnis der Agentenrealität: Was ein Agent weiß, was er beobachtet, was er kann, was er darf, in welchem Zustand er sich befindet, welche Unsicherheiten bestehen und wie Entscheidungen über kontrollierte Werkzeuge verifiziert werden.

Die folgenden Aussagen wurden gegen den aktuellen Stand des lokalen Entwicklungsbranches `temp/agent-workflow-current` geprüft, insbesondere gegen `docs/CURRENT_STATE.md`, `ARCHITECTURE.md`, `ROADMAP.md`, `agent_state.py`, `agent_contracts.py`, `agent_orchestrator.py`, `agent_planner.py`, `agent_reviewer.py`, `agent_ui_worker.py`, `model_router.py` und `ai_context.py`.

---

## 1. Grundprinzip

Ein LLM ist nicht mit der gesamten Laufzeitrealität identisch.

Für ForgeAI gilt daher:

```text
Modell        != Kontext
Kontext       != Weltzustand
Wissen        != Wahrheit
Fähigkeit     != Verfügbarkeit
Fähigkeit     != Berechtigung
Intention     != Ausführung
Ausführung    != Erfolg
Konfidenz     != Korrektheit
Erinnerung    != aktueller Zustand
Hypothese     != Fakt
Modell        != Orchestrator
```

ForgeAI soll diese Grenzen explizit machen, statt sie im Agenten zu vermischen.

---

## 2. Agent Reality Model

Die vorgeschlagene Struktur besteht aus folgenden Zustandsbereichen:

```text
Agent Reality
├── Context
├── Knowledge
├── Memory
├── State
├── Capability
├── Authority
├── Observation
├── Evidence
├── Uncertainty
├── Decision / Intent
├── Action / Execution
├── Verification
└── Self Model
```

### Context

Was liegt dem Modell in diesem Verarbeitungsschritt tatsächlich vor?

Enthalten sein können unter anderem:

- Benutzeranforderung
- relevante Projektdaten
- freigegebene Dateien
- Architekturinformationen
- bisherige Agentenereignisse
- Review-Ergebnisse
- Test- und Fehlerdaten
- relevante Memory-Einträge
- aktuelle Constraints

### Knowledge

Informationen, die der Agent als bekannt behandelt.

Wissen sollte möglichst mit Herkunft und Gültigkeit verbunden werden.

Beispiel:

```text
knowledge:
  statement: "WorkspaceTools kontrolliert Dateiänderungen"
  source: ARCHITECTURE.md
  status: verified
  validity: current
```

### Memory

Dauerhaft oder längerfristig gespeicherte Informationen. Memory ist nicht automatisch aktueller Projektzustand und kann veraltet sein.

### State

Autoritativer Zustand des laufenden Agentenprozesses.

ForgeAI besitzt dafür bereits `AgentState` und `AgentRun` mit Zuständen wie:

```text
PLANNING
REVIEWING
APPROVAL_REQUIRED
EXECUTING
TESTING
ANALYZING
REPAIRING
COMPLETED
FAILED
ABORTED
```

Der Zustand sollte vom Orchestrator kontrolliert werden, nicht vom LLM selbst.

### Capability

Was kann der Agent bzw. die Laufzeit technisch ausführen?

Eine deklarierte Fähigkeit ist noch kein Beweis, dass sie im aktuellen Moment funktioniert.

### Authority

Was darf der Agent tatsächlich tun?

Capability und Authority müssen getrennt bleiben.

Beispiel:

```text
filesystem.write = technisch verfügbar
filesystem.write = confirmation_required
```

Forge besitzt bereits eine zentrale Schreibschutzgrenze über `confirmed=True` sowie Projektmodi und KI-Freigaben.

### Observation

Was wurde durch eine überprüfbare Quelle tatsächlich beobachtet?

Beispiele:

```text
Tool: tests.run
Observation: 2 tests failed
```

```text
Tool: filesystem
Observation: erwarteter Diff ist vorhanden
```

### Evidence

Beobachtungen werden als Evidenz verwendet, um Hypothesen oder Zustandsaussagen zu stützen oder zu widerlegen.

```text
supports:
  hypothesis A

contradicts:
  hypothesis B

untested:
  hypothesis C
```

### Uncertainty

Unsicherheit sollte nicht nur als Prozentzahl gespeichert werden. Wichtiger sind offene Fragen, Evidenzlage, Widersprüche und Möglichkeiten zur weiteren Verifikation.

```text
unknown: root_cause
reason: insufficient_evidence
obtainable: true
tools: [tests.run, filesystem.read, git.diff]
next_best_action: inspect_failing_stacktrace
```

### Decision / Intent

Das LLM kann eine Absicht bzw. Entscheidung erzeugen:

```text
"Ich möchte Datei X ändern."
```

Das ist noch keine Ausführung.

### Action / Execution

Die vorgeschlagene Handlung wird über einen kontrollierten Mechanismus ausgeführt.

```text
Intent
→ Policy / Authority
→ Tool
→ Execution
```

### Verification

Die tatsächliche Systemrealität muss unabhängig von der Agentenbehauptung überprüfbar sein.

```text
Agent claim: "Änderung erfolgreich"

System verification:
- erwarteter Diff vorhanden
- Tests bestanden
```

Erst daraus entsteht ein verifizierter Erfolg.

### Self Model

Der Agent kann ein Arbeitsmodell seiner Fähigkeiten, seines Wissens, seines Zustands und seiner offenen Fragen erhalten.

Das Self Model ist eine **Beschreibung** des Agentenzustands, nicht die Autorität darüber.

```text
Self Model != Authority
```

---

## 3. Aktueller ForgeAI-Stand

ForgeAI besitzt bereits mehrere Grundbausteine des Modells.

### Bereits vorhanden

```text
AgentState / AgentRun
    → Zustandsmaschine und Laufhistorie

AgentTask / AgentPlan / ReviewResult
    → strukturierte Agentenverträge

AgentPlanner
    → LLM-basierte Planung ohne direkten Dateischreibzugriff

AgentReviewer
    → getrennte kritische Gegenprüfung ohne direkten Dateizugriff

AgentOrchestrator
    → Steuerung von Planung, Review, Approval, Execution,
      Testing, Analysis und Repair als Zustandsübergänge

ModelRouter
    → Trennung von Agentenrolle und konkretem Modell/Provider

AIContextProvider
    → explizit freigegebener, begrenzter Projektkontext

ChangePreview / WorkspaceTools / FileSystem
    → kontrollierter Übergang von Vorschlag zu bestätigter Ausführung
```

### Aktuell noch nicht vollständig verbunden

Der vorhandene Agentenrahmen erreicht derzeit noch nicht den vollständigen Runtime-Kreislauf:

```text
AgentPlan
→ ChangePreview
→ Benutzerbestätigung
→ WorkspaceTools.apply
→ Tests
→ Fehleranalyse
→ Repair-Vorschlag
→ Review
→ erneute Ausführung
```

Der `AgentOrchestrator` besitzt bereits Zustandsmethoden für Ausführung, Test, Analyse und Repair, aber der aktuelle `AgentWorkflowWorker` führt praktisch nur Planung und Review bis zur Freigabe durch. Die eigentliche End-to-End-Ausführungs-, Verifikations- und Reparaturschleife ist noch nicht vollständig verdrahtet.

Der aktuelle Worker enthält außerdem noch eine doppelte identische `ABORTED`-Prüfung. Das ist ein Codequalitätsdetail und kein Bestandteil des Reality Models.

### Aktueller Kontextstand

`AIContextProvider` begrenzt den lokalen Projektkontext bereits anhand eines Tokenbudgets und einer einfachen Zeichen/Token-Näherung (`CHARS_PER_TOKEN = 4`). Der Kontext wird aus explizit freigegebenen Dateien aufgebaut.

Damit existiert bereits ein wichtiger Teil des Context-Layers. Noch nicht vorhanden ist ein allgemeines strukturiertes Reality-Objekt, das Kontext, State, Knowledge, Evidence, Capability, Authority und Uncertainty gemeinsam beschreibt.

---

## 4. Verantwortlichkeitstrennung

```text
Luna / LLM
→ Interpretation
→ Hypothesen
→ Planung
→ Entscheidungen innerhalb des erlaubten Aktionsraums

Forge Orchestrator
→ Zustandssteuerung
→ Reihenfolge der Schritte
→ Loop-Control
→ Übergänge zwischen Agentenrollen

Policy / Authority Layer
→ Was ist erlaubt?
→ Welche Bestätigung ist nötig?

Tools
→ tatsächliche Wirkung auf die Welt

Verifier / Testsystem
→ objektive Rückmeldung über die Wirkung

Reality Model
→ gemeinsamer strukturierter Zustand der Agentenrealität
```

Forge bleibt damit die Instanz mit der Handlungskontrolle. Ein Modell erhält Intelligenz und Werkzeuge, aber nicht automatisch deren vollständige Autorität.

---

## 5. Agentenzyklus

Der zukünftige Standardkreislauf soll eher einem Reasoning- und Verifikationsloop entsprechen als einem einfachen Retry-Loop:

```text
OBSERVE
→ INTERPRET
→ HYPOTHESIZE
→ DECIDE
→ POLICY CHECK
→ ACT
→ OBSERVE
→ VERIFY
→ UPDATE STATE
→ UPDATE KNOWLEDGE / MEMORY
→ next decision
```

Bei Unsicherheit:

```text
UNCERTAINTY
→ Welche Information fehlt?
→ Welche Aktion liefert relevante Evidenz?
→ Ist diese Aktion erlaubt?
→ Beobachtung
→ Bewertung
```

Damit wird ein Fehler nicht einfach wiederholt, sondern untersucht.

---

## 6. Erfolgs- und Fehlersemantik

Ein Agentenlauf sollte mindestens unterscheiden zwischen:

```text
INTENT
PROPOSAL
AUTHORIZED
EXECUTING
EXECUTED
OBSERVED
VERIFIED
```

Ein Agent darf nicht allein durch eine Behauptung den Systemzustand auf `VERIFIED` setzen.

Bei widersprüchlicher Evidenz sollte der Zustand nicht künstlich auf Erfolg oder Misserfolg reduziert werden. Ein möglicher zukünftiger Zustand ist:

```text
CONFLICTING_EVIDENCE
```

---

## 7. Unsicherheit als Steuerung

Unsicherheit sollte nicht nur als Konfidenzwert gespeichert werden. Für Forge ist entscheidender:

```text
Was ist unbekannt?
Warum ist es unbekannt?
Kann es überprüft werden?
Welche Tools können Evidenz liefern?
Welche nächste Aktion reduziert die Unsicherheit am stärksten?
```

Das eröffnet einen gezielten Investigation-Loop:

```text
Hypothesenraum
→ Evidenz sammeln
→ Hypothesen ausschließen
→ nächste beste Untersuchung
→ Reparatur
→ Verifikation
```

---

## 8. Kontextstrategie

Das Ziel ist nicht ein maximal großes Kontextfenster, sondern ein möglichst kleiner, relevanter und verlässlicher Kontext.

Der zukünftige Kontext sollte möglichst strukturiert zusammengestellt werden:

```text
Context Budget
├── Agent / System Rules
├── User Task
├── Current State
├── Relevant Project Knowledge
├── Relevant Files
├── Previous Decisions
├── Review Results
├── Test / Error Evidence
├── Memory
└── Output Reserve
```

Der bestehende `AIContextProvider` ist dafür eine Ausgangsbasis, arbeitet aber aktuell überwiegend mit einem einzelnen begrenzten Textblock aus freigegebenen Dateien. Ein späterer Context Engine Layer sollte gezielter nach Aufgabenrelevanz und Evidenzbedarf zusammensetzen.

Langfristiges Ziel:

```text
Context-on-Demand
```

statt eines ungezielten vollständigen Projekt-Dumps.

---

## 9. Evidence und Provenienz

Informationen sollten möglichst eine Quelle besitzen.

Geeignete Quellenklassen sind beispielsweise:

```text
USER_CLAIM
SYSTEM_STATE
TOOL_OBSERVATION
TEST_RESULT
MEMORY
PROJECT_ANALYSIS
EXTERNAL_SOURCE
MODEL_INFERENCE
```

Damit kann Forge unterscheiden zwischen:

```text
"Der Benutzer sagt X."
"Das Tool beobachtet X."
"Das Modell schließt X daraus."
"Der Test bestätigt X."
```

Diese Unterscheidung ist eine Voraussetzung für nachvollziehbare Agentenentscheidungen.

---

## 10. Self Model

Ein zukünftiger Agent Context sollte dem Modell beschreiben können:

```text
KNOWN
INFERRED
UNKNOWN
UNAVAILABLE

CAPABILITIES
AUTHORITIES
CURRENT STATE
AVAILABLE TOOLS
CURRENT LIMITATIONS
```

Beispiel:

```text
KNOWN
✓ Test X failed
✓ Datei Y wurde geändert

INFERRED
~ Änderung Y ist wahrscheinlich ursächlich

UNKNOWN
? genaue Ursache

CAPABILITIES
✓ Dateien lesen
✓ Tests ausführen

AUTHORITY
✓ ChangePreview erzeugen
✗ direkt ohne Bestätigung schreiben

NEXT ACTION
→ Stacktrace analysieren
```

Diese Informationen sollen aus autoritativen Forge-Zuständen erzeugt werden. Das Modell darf daraus nicht seine eigenen Rechte ableiten.

---

## 11. Modell- und Provider-Unabhängigkeit

Das Reality Model soll nicht an ein konkretes Modell gebunden werden.

Der bestehende `ModelRouter` ist dafür bereits die passende Grundlage:

```text
Forge
└── ModelRouter
    ├── Ollama / lokale Modelle
    ├── OpenAI / API-Modelle
    └── weitere Provider
```

Ein Modell wie Luna wäre damit eine mögliche Intelligenzquelle innerhalb von Forge, nicht ein zweiter Forge-Kern.

Die Umgebung bleibt unter Forge-Kontrolle:

```text
Forge besitzt:
- Context
- State
- Authority
- Tools
- Verification
- Memory / Project Knowledge

Modell liefert:
- Interpretation
- Planung
- Hypothesen
- Entscheidungen
```

---

## 12. Zusammenhang mit ForgeBrain

`ForgeBrain` ist aktuell als dauerhaftes, KI-unabhängiges Projektwissen ausgelegt.

Das Reality Model ergänzt dieses Projektwissen um laufzeitbezogene Informationen.

```text
ForgeBrain
→ dauerhaftes Projektwissen

Agent Reality
→ aktueller Laufzeitkontext

Conversation / Task
→ kurzfristiger Arbeitskontext
```

Diese Ebenen sollten getrennt bleiben, aber miteinander verknüpft werden können.

---

## 13. Zielbild

```text
                    FORGE
                       │
              ┌────────┴────────┐
              │ Reality Model   │
              └────────┬────────┘
                       │
       ┌───────────────┼────────────────┐
       ▼               ▼                ▼
     CONTEXT          STATE          AUTHORITY
       │               │                │
       └───────────────┼────────────────┘
                       ▼
                    LUNA/LLM
                       │
                 Decision/Intent
                       │
                       ▼
                    POLICY
                       │
                       ▼
                     TOOL
                       │
                    WORLD
                       │
                   OBSERVE
                       │
                  VERIFICATION
                       │
                       ▼
                 REALITY UPDATE
                       │
                       └────────→ next loop
```

Leitprinzip:

> **Luna denkt. Forge orchestriert. Tools handeln. Verifier prüfen. Das Reality Model hält die gemeinsame Wahrheit über den Laufzustand zusammen.**

---

## 14. Abgrenzung

Dieses Dokument ist ein konzeptionelles Architekturartefakt und keine Vorgabe für sofortige Implementierung.

Noch offen bleiben insbesondere:

- genaue Klassen- und Datenstrukturen des Reality Models
- Speicherformat und Persistenz der Runtime-Ereignisse
- genaue Provenienz- und Evidence-Schemata
- konkrete Unsicherheitsmetriken
- Kontext-Retrieval und Information-Gain-Strategien
- Verifier-Architektur
- Verbindung des Agentenrahmens mit `ChangePreview` und Tests
- UI-Darstellung des Agent Reality Model
- mögliche externe Provider und deren konkrete Limits

Diese Punkte sollen erst nach Abgleich mit dem jeweils aktuellen ForgeAI-Code konkretisiert werden.

---

## 15. Nächste technische Schritte

1. Reality Model als Datenmodell konkretisieren.
2. Bestehende `AgentRun`-/`AgentState`-Struktur darauf abbilden.
3. Ereignis-/Provenienzmodell ergänzen.
4. Context Engine von einem einzelnen Textblock zu strukturiertem Kontext weiterentwickeln.
5. AgentPlan mit bestehendem `ChangePreview`-Workflow verbinden.
6. Execution und Verification anbinden.
7. Test-/Failure-Evidenz strukturiert an Analysis und Repair übergeben.
8. Self Model des Agenten aus autoritativen Forge-Daten erzeugen.
9. Erst danach automatische Loops und weitergehende Autonomie ausbauen.

Die bestehende Sicherheitsgrenze bleibt erhalten:

```text
LLM-Vorschlag
→ ChangePreview
→ Benutzer-/Policy-Freigabe
→ WorkspaceTools.apply(..., confirmed=True)
→ FileSystem
→ Verification
```

---

## Status

**Stand:** konzeptionelle Grundlage erstellt und gegen den lokalen Entwicklungsbranch `temp/agent-workflow-current` abgeglichen.

**Implementierungsstatus:** überwiegend Konzept; einzelne Bausteine existieren bereits im aktuellen Agentenrahmen.

**Dokumentationshinweis:** `docs/CURRENT_STATE.md` enthält aktuell einen älteren Referenz-Commit und sollte beim nächsten Dokumentationscommit auf den tatsächlichen Stand von `forgeai-dev` synchronisiert werden.

**Wichtig:** Dieses Dokument ersetzt weder `ARCHITECTURE.md` noch `ROADMAP.md` oder `docs/CURRENT_STATE.md`. Es bündelt die neue konzeptionelle Ebene und soll vor der nächsten größeren Agenten-/Orchestratoränderung gemeinsam mit diesen Dokumenten aktualisiert werden.
