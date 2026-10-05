<!-- FORGE:RECOVERY_FOUNDATION:START -->
## Recovery-Grundgerüst (2026-10-05)

- Vor jeder Recovery werden Index, vorhandene Reality-Evidence und Agent-Kontext aktualisiert.
- Die nächste Analyse/Reparatur nutzt aktuelle freigegebene Inhalte und das bestehende Kontextbudget.
- Ein Refresh-Fehler stoppt den Lauf ohne Rückgriff auf den alten Kontext.
- `AgentRun.verification_history` erfasst Testergebnisse, Rundenzähler und Planpfade.
- Fehlgeschlagene Tests erhalten stabile, versionierte `FailureFingerprint`-Signaturen.
- Verifiziert: 347 Tests bestanden in der Linux-Testumgebung; Ollama-Antworten im Integrationstest ersetzt.
- Noch offen: automatische Stagnationsentscheidung, Eskalation, Redesign, CompletionGate und Run-Persistenz.

Details: `docs/RECOVERY_FOUNDATION.md`.
<!-- FORGE:RECOVERY_FOUNDATION:END -->
