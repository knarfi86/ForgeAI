# Verification Framework

Stand: 2026-10-05

## Zweck

Das Verification Framework ist die fachneutrale Steckschicht zwischen
Capability-Plugins, lokalen Tools und dem zentralen `CompletionGate`.

Es definiert, **wie** reproduzierbare Prüfungen registriert, ausgeführt,
historisiert und in Completion-Evidence übersetzt werden. Es enthält selbst
keine Python-, Unreal-, Blender-, ComfyUI-, Bild-, Video- oder Audio-Speziallogik.

## Zentrale Bausteine

### `VerificationRegistry`

Registriert:

- `VerificationProvider`: konkrete Prüfer;
- `VerificationProfile`: benannte Gruppen von Prüfschritten.

Doppelte IDs werden standardmäßig abgelehnt. Ein bewusstes Ersetzen muss
explizit angefordert werden.

### `VerificationProvider`

Ein Provider kapselt genau eine verifizierende Fähigkeit. Er deklariert:

- stabile `provider_id`;
- Evidence-Kategorie (`technical`, `runtime`, `visual`, `semantic`);
- Evidence-Modus (`FACT` oder `INFERENCE`);
- eine `verify(...)`-Operation.

Objektive Kategorien (`technical`, `runtime`, `visual`) dürfen nur Provider
registrieren, die `FACT` liefern. Damit kann ein Plugin keine LLM-Inferenz als
beobachtete Runtime- oder Visual-Wahrheit einschleusen.

### `VerificationCheck`

Ein Check referenziert einen registrierten Provider und beschreibt:

- stabile `check_id`;
- `provider_id`;
- Evidence-Kategorie;
- ob der Check für das Profile erforderlich ist;
- optionale Metadaten.

### `VerificationProfile`

Ein Profile gruppiert Checks für eine konkrete Fähigkeit oder Aufgabe.

Beispiele für spätere Profile:

- `python.basic`;
- `unreal.editor-launch`;
- `game.window-visible`;
- `image.output-inspection`;
- `blender.model-validation`;
- `video.output-validation`.

Das Profile bestimmt aus seinen Required Checks automatisch, welche Completion-
Evidence-Kategorien für den Lauf zusätzlich erforderlich werden.

### `VerificationEngine`

Der Engine-Core führt nur registrierte Checks aus. Er enthält keine
fachspezifischen Prüfregeln.

Der Ablauf lautet:

```text
VerificationProfile
        ↓
VerificationCheck
        ↓
registrierter Provider
        ↓
VerificationResult
        ↓
VerificationReport
        ↓
CompletionEvidence
        ↓
CompletionGate
```

Provider-Fehler werden nicht als Erfolg interpretiert. Ein Provider, der keine
belastbare Evidence liefern kann, erzeugt einen `ERROR`-Status. Dieser wird für
das CompletionGate als `UNKNOWN` weitergegeben: **nicht geprüft ist nicht
bestanden und auch nicht automatisch fehlgeschlagen**.

## Freshness und Laufbezug

Jeder `VerificationContext` enthält mindestens:

- `task_id`;
- aktuelle `execution_round`;
- optional den Projektpfad;
- zusätzliche kontrollierte Metadaten.

`VerificationReport` ist ebenfalls an `task_id` und `execution_round` gebunden.
Der `AgentOrchestrator` lehnt Reports für andere Tasks oder alte Execution-
Runden ab.

Damit kann historische Evidence erhalten bleiben, ohne als aktueller Nachweis
zu gelten.

## Integration in AgentRun und Reality

Ein Agentenlauf kann erforderliche Verification-Profile deklarieren.

`AgentRun` historisiert:

- `required_verification_profiles`;
- `verification_reports`;
- daraus erzeugte `completion_evidence`;
- die resultierenden Completion-Entscheidungen.

`RunReality` projiziert diese Daten, bleibt aber weiterhin nur Sicht auf den
autoritativen `AgentRun`.

## Verhältnis zum bestehenden technischen Testlauf

Der bisherige `ProjectTestRunner` und `AgentVerificationWorker` bleiben
kompatibel. Ihre technische Evidence wird weiterhin über den bestehenden
technischen Pfad erzeugt.

Das neue Framework ergänzt diesen Pfad um beliebige registrierbare Profile.
Ein späteres Capability-Plugin kann daher zusätzliche Runtime-, Visual- oder
Semantic-Prüfungen verlangen, ohne den bestehenden Agentenworkflow zu ersetzen.

## Noch nicht enthalten

Dieser Core-Schritt enthält bewusst noch nicht:

- konkrete Runtime-Provider für Fenster, Prozesse oder Ports;
- Screenshot- oder Vision-Provider;
- Python-/Unreal-/Blender-/ComfyUI-spezifische Profile;
- konkrete fachliche FactProvider für allgemeine Systemwahrheit;
- PluginManager/CapabilityRegistry;
- GPU-/VRAM-Ressourcenkoordination.

Diese Funktionen werden schrittweise auf der jetzt stabilen Registry-/Profile-
Schnittstelle aufgebaut.

## Verbindung zum FactService

Die allgemeine Fact-/Evidence-Schicht ist jetzt implementiert. FactProvider
beobachten objektive Zustände und liefern `FactRecord`-Evidence;
VerificationProvider entscheiden darauf aufbauend, ob ein konkreter Required
Check `PASS`, `FAIL` oder `UNKNOWN` ist.

Damit bleibt die Trennung klar: Der FactService beantwortet „Was ist aktuell
beobachtet?“, das Verification Framework beantwortet „Erfüllt diese Beobachtung
den geforderten Check?“.

Details: `docs/FACT_EVIDENCE_PROVIDER.md`.
