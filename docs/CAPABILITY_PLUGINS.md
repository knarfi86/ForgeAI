# ForgeAI Capability-Plugin-Architektur

Stand: 2026-10-06

Dieses Dokument beschreibt das Zielbild für schrittweise aktivierbare
Spezialfähigkeiten. Das allgemeine Plugin-/Capability-Grundgerüst ist
implementiert; Python ist als erstes reales Referenzplugin angebunden.

## Grundidee

Spezialfähigkeiten werden nicht dauerhaft in den Core eingebaut. Sie werden als
aktivierbare Capability-Plugins registriert und vom Core orchestriert.

Geplante Capability-Gruppen sind unter anderem:

- Entwicklung: Python, Lua, C#, C++, weitere Sprachen;
- GameDev: Unreal Engine, Unity, Godot, Pygame und projektspezifische Adapter;
- Bild: FLUX, SDXL, ComfyUI und Bildbearbeitung;
- Video: WAN, ComfyUI, Videoverarbeitung und FFmpeg;
- 3D: Hunyuan3D, Blender, Rigging, Export und Validierung;
- Audio: TTS, Voice, Soundeffekte und Audiobearbeitung.

## Core bleibt Orchestrator

Ein Plugin stellt Fähigkeiten bereit. Der Forge-Core behält die Hoheit über:

- Authority und Schreibrechte;
- Request-Routing;
- Task- und Run-State;
- ContextRefresh und Reality;
- Evidence und Facts;
- Verification;
- Repair, Stagnation und Eskalation;
- CompletionGate;
- Modellrouting;
- Ressourcenplanung.

## Plugin-Manifest

Ein Plugin soll deklarativ beschreiben, was es kann und was es benötigt.
Vorgesehene Felder sind:

- stabile Plugin-ID und Version;
- angebotene Capabilities;
- benötigte lokale Programme, APIs oder Executables;
- ausführbare Tool-Adapter bzw. Scripts;
- Verification-Profile;
- optionale Modellrollen;
- Ressourcenbedarf wie GPU, VRAM oder RAM;
- unterstützte Dateitypen oder Projektarten;
- Abhängigkeiten zu anderen Plugins;
- Lifecycle-Status (`available`, `experimental`, `planned`, `unavailable`);
- Aktivierungs- und Autonomiestatus.

Beispielhafte Capability-Namen:

- `code.generate`
- `code.modify`
- `code.test`
- `code.debug`
- `image.generate`
- `image.edit`
- `video.generate`
- `video.edit`
- `model3d.generate`
- `model3d.validate`
- `audio.generate`
- `audio.edit`

## Komposition statt Monolith

Höhere Fähigkeiten dürfen andere Plugins orchestrieren.

Ein GameDev-Plugin kann beispielsweise für ein Unreal-Projekt Capabilities aus
C++, Unreal, Git, Bild und Blender kombinieren, ohne deren Implementierungen zu
kopieren.

Forge soll vor einem Auftrag ermitteln:

1. welche Capabilities benötigt werden;
2. welche davon aktiviert und verfügbar sind;
3. welche lokalen Tools tatsächlich vorhanden sind;
4. welche Verification-Profile für das Ergebnis nötig sind;
5. welche Ressourcen gleichzeitig belegt werden dürfen.

Fehlende Fähigkeiten werden explizit gemeldet. Forge darf sie nicht durch
Halluzination oder stilles Weglassen ersetzen.

Der Planner und Reviewer erhalten dafür einen deterministischen
`CAPABILITY_CONTEXT`. Dieser enthält alle registrierten optionalen Plugins,
ihren Lifecycle-Status, Benutzerautorisierung, Match-/Selection-Status und die
deklarierten Capability-IDs. Der Kontext beschreibt optionale Plugin-/Tool-
Fähigkeiten und schränkt die normale Core-Datei- und Codeplanung nicht ein.

