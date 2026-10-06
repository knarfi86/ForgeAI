# Python-Referenzplugin

Stand: 2026-10-05

## Zweck

`forgeai.plugins.python_plugin` ist das erste reale Spezialplugin der neuen
ForgeAI-Capability-Architektur. Es beweist die komplette Verbindung von
PluginManifest, FactService, Verification Framework, serieller Ausführung und
Plugin-UI, ohne Python-Speziallogik in den fachneutralen Core zu verschieben.

Das Plugin ist kein zweiter Coding-Agent. Planung, Codeänderungen, Authority,
Recovery und Completion bleiben beim Forge-Core.

## Manifest

Plugin-ID: `python`

Deklarierte Capabilities:

- `code.python.generate`
- `code.python.modify`
- `code.python.test`
- `code.python.debug`

Deklarierte Modellrollen:

- `coding`
- `reasoning`

Die Rollen sind Anforderungen. Die PrimaryModelPolicy verwendet standardmäßig
das Primärmodell; daraus wird noch kein Specialist automatisch ausgewählt.

## Interpreter-Auswahl

Die Interpreter-Suche ist deterministisch und bevorzugt:

1. `.venv` / `venv` / `env` im aktuellen Projekt;
2. `python` bzw. `python3` aus `PATH`;
3. den Python-Interpreter der laufenden Forge-Instanz als Fallback.

Jeder Kandidat wird real mit `--version` gestartet. Ein bloß vorhandener Pfad
reicht nicht als Beleg.

## Facts

Provider: `python.environment`

Beobachtete Fact-Keys:

- `python.available`
- `python.executable`
- `python.version`
- `python.pytest.available`
- `python.pytest.version`
- `python.project.markers`

`pytest` wird über `python -m pytest --version` geprüft. Projektmarker werden nur
als beobachtete Dateinamen gemeldet; aus ihnen wird keine unbelegte semantische
Behauptung über das Projekt abgeleitet.

## Verification

Profile: `python-source`

Required Checks:

- `python-interpreter`: der ausgewählte Interpreter ist real ausführbar;
- `python-compile`: alle berücksichtigten `.py`-Projektdateien werden mit genau
  diesem Interpreter über `py_compile` geprüft.

Typische Cache-, venv-, Build- und VCS-Verzeichnisse werden von der Quellprüfung
ausgeschlossen. Die Ergebnisse sind `technical` / `FACT` Evidence und werden
nicht durch LLM-Einschätzung ersetzt.

## Serieller Executor und Action Contract

Das Manifest deklariert über `PluginActionSpec` genau drei Aktionen:

- `inspect`: Interpreter und Version beobachten;
- `compile`: Python-Projektdateien kompilieren;
- `test`: pytest nutzen, falls im ausgewählten Interpreter vorhanden, sonst
  `unittest discover`.

Alle drei Aktionen akzeptieren aktuell keine freien Parameter. Der Planner darf
die Action-IDs nur als strukturierte `plugin_actions` im AgentPlan anfordern.
Freie Shell-Kommandos oder erfundene Aktionsnamen werden nicht akzeptiert.

Der Executor liest die freigegebene Aktion direkt aus dem
`CapabilityPlanStep.action_id`. Die ältere Übergabe über
`ExecutionContext.metadata["plugin_actions"]["python"]` bleibt nur als
Kompatibilitätsfallback erhalten. Ohne explizite Aktion gilt weiterhin
`inspect`.

## Benutzerfreigaben

Das Built-in-Plugin wird beim Forge-Start registriert und ist grundsätzlich
aktiviert. Die autonome Nutzung bleibt jedoch standardmäßig ausgeschaltet.
Forge darf das Plugin autonom in einen ausführbaren Capability-Plan aufnehmen,
wenn der Benutzer global oder für das aktuelle Projekt die autonome Nutzung
freigibt. Im Standardzustand `manual_only` darf eine konkrete Aktion trotzdem
sichtbar im AgentPlan stehen. Bestätigt der Benutzer diesen Plan, erhält exakt
diese Plugin-ID eine einmalige Freigabe für den aktuellen AgentRun. Die globale
Autonomieeinstellung bleibt unverändert.

Unter `Werkzeuge -> Plugins & Fähigkeiten` zeigt die UI zusätzlich den realen
Availability-Status. Dieser Status wird aus den Fact-Anforderungen des Plugins
erzeugt, nicht aus einer statischen Beschriftung.

## Nächste Schritte

Nach dem Python-Referenzplugin ist die PrimaryModelPolicy die Standardroute.
Als nächste Modellschritte folgen reale Benchmarks und eine nur bei belegtem
Bedarf aktive Specialist-Auswahl. Weitere Sprach- und Spezialplugins werden
anschließend nach demselben Vertrag ergänzt.
