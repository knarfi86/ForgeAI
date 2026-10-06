# ForgeAI Core-Prinzipien

Stand: 2026-10-05

Dieses Dokument definiert verbindliche Architekturregeln für den ForgeAI-Core.
Fachspezifische Fähigkeiten dürfen diese Regeln erweitern, aber nicht umgehen.

## 1. Core first

Der ForgeAI-Core bleibt fachneutral. Er enthält die allgemeine Infrastruktur für:

- Request-Routing;
- Planung und Review;
- kontrollierte Ausführung;
- Kontext und Reality;
- Verifikation;
- Fehleranalyse und Reparatur;
- Stagnationserkennung und Eskalation;
- Completion-Gates;
- Berechtigungen und Schreibschutz;
- Evidence und Fakten;
- Plugin- und Capability-Verwaltung;
- Modellrouting und Ressourcensteuerung.

Sprach-, Engine-, Medien- oder Domänenwissen gehört nicht in den Core, wenn es
als aktivierbare Capability gekapselt werden kann.

## 2. Script-first Truth

Alles, was objektiv ermittelt, gemessen, gelesen oder ausgeführt werden kann,
wird durch deterministische Werkzeuge ermittelt. Dazu zählen insbesondere
Skripte, APIs, Dateisystemzugriffe, Git, Compiler, Test-Runner, Prozessabfragen
und Programmschnittstellen.

Beispiele:

- Dateiexistenz über das Dateisystem;
- aktiver Branch und Änderungen über Git;
- installierte Modelle über die jeweilige lokale API oder CLI;
- Python-, Blender-, Unreal- oder Tool-Versionen über die ausführbare Software;
- Build-Erfolg über Exit-Code und Build-Log;
- Testerfolg über Test-Runner und Exit-Code;
- VRAM und Hardwarezustand über Systemwerkzeuge;
- ComfyUI-Modelle, Queue und History über Dateiscan oder API;
- Blender-Objekte, Bones und Exportstatus über Blender-Python.

Ein LLM darf solche Fakten erklären und interpretieren. Es ist nicht die
autoritative Quelle für objektiv prüfbare Zustände.

## 3. Wahrheitshierarchie

Bei widersprüchlichen Informationen gilt folgende Priorität:

1. aktuelle direkte System- oder Toolabfrage;
2. aktuelle Datei-, Repository-, Datenbank- oder API-Evidence;
3. aktuelle Test-, Build- oder Prozessausgabe;
4. aktueller Forge-State und Reality-Layer, sofern aus Evidence abgeleitet;
5. LLM-Inferenz;
6. Erinnerung, Chatverlauf oder historische Zusammenfassung.

Eine niedrigere Ebene darf eine höhere Ebene nicht überschreiben.

Erinnerung ist ein Navigationshinweis. Sie kann Forge sagen, wo geprüft werden
sollte, aber nicht, was aktuell wahr ist.

## 4. Fact und Inference bleiben getrennt

Objektive Beobachtungen und Modellinterpretationen werden semantisch getrennt.

Ein Fact soll mindestens enthalten:

- Wert oder Aussage;
- Quelle bzw. Provider;
- Zeitpunkt der Erhebung;
- verwendetes Tool, Script oder API;
- Erfolg bzw. Exit-Code, soweit anwendbar;
- optionale Roh-Evidence oder Referenz darauf.

Eine Inference soll mindestens enthalten:

- abgeleitete Aussage;
- zugrunde liegende Facts bzw. Evidence-Referenzen;
- optional eine Unsicherheits- oder Confidence-Angabe.

Forge darf aus einer Inference keinen Fact machen, nur weil ein LLM sie wiederholt.

## 5. Freshness vor Erinnerung

Fakten können veralten. Vor einer Entscheidung muss Forge prüfen, ob die
vorliegende Evidence für die konkrete Aufgabe noch frisch genug ist.

Beispiele:

- GPU-Auslastung wird unmittelbar neu abgefragt;
- Git-Status wird vor Commit oder Push neu abgefragt;
- Projektkontext wird nach Änderungen neu aufgebaut;
- installierte Modelle werden bei Bedarf neu eingelesen;
- Build- oder Teststatus gilt nur für den dazugehörigen Projektzustand.

