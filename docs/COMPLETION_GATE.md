# CompletionGate

Stand: 2026-10-05

## Zweck

`CompletionGate` trennt einen technisch erfolgreichen Lauf von einem nachweislich
erfüllten Auftrag. Ein grüner Test ist notwendige technische Evidence, aber nicht
zwangsläufig die vollständige Evidence für das Benutzerziel.

Der Core bleibt fachneutral. Das Gate bewertet nur explizit bereitgestellte
Evidence und führt selbst keine fachlichen Tests, Bildanalysen oder LLM-Aufrufe
aus.

## Evidence-Klassen

Der Core kennt vier generische Klassen:

- `technical`: Tests, Build, Compiler, Exitcodes und andere technische Checks;
- `runtime`: tatsächlich gestartete Prozesse, Fenster, Ports oder Laufzeitverhalten;
- `visual`: beobachtete sichtbare Ergebnisse, Screenshots, Frames oder Render;
- `semantic`: evidence-basierte Bewertung, ob das belegte Ergebnis die
  Benutzeranforderung erfüllt.

Konkrete Provider werden über das implementierte generische Verification-Framework
registriert. Fachspezifische Provider folgen später über Capability-Plugins.

## Fact vor Inference

`technical`, `runtime` und `visual` zählen nur als positive oder negative
Completion-Evidence, wenn sie als beobachtete `FACT`-Evidence vorliegen.
Eine LLM-Inferenz darf diese Kategorien nicht ersetzen.

`semantic` darf eine `INFERENCE` sein. Eine solche Inferenz zählt jedoch nur,
wenn sie konkrete vorhandene Fact-Evidence-IDs referenziert. Nicht belegte oder
auf erfundene IDs verweisende semantische Aussagen werden ignoriert.

Damit bleibt die Rollenverteilung eindeutig:

```text
Tools / Scripts / APIs -> Facts
LLM                    -> Interpretation von Facts
CompletionGate         -> deterministische Entscheidung
```

## Outcomes

Finale Outcomes:

- `COMPLETED`: alle für den aktuellen Completion-Profile erforderlichen
  Evidence-Klassen sind positiv belegt;
- `PARTIALLY_COMPLETED`: die technische Grundlage ist erfolgreich, aber eine
  weitere ausdrücklich erforderliche Evidence-Klasse ist nachweislich
  fehlgeschlagen;
- `FAILED`: die technische Verifikation ist fehlgeschlagen.

Zusätzlich existiert der transiente Zustand `PENDING`. Im AgentRun wird dieser
als `COMPLETION_CHECKING` abgebildet. Er bedeutet ausdrücklich nicht
"teilweise fertig", sondern "erforderliche Evidence steht noch aus".

## Aktuelles Integrationsverhalten

Der bestehende Agentenworkflow verwendet vorerst ein technisches Completion-
Profile. Damit bleibt der heutige Code-Workflow kompatibel: erfolgreiche
technische Verifikation wird vom CompletionGate geprüft und kann weiterhin in
`COMPLETED` enden.

Das Gate unterstützt bereits zusätzliche Required Categories. Wird zum Beispiel
`semantic` oder `visual` als erforderlich konfiguriert, bleibt der Lauf nach der
technischen Verifikation in `COMPLETION_CHECKING`, bis entsprechende Evidence
über `AgentOrchestrator.add_completion_evidence()` vorliegt.

Die konkreten Runtime-, Visual- und Semantic-Provider sind absichtlich noch
nicht Teil des CompletionGate selbst. Das generische Verification-Framework ist
inzwischen implementiert; konkrete Runtime-/Visual-/Semantic-Provider folgen als
Capability- bzw. Evidence-Provider.

## Freshness

Completion-Evidence kann an eine `execution_round` gebunden werden. Evidence aus
einer anderen Execution-Runde wird bei einer aktuellen Bewertung ignoriert.
Historische Evidence darf gespeichert bleiben, aber nicht still als aktueller
Nachweis dienen.

## Reality-Projektion

`AgentRun` bleibt autoritativ für:

- `completion_evidence`;
- `completion_decision`;
- `completion_history`.

`RunReality` projiziert diese Strukturen für Beobachtung und spätere Persistenz.

## Bewusste Grenzen

Noch nicht enthalten:

- automatische Auswahl eines Completion-Profils aus der Aufgabe;
- Runtime-Verifier;
- Screenshot-/Visual-Verifier;
- semantischer Completion-Reviewer;
- plugin-spezifische Verification-Profile;
- persistente Completion-Historie über Prozessneustarts.

Diese Grenzen sind beabsichtigt. Das CompletionGate definiert zuerst die
fachneutrale Entscheidungsschicht, bevor Spezialfähigkeiten angebunden werden.
