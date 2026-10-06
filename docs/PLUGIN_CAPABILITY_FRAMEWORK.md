# PluginManager und CapabilityRegistry

Stand: 2026-10-05

## Zweck

ForgeAI trennt den fachneutralen Core von optionalen Spezialfähigkeiten. Der Core
entscheidet über Authority, Evidence, Verification, Recovery und Completion.
Plugins liefern nur Fähigkeiten, deterministische Provider und ausführbare
Adapter.

## Implementierte Core-Komponenten

- `CapabilityRegistry`: registriert deklarative `PluginManifest`-Objekte und
  ordnet explizite Capability-Anforderungen oder konservative Task-Hints
  deterministisch Plugins zu.
- `PluginManager`: verwaltet Aktivierung, autonome Nutzung,
  projektspezifische Freigaben, Abhängigkeiten, Fact-Anforderungen und
  persistierbare Benutzerpräferenzen.
- `CapabilityExecutionPlan`: unveränderlicher, nachvollziehbarer Plan der
  ausgewählten und blockierten Plugins.
- `execute_serial(...)`: führt Plugin-Schritte strikt nacheinander aus. Die
  erste Plugin-Architektur enthält bewusst keine Parallel-Ausführung.
- UI `Werkzeuge -> Plugins & Fähigkeiten`: Kontrollzentrum für Aktivierung,
  autonome Nutzung und projektbezogene Freigaben.

## Aktivierung und Autonomie

Drei Fragen bleiben getrennt:

1. Ist ein Plugin registriert/installiert?
2. Ist es durch den Benutzer aktiviert?
3. Darf Forge es autonom für diesen Auftrag bzw. dieses Projekt auswählen?

Forge darf eine benötigte Capability selbst erkennen, aber niemals ein
abgeschaltetes oder nur manuell freigegebenes Plugin selbst freischalten.
Solche Kandidaten werden im Plan als blockiert geführt.

## Capability-Auswahl

Die Basisschicht ist absichtlich konservativ. Sie nutzt:

- explizite Capability-IDs, die ein späterer Planner liefern kann;
- deklarierte `task_hints` des Plugins;
- bereits beobachtete Projektmarker.

Die Registry liest Projektmarker nicht selbst aus dem Dateisystem. Projektmarker
müssen vorher durch eine maschinelle Evidence-/Fact-Quelle beobachtet worden
sein. Damit bleibt das Script-first-Truth-Prinzip erhalten.

## Fact- und Verification-Anbindung

Ein Plugin kann bei der Registrierung gemeinsam anmelden:

- Fact-Provider;
- Verification-Provider;
- Verification-Profile;
- einen Executor.

Fact-Anforderungen eines Plugins werden unmittelbar vor der Nutzung über den
zentralen `FactService` geprüft. Fehlende oder widersprüchliche Evidence macht
das Plugin nicht verfügbar.

Verification-Profile werden nur deklariert bzw. registriert. Die finale
Completion-Entscheidung bleibt beim zentralen Verification-/Completion-System.

## Ressourcen und serielle Ausführung

Ein `PluginManifest` kann Ressourcen deklarieren:

- GPU erforderlich;
- minimale VRAM-Menge;
- minimale RAM-Menge;
- exklusive Ressourcen.

Der aktuelle Scheduler führt alle Capability-Schritte strikt seriell aus. Damit
werden GPU-intensive Spezialfähigkeiten später nicht versehentlich gleichzeitig
gestartet. Eine mögliche Parallelisierung wäre eine eigene, erneut zu prüfende
Architekturänderung.

## Modellrollen

Plugins dürfen gewünschte Modellrollen wie `coding`, `reasoning`, `creative`
oder `vision` deklarieren. Diese Angaben werden im Capability-Plan gesammelt.
Die PrimaryModelPolicy verwendet standardmäßig das konfigurierte Primärmodell;
automatische Specialist-Auswahl aus den Plugin-Rollen bleibt ein späterer Schritt.

## Nachvollziehbarkeit

Jeder für einen Agentenlauf erzeugte Capability-Plan wird in
`AgentRun.capability_plans` gespeichert und in `RunReality` projiziert.
Damit bleibt sichtbar:

- welche Plugins gewählt wurden;
- welche Capabilities sie liefern sollten;
- warum sie gewählt wurden;
- welche Kandidaten wegen Benutzerfreigaben blockiert waren;
- dass die Ausführung seriell geplant wurde.

## Erstes Referenzplugin: Python

Python ist als erstes reales Capability-Plugin implementiert. Es registriert
einen scriptbasierten Fact-Provider, ein technisches Verification-Profile und
einen eng begrenzten seriellen Executor. Die Plugin-UI zeigt die reale
Verfügbarkeit anhand der Fact-Evidence an.

Damit ist die Schnittstelle für weitere Sprach-, GameDev-, Bild-, Video-, 3D-
und Audio-Plugins praktisch bewiesen. Primary-first Routing ist umgesetzt;
automatische Specialist-Auswahl und Modellbenchmarks bleiben separat.