Veraltete Evidence darf als Historie erhalten bleiben, aber nicht stillschweigend
als aktueller Zustand verwendet werden.

## 6. LLM-Rolle

LLMs sind für Aufgaben geeignet, bei denen Interpretation, Planung, Generierung,
Review, Fehlersuche oder kreative Entscheidungen nötig sind.

LLMs sollen insbesondere:

- Anforderungen verstehen;
- Pläne erzeugen und prüfen;
- Code oder Inhalte generieren;
- Evidence interpretieren;
- mögliche Ursachen priorisieren;
- Reparatur- oder Eskalationsstrategien vorschlagen.

LLMs sollen nicht:

- Dateizustände erfinden;
- Test- oder Build-Erfolge behaupten;
- installierte Programme oder Modelle aus Erinnerung annehmen;
- aktuelle Hardwarezustände schätzen, wenn sie messbar sind;
- autoritative Fakten ohne Evidence erzeugen.

## 7. Evidence vor Completion

Ein Auftrag gilt erst als erfolgreich abgeschlossen, wenn die dafür erforderliche
Evidence vorhanden ist. Ein positiver LLM-Text ist kein Erfolgsnachweis.

Das `CompletionGate` baut deshalb ausschließlich auf expliziter Evidence auf.
Objektive Completion-Kategorien akzeptieren nur Facts; semantische Inferenz muss
konkrete Fact-Evidence referenzieren.

## 8. Plugins unterliegen dem Core

Capability-Plugins liefern Spezialfähigkeiten, Tools, Adapter, Parser und
Verification-Profile. Sie dürfen die zentralen Regeln nicht umgehen.

Insbesondere dürfen Plugins nicht:

- direkt außerhalb der Authority-Regeln schreiben;
- eigene unkontrollierte Endlosschleifen starten;
- Verifikation durch LLM-Behauptungen ersetzen;
- Completion selbst autoritativ erklären;
- die zentrale Recovery- und Stagnationslogik umgehen;
- ungeprüfte historische Annahmen als aktuelle Facts einspeisen.

## 9. Ziel

Forge soll sich erinnern dürfen, aber nachsehen müssen.

Autonomie entsteht nicht dadurch, dass ein Modell möglichst selbstbewusst
antwortet, sondern dadurch, dass Forge Entscheidungen auf aktuelle, reproduzierbare
und nachvollziehbare Evidence stützt.

## 10. Verification-Provider sind Evidence-Lieferanten, keine Entscheider

Das generische Verification Framework registriert fachliche Prüfer, ohne ihnen
Completion-Hoheit zu geben. Provider liefern strukturierte Beobachtungen bzw.
Evidence; das `CompletionGate` entscheidet weiterhin zentral.

Objektive Provider müssen `FACT` liefern. Ein nicht ausführbarer oder
abgestürzter Verifier erzeugt keinen stillen Erfolg. Fehlende belastbare
Evidence bleibt `UNKNOWN`.

## 11. FactService ist die autoritative Abfrageschicht

Objektiv prüfbare Zustände werden über registrierte maschinelle `FactProvider`
bezogen. Zulässige Quellen sind Scripts, APIs, Dateisystem, Repository,
Datenbank, Runtime oder andere Tools. LLM, Memory und Chat sind keine
Fact-Quellen.

Der `FactService` stempelt Provenance, Laufbezug und Freshness. Nur autoritative
Beobachtungen dürfen innerhalb eines expliziten Freshness-Budgets
wiederverwendet werden. `UNKNOWN` und `ERROR` werden nicht als frische Wahrheit
gecached.

Ein negatives Ergebnis (`ABSENT`) ist nur dann ein Fact, wenn der Provider eine
vollständige negative Prüfung garantiert. „Nicht gefunden“ aus einer partiellen
Suche bleibt `UNKNOWN`.

Details: `docs/FACT_EVIDENCE_PROVIDER.md`.
