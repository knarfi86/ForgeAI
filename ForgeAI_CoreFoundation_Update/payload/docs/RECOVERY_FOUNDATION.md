# Recovery-Grundgerüst: ContextRefresh und FailureFingerprint

Stand: 2026-10-05. Diese Erweiterung überträgt die ersten allgemeinen
Recovery-Erkenntnisse aus dem n8n-Prototyp nach ForgeAI.

## Aktueller Projektkontext

Vor jedem `AgentRecoveryWorker` führt `MainWindow` folgende Schritte aus:

1. Den alten Agent-Kontext verwerfen.
2. Den Workspace-Index neu einlesen.
3. Falls vorhanden, die Project-Evidence in `AgentReality` aktualisieren.
4. Den Kontext mit `AIContextProvider.build` neu aus den aktuell freigegebenen
   Dateien aufbauen. Das bereits ermittelte Kontextbudget bleibt bestehen.
5. Diesen Kontext an Analyzer, Repairer und Reviewer übergeben und für die
   folgende Coder-Ausführung in `MainWindow` behalten.

Eine Aktualisierung erteilt keine zusätzlichen Lesefreigaben. Neue Dateien
werden berücksichtigt, wenn eine gültige Datei-, Verzeichnis- oder
Session-Freigabe sie umfasst. Scheitert die Aktualisierung, wird der Lauf
`FAILED`; es startet keine Reparatur mit einem veralteten Kontext.

## Fehlersignaturen und Verifikationshistorie

`FailureFingerprint.from_output` erzeugt aus fehlgeschlagenen Testausgaben
eine deterministische Signatur der Form `E-v1-<16 Hex-Zeichen>`.

Die Normalisierung gleicht ANSI-Farben, Zeilenenden, absolute Verzeichnisse,
Quellcode-Zeilennummern, erkannte Speicheradressen, ISO-Zeitstempel,
Laufzeiten und die Zahl erfolgreicher Tests aus. Dateinamen, relative
Testpfade, Testnamen und fachliche Fehlerwerte bleiben erhalten.
Eine leere Ausgabe erhält den expliziten Ersatz `<NO_TEST_OUTPUT>`.

Absolute Pfade werden auf `<PATH>/<Dateiname>` reduziert. Gleichnamige
Dateien in unterschiedlichen absoluten Verzeichnissen können deshalb
dieselbe normalisierte Ortsangabe haben. Die Signatur ist ein Hinweis auf
wiederholte Diagnosen, kein Beweis für identische Ursachen. Beliebige
Runner-Ausgaben werden noch nicht als strukturierte Einzelfehler geparst.

`AgentRun.verification_history` enthält für jede tatsächlich verarbeitete
Verifikation einen unveränderlichen `VerificationRecord` mit:

- Ausführungsrunde und Reparaturzähler zum Testzeitpunkt;
- Erfolg oder Misserfolg;
- unveränderter Testausgabe;
- Fehlersignatur und normalisierter Diagnose bei Misserfolg;
- den Dateipfaden des zugehörigen Plans (`planned_paths`).

Planpfade sind keine Bestätigung tatsächlich geschriebener Dateien. Auch
erfolgreiche Tests werden erfasst, besitzen aber keine Fehlersignatur.
Die vorhandene Zustands-History bleibt davon getrennt und kompatibel.

## Nachgewiesenes Verhalten

Die Regressionstests prüfen frische Dateiinhalte über den realen Workspace
und `AIContextProvider` bis in die Analyzer-, Repairer- und Reviewer-Prompts,
neue Session-Freigaben, den Ausschluss privater Inhalte, den Abbruch bei
fehlgeschlagener Aktualisierung sowie identische, geänderte und anschließend
behobene Fehler über mehrere Ausführungsrunden.

Die Modellantworten werden am Ollama-Netzwerkübergang durch feste Testantworten
ersetzt. Ein echter lokaler Ollama-/Windows-Gesamtlauf ist damit nicht
nachgewiesen. Die vollständige Linux-Testsuite besteht mit 347 Tests.

## Nächste Schritte

Diese Grundlage ändert keine Repair-Budgets oder Freigaben. Sie führt noch
keine automatische Stagnationsentscheidung, Dependency-Eskalation,
Redesign-Schleife, Run-Persistenz nach Neustart oder CompletionGate ein.
Diese Mechanismen können anschließend auf aktuellen Kontexten und der
Verifikationshistorie aufbauen. ComfyUI, Video, Blender, Hunyuan3D und Audio
bleiben spätere Erweiterungen.
