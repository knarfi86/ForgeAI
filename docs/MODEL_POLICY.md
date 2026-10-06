# ForgeAI Model Policy

## Ziel

ForgeAI bevorzugt ein starkes **Primärmodell** über einen zusammenhängenden
AgentRun. Rollen wie Planner, Reviewer, Analyzer und Repairer erzwingen nicht
länger automatisch unterschiedliche Modelle.

Das reduziert Modellwechsel, Warmup-/Ladeaufwand und unnötigen Kontextverlust.
Ein Spezialmodell wird nur verwendet, wenn ein Aufrufer es für eine konkrete
Aufgabe ausdrücklich als erforderlich markiert.

## Modellunabhängiger Forge Contract

Forge optimiert seine Arbeitsabläufe nicht auf die Schwächen eines einzelnen
Modells. Der Core definiert weiterhin modellunabhängig:

- Auftrag und Authority,
- Facts und Evidence,
- erwartete strukturierte Ausgabe,
- Verification und Completion,
- FailureFingerprint, Recovery und Stagnation.

Dadurch müssen kleinere Modelle möglichst wenig erraten. Größere Modelle
profitieren von denselben Leitplanken und können ihre zusätzliche Kapazität für
Reasoning statt für Rekonstruktion unklarer Zustände verwenden.

## ModelProfile

`ModelProfile` beschreibt stabile Metadaten eines Modells, unter anderem:

- Provider und Modellname,
- zugehöriger `ModelAdapter`,
- bevorzugte Rollen,
- Specialist-Flag,
- optional bekannte native Kontextgröße.

Benchmarkwerte und automatisch gelernte Qualitätsmetriken sind noch nicht Teil
dieses Schritts.

## PrimaryModelPolicy

`PrimaryModelPolicy` besitzt genau ein Primärmodell. Ohne expliziten
Spezialistenbedarf erhalten alle Agentrollen dieses Modell.

Ein Spezialist muss vorher registriert und für die konkrete Rolle ausdrücklich
mit `specialist_required=True` angefordert werden. Fehlt ein geforderter
Spezialist, schlägt die Auswahl kontrolliert fehl statt still auf irgendein
Modell zurückzufallen.

Nach einem Spezialistenaufruf kehrt die Policy zum Primärmodell zurück.

## ModelAdapter

`ModelAdapter` ist die einzige vorgesehene Stelle für spätere modellspezifische
Anpassungen an Promptstil oder Generierungsoptionen.

Adapter dürfen **nicht** verändern:

- was als Fact gilt,
- welche Authority besteht,
- welche Verification erforderlich ist,
- wann Completion erreicht ist,
- welche Recovery-Grenzen gelten.

Der aktuelle Standardadapter `IdentityModelAdapter` verändert weder Prompt noch
Optionen.

## Kompatibilität

Der bestehende `ModelRouter.set_route(...)` bleibt als explizite manuelle bzw.
Legacy-Route erhalten. Solche Routen überschreiben bewusst die Primary-Policy.
Neue AgentWorker konfigurieren dagegen nur noch das Primärmodell.

Die gespeicherte Einstellung `model` bleibt aus Kompatibilitätsgründen bestehen,
wird in der UI aber als **Primärmodell** bezeichnet.

## Noch nicht enthalten

- automatische Qualitätsbenchmarks,
- automatische Specialist-Auswahl,
- modellbedingte Failure-Eskalation,
- automatische Bewertung installierter Ollama-Modelle,
- Performance-/VRAM-basierte Modellauswahl.

Diese Punkte bauen später auf der hier definierten Primary-first-Policy auf.