`runtime_availability = not_checked` ist ausdrücklich kein Laufzeitbeweis.
Objektive Fact-Anforderungen werden weiterhin unmittelbar vor einer realen
Plugin-Ausführung über den `FactService` geprüft.

## Script-first auch im Plugin

Plugins sollen objektive Zustände immer über Scripts, APIs oder native Tools
ermitteln.

Beispiele:

- Python-Plugin: Interpreter, Compile und pytest;
- C++-Plugin: Compiler, Build-System und Tests;
- Unreal-Plugin: UBT/UAT, Projektdateien und Editor-/Build-Logs;
- Blender-Plugin: Blender-Python für Scene-, Mesh-, Armature- und Exportprüfung;
- ComfyUI-Plugin: Workflow-JSON, Queue, History und Modelldateien;
- Video-Plugin: FFmpeg/ffprobe für technische Validierung;
- Audio-Plugin: ffprobe bzw. Audiotools für Format-, Dauer- und Kanalprüfung.

## Verification-Profile

Plugins liefern fachliche Prüfschritte, aber nicht die zentrale Entscheidung.

Ein Verification-Profile beschreibt reproduzierbare Checks und deren Evidence.
Der Core führt die Checks aus, sammelt Ergebnisse und entscheidet anhand des
allgemeinen Verification- und Completion-Frameworks. Plugins dürfen dabei
angeben, welche Completion-Evidence-Klassen (`technical`, `runtime`, `visual`,
`semantic`) für eine konkrete Fähigkeit erforderlich sind. Sie liefern jedoch
nur Evidence und Requirements; die finale Entscheidung bleibt beim zentralen
`CompletionGate`.

## Modellrouting

Plugins dürfen Modellrollen anfordern, aber keine fest verdrahtete globale
Modellarchitektur erzwingen.

Beispielhafte Rollen:

- `coding`
- `reasoning`
- `review`
- `creative`
- `vision`

Der zentrale ModelRouter wählt aus den tatsächlich verfügbaren lokalen Modellen.

## Ressourcensteuerung

GPU-intensive Plugins müssen ihren Bedarf deklarieren. Der Core soll verhindern,
dass inkompatible Workloads gleichzeitig VRAM oder andere Ressourcen belegen.

Damit kann Forge später beispielsweise WAN, Hunyuan3D und große lokale LLMs
koordiniert statt gleichzeitig starten.

## Geplante Reihenfolge

Vor der ersten Spezialfähigkeit wird das allgemeine Grundgerüst abgeschlossen:

1. RepairHistory;
2. StagnationDetector;
3. RecoveryEscalation;
4. CompletionGate;
5. generisches Verification-Framework (implementiert);
6. Fact-/Evidence-Provider;
7. PluginManager und CapabilityRegistry;
8. erste Referenz-Capability Python (implementiert);
9. PrimaryModelPolicy nutzen und Specialist-Auswahl mit realen Capability-Anforderungen später prüfen;
10. danach weitere Plugins schrittweise aktivieren.


## Implementierungsstatus

Implementiert sind `CapabilityRegistry`, `PluginManager`, persistierbare
Plugin-Freigaben, projektspezifische Auto-Freigaben, deklarative
Ressourcenanforderungen, Fact-/Verification-Anschluss, strikt serielle
Capability-Pläne, Lifecycle-Status sowie ein deterministischer Planning-Snapshot
für Planner und Reviewer. Die UI liegt unter `Werkzeuge -> Plugins & Fähigkeiten`.

Forge darf registrierte Plugins innerhalb der Benutzerfreigaben automatisch
auswählen. Es darf Plugins jedoch niemals selbst aktivieren oder eine
Projektfreigabe eigenmächtig setzen.

Modellrollen werden bereits deklarativ erfasst, aber noch nicht automatisch auf
konkrete lokale Modelle geroutet. Das Primärmodell ist inzwischen die Standardroute; automatische Specialist-Auswahl wird separat ergänzt.

