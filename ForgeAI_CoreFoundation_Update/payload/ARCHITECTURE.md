<!-- FORGE:RECOVERY_FOUNDATION:START -->
## Recovery-Grundgerüst: aktueller Kontext und Fehlersignaturen

Vor jedem Recovery-Lauf werden Workspace-Index, vorhandene Reality-Evidence
und der tatsächlich an Analyzer/Repairer übergebene Projektkontext erneuert.
Dateifreigaben und das bestehende Kontextbudget bleiben maßgeblich.
Ein fehlgeschlagener Refresh beendet den Lauf, statt alten Kontext zu nutzen.

Der Orchestrator erfasst Verifikationsergebnisse als unveränderliche
`VerificationRecord`-Einträge in `AgentRun.verification_history`.
Fehlgeschlagene Ergebnisse erhalten eine deterministische, versionierte
`FailureFingerprint`-Signatur. Die bestehende Zustands-History bleibt erhalten.

Diese Daten sind die Grundlage für spätere Stagnationserkennung; automatische
Eskalation und dauerhafte Run-Persistenz sind noch nicht implementiert.
Details und nachgewiesene Grenzen: `docs/RECOVERY_FOUNDATION.md`.
<!-- FORGE:RECOVERY_FOUNDATION:END -->
