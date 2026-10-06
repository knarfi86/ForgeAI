# Fact / Evidence Provider

Stand: 2026-10-05

## Zweck

Der Fact-/Evidence-Provider ist die zentrale fachneutrale Wahrheitsschicht des
ForgeAI-Cores. Er setzt das verbindliche Prinzip **„Forge darf sich erinnern,
aber es muss nachsehen“** technisch um.

Objektiv prüfbare Zustände werden nicht aus Chatverlauf, Memory oder
LLM-Erinnerung abgeleitet. Sie werden über registrierte maschinelle Provider
beobachtet und mit Quelle, Zeit, Laufbezug und Freshness historisiert.

## Zulässige Fact-Quellen

`FactSourceType` kennt ausschließlich maschinell beobachtbare Quellen:

- `script`;
- `api`;
- `filesystem`;
- `repository`;
- `database`;
- `runtime`;
- `tool`.

Es gibt bewusst keinen Source-Typ `llm`, `memory` oder `chat`.

Ein LLM kann aus Facts eine Inference bilden. Es kann aber keinen FactProvider
ersetzen.

## Zentrale Bausteine

### `FactQuery`

Fordert genau einen objektiven Fakt an. Eine Query enthält mindestens:

- `fact_key`;
- optionale Parameter;
- optional eine explizite `provider_id`;
- `max_age_seconds` als Freshness-Budget.

`max_age_seconds = 0` bedeutet: immer neu beobachten.

### `FactProvider`

Ein Provider deklariert:

- stabile `provider_id`;
- einen zulässigen `FactSourceType`;
- die unterstützten `fact_keys`;
- eine `observe(...)`-Operation.

Capability-Plugins können später eigene Provider registrieren, zum Beispiel für
Git, Ollama, Blender, Unreal, ComfyUI, GPU-Zustand oder Audio-Tools.

### `FactObservation`

Das rohe Provider-Ergebnis kann sein:

- `OBSERVED`: Wert wurde positiv beobachtet;
- `ABSENT`: Abwesenheit wurde vollständig belegt;
- `UNKNOWN`: Zustand konnte nicht belastbar bestimmt werden;
- `ERROR`: Provider konnte die Beobachtung nicht durchführen.

`ABSENT` zählt nur dann als Fact, wenn der Provider die Abwesenheit als
`authoritative_absence=True` kennzeichnet. Ein partieller Suchlauf darf aus
„nicht gefunden“ keinen Beweis für „existiert nicht“ machen.

### `FactRecord`

Forge stempelt die Beobachtung selbst und ergänzt mindestens:

- stabile `fact_id`;
- `fact_key`;
- `provider_id` und `source_type`;
- Status und Wert;
- `observed_at` und optional `expires_at`;
- `task_id` und `execution_round`;
- Projektpfad und Query-Parameter;
- Tool/Command/Exit-Code, falls vorhanden;
- optionale Rohreferenz und Details.

`OBSERVED` und autoritatives `ABSENT` sind objektive Facts. `UNKNOWN` und
`ERROR` bleiben wichtige Diagnose-Evidence, stellen den angefragten Fakt aber
nicht fest.

### `FactService`

Der Service ist die zentrale Auflösungs- und Freshness-Schicht.

Ablauf:

```text
Agent / Verifier / Plugin braucht Fakt
        ↓
FactQuery
        ↓
FactRegistry
        ↓
registrierter maschineller Provider
        ↓
FactObservation
        ↓
FactService stempelt Provenance + Freshness
        ↓
FactRecord
        ↓
AgentRun / Reality / nachfolgende Interpretation
```

Wenn mehrere Provider denselben `fact_key` anbieten, wählt Forge nicht
willkürlich. Dann muss die `provider_id` explizit angegeben werden.

## Freshness

Ein vorhandener Fact darf nur wiederverwendet werden, wenn:

1. die Query ein positives Freshness-Budget erlaubt;
2. Provider, Fact-Key, Parameter, Task, Execution-Round und Projektpfad identisch
   sind;
3. der vorhandene Record noch nicht abgelaufen ist;
4. der Record tatsächlich autoritativ ist.

`UNKNOWN` und `ERROR` werden nicht als frische Wahrheit gecacht. Der nächste
Bedarf löst deshalb erneut eine reale Beobachtung aus.

Ein Wechsel der `execution_round` erzeugt unabhängig vom Zeitbudget einen neuen
Kontext und damit eine neue Beobachtung.

## AgentRun und Reality

Der `AgentOrchestrator` kann über `resolve_fact(...)` den zentralen FactService
nutzen. Frisch erhobene Records werden in `AgentRun.fact_history` historisiert.

`RunReality` projiziert diese History, besitzt sie aber nicht selbst. Damit
bleibt `AgentRun` die autoritative Laufzeitinstanz.

Ein wiederverwendeter noch frischer Fact wird nicht künstlich als neue
Beobachtung dupliziert. Seine bestehende `fact_id` bleibt nachvollziehbar.

## Verhältnis zum Verification Framework

FactProvider und VerificationProvider haben unterschiedliche Aufgaben:

- FactProvider beantworten objektive Zustandsfragen;
- VerificationProvider bewerten, ob ein konkreter Required Check bestanden,
  fehlgeschlagen oder unbekannt ist;
- VerificationProvider können später FactProvider verwenden;
- `CompletionGate` bleibt allein für Completion-Entscheidungen zuständig.

Beispiel:

```text
FactProvider: "Fenster handle 81234 ist sichtbar"
        ↓
VerificationProvider: Required Check `window-visible` = PASS
        ↓
RuntimeEvidence
        ↓
CompletionGate
```

## Sicherheitsgrenze

Der FactService ist keine allgemeine Shell für LLM-generierte Commands.

Konkrete Scripts, APIs und Tools werden von registrierten Core- oder
Capability-Providern gekapselt. Dadurch kann ein Modell nicht allein durch die
Formulierung einer Query beliebige Befehle mit Fact-Autorität ausführen.

## Noch nicht enthalten

Dieser Schritt enthält bewusst noch nicht:

- konkrete Git-, Hardware-, Ollama-, Prozess- oder Dateisystem-Provider;
- fachliche Python-/Unreal-/Blender-/ComfyUI-Provider;
- PluginManager/CapabilityRegistry;
- automatische Fact-Anforderung durch LLM-Prompts;
- Runtime-/Visual-Screenshot-Inspektion.

Diese Provider werden später als kleine, überprüfbare Core- oder
Capability-Bausteine auf der jetzt stabilen Fact-Schicht registriert.