Details: `docs/PLUGIN_CAPABILITY_FRAMEWORK.md`.


## Python-Referenzplugin

Das eingebaute Plugin `python` beweist die reale Plugin-Schnittstelle. Es
registriert Manifest, Fact-Provider, Verification-Provider/-Profile und einen
seriellen Executor. Interpreter und pytest werden durch echte Subprozesse
geprüft. Das Verification-Profile `python-source` belegt Interpreter und
Syntaxprüfung der Projektquellen.

Die Standardaktion des Executors ist absichtlich nur `inspect`. `compile` oder
`test` werden erst ausgeführt, wenn Forge die entsprechende Plugin-Aktion
explizit anfordert. Das Plugin plant oder schreibt keinen Code selbst; diese
Verantwortung bleibt beim Forge-Core und seinen Agenten.

Details: `docs/PYTHON_PLUGIN.md`.


## Capability Execution Gate

Reale Plugin-/Tool-Ausführung läuft über eine zusätzliche deterministische Schranke.
Der Planning Context ist dabei nur Vorwissen; unmittelbar vor einem Executor werden
Lifecycle/Autorisierung, Abhängigkeiten, registrierter Executor, Runtime-Fakten und
deklarierte Verification Profiles erneut geprüft.

Wichtig: Diese Schranke gilt ausschließlich für optionale Plugin-/Tool-Ausführung.
Normale ROSSA-Core-Planung und Dateiänderungen werden dadurch nicht blockiert.
`manual_only` oder ein fehlendes Plugin ist daher keine globale Aussage darüber, ob
ROSSA Quellcode planen oder über den bestehenden WorkspaceTools-Pfad ändern darf.

`AgentOrchestrator.execute_capability_plan()` ist der vorgesehene Einstiegspunkt für
konkrete zukünftige `plugin_actions`. Das Gate schreibt seine Entscheidung und die
beobachteten FactRecords in den AgentRun. Deklarierte Verification Profiles werden
vor der Plugin-Ausführung als Completion-Anforderung registriert.

## Explizite Plugin-Aktionen im AgentPlan

`AgentPlan` kann jetzt neben Dateiänderungen auch konkrete `plugin_actions`
enthalten. Eine Aktion besitzt in Version 1 exakt diese Form:

```json
{
  "plugin_id": "python",
  "action": "test",
  "parameters": {}
}
```

Der Planner darf nur Aktionen verwenden, die das jeweilige `PluginManifest`
über `PluginActionSpec` deklariert. Freie oder erfundene Aktionsnamen werden
vor der Ausführung deterministisch abgewiesen. Version 1 erlaubt bewusst nur
eine Aktion pro Plugin und Plan.

`manual_only` bedeutet dabei nicht mehr "nicht ausführbar", sondern "nur nach
expliziter Benutzerfreigabe". Wenn eine solche Aktion sichtbar im AgentPlan
steht und der Benutzer den Plan bestätigt, gilt diese Freigabe genau einmal für
den aktuellen `AgentRun`. Die globale Plugin-Autonomie wird dadurch nicht
verändert. `disabled`, `planned` und `unavailable` bleiben hart blockiert.

Die Desktop-Kette führt Plugin-Aktionen erst nach erfolgreich angewendeten
Dateiänderungen aus. Reine Plugin-Pläne können direkt nach der Planfreigabe
laufen. Die Ausführung erfolgt in einem eigenen Worker, damit Tool- oder
Testläufe die UI nicht blockieren.

Nach erfolgreicher Plugin-Ausführung läuft die normale technische
Projektverifikation. Zusätzlich werden alle vom Plugin deklarierten
Verification Profiles in einem separaten Worker ausgeführt und als Evidence an
den `CompletionGate` übergeben. Damit endet ein Capability-Lauf nicht mehr bei
"weitere Evidence ausstehend", sondern kann den Abschluss vollständig belegen.
