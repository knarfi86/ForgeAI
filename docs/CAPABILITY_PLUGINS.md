# ForgeAI Capability-Plugin-Architektur

Stand: 2026-10-05

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
- Aktivierungsstatus.

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
Capability-Pläne sowie die UI unter `Werkzeuge -> Plugins & Fähigkeiten`.

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
