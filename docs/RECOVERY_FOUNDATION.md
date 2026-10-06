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

## RepairHistory und StagnationDetector

`AgentRun.repair_history` erfasst abgeschlossene Reparaturversuche als
unveränderliche `RepairRecord`-Einträge. Ein Eintrag verbindet die vorherige
Fehlersignatur mit Analyse, Reparaturanforderungen, Reparaturplan, geplanten
Dateipfaden und dem danach tatsächlich beobachteten Verifikationsergebnis.
Planpfade bleiben weiterhin Planungsevidence und sind kein Beweis für
tatsächlich geschriebene Dateien.

`StagnationDetector` arbeitet ausschließlich auf aufgezeichneter Evidence.
Er zählt aufeinanderfolgende identische Fehlersignaturen und aufeinanderfolgende
identische Reparatur-Zielmengen. Standardmäßig wird Stagnation erst markiert,
wenn sowohl ein Fehler als auch dieselbe Zielmenge mindestens zweimal
aufeinanderfolgend beobachtet wurden. Ein geänderter Fehler oder ein geändertes
Reparaturziel verhindert damit eine falsche Stagnationsmeldung. Erfolgreiche
Verifikation setzt die Fehlerwiederholung zurück, löscht aber keine Historie.

Die Erkennung bleibt von der Handlungsentscheidung getrennt.
`StagnationDetector` liefert nur Evidence; die darauf folgende Strategie liegt
bei `RecoveryEscalationPolicy`.

## RecoveryEscalation

`RecoveryEscalationPolicy` konsumiert ausschließlich den aufgezeichneten
`StagnationStatus` sowie das konfigurierte Repair-Budget. Die Policy verwendet
kein LLM und liest keinen Quellcode selbst.

Bei aktiver Stagnation und verbleibendem Reparaturbudget erzeugt sie die Aktion
`broaden_analysis`. Analyzer und Repairer erhalten daraufhin zusätzlich einen
strukturierten `RECOVERY_ESCALATION`-Block mit Fehlersignatur, wiederholten
Zielpfaden, Grundcodes, verbleibendem Budget und deterministischen Vorgaben.
Insbesondere darf der zuvor stagnierende Reparaturplan nicht unverändert
wiederholt werden; Caller, Imports, Abhängigkeiten und angrenzende Dateien
dürfen nur auf Basis des aktuellen Projektkontexts berücksichtigt werden.

Ist das konfigurierte Reparaturbudget nach einem fehlgeschlagenen Repair ausgeschöpft,
erzeugt die Policy `stop` unabhängig davon, ob die letzte Fehlersignatur inzwischen
gewechselt hat. Der Orchestrator beendet den Lauf dann
kontrolliert als `FAILED`, statt einen weiteren automatischen Repair-Versuch zu
starten. Historie und Evidence bleiben erhalten.

`AgentRun.recovery_escalation` enthält die aktuelle Entscheidung;
`recovery_escalation_history` bewahrt aktive Eskalationsentscheidungen für die
Nachvollziehbarkeit. Beide werden zusätzlich in `RunReality` projiziert.

Wichtig: `broaden_analysis` erweitert derzeit die Analyseanweisung über den
bereits frisch aufgebauten und freigegebenen Projektkontext. Es erteilt keine
neuen Leserechte und führt noch keinen eigenen Dependency-Scan oder ein
separates Redesign/Replanning durch. Diese weitergehenden Strategien bleiben
spätere Ausbaustufen.

## Nächste Schritte

`CompletionGate` ist jetzt als nächste Core-Stufe umgesetzt. Danach folgen das
konkrete Runtime-/Visual-/Semantic-Provider auf Basis des implementierten Verification-Frameworks,
Fact-/Evidence-Provider mit Freshness-Regeln und persistente Run-Historie. ComfyUI, Video, Blender, Hunyuan3D und Audio bleiben
spätere Capability-Plugins.
