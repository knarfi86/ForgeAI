# Architektur

ForgeAI ist eine native PySide6-Desktopanwendung. `main.py` erstellt die Qt-Anwendung, `ForgeAIApplication` initialisiert Konfiguration, Logging und die SQLite-Datenbank. `MainWindow` ist ausschließlich die UI-Komposition: Es verbindet Widgets mit fachlichen Diensten, ohne Index- oder Persistenzlogik selbst zu enthalten.

## Kernmodule

| Modul | Verantwortung |
|---|---|
| `WorkspaceManager` | aktives Projekt, Öffnen/Schließen, Favoriten und Projektmodus |
| `FileIndexer` | rekursive Metadatenindexierung unterstützter Textdateien und Ordner |
| `WorkspaceDatabase` | SQLite-Schema für Workspace, Index, Aufgaben und Wissen |
| `TaskManager` | Erstellen, Abfragen und Abschließen lokaler Aufgaben |
| `ForgeBrain` | dauerhaftes, KI-unabhängiges Projektwissen |
| `FileViewer` | schreibgeschützte Text- und Codeansicht mit leichter Hervorhebung |

`Database` bleibt die kleine, allgemeine SQLite-Basis für Chatverlauf und Einstellungen. `WorkspaceDatabase` erweitert diese Basis, statt die bestehende Chat-Persistenz zu ersetzen.

## Sicherheit und Projektmodi

`ProjectMode` definiert `READ_ONLY`, `PROPOSE`, `WRITE_WITH_CONFIRMATION` und den vorbereiteten, aber nicht aktivierten Wert `AUTO_WRITE`. Die derzeitige UI schreibt keine Projektdateien. Der Modus wird pro aktivem Projekt gespeichert und ist daher eine stabile Grundlage für spätere Schreibwerkzeuge.

## Lokale Daten

Anwendungsdaten liegen in `%USERPROFILE%\.forgeai`: SQLite-Datenbank und `logs/ForgeAI.log`. Projektdateien werden nur gelesen und indexiert.

## Workspace und Selbstanalyse

`WorkspaceManager` erzeugt beim Öffnen eines lokalen Projektordners einen Workspace, aktualisiert die Liste zuletzt geöffneter Projekte und indexiert die zulässigen Dateitypen. Der Index speichert pro Datei relativen Pfad, Sprache, Größe, Änderungsdatum und SHA-256-Hash in SQLite.

`ProjectAnalyzer` liest die bekannten Projektdokumente lokal und analysiert Python-Quellen mit dem Python-Standardmodul `ast`. Die dauerhafte ForgeBrain-Analyse enthält Dateien, Ordner, Module, Klassen, Importe, den Abhängigkeitsgraphen, Sprachen, Git-Status, Dokumente und offene Aufgaben. Öffnet ForgeAI seinen eigenen Projektordner, wird diese Analyse automatisch erstellt und als Selbstanalyse markiert.

`FileSystem` ist der zentrale Zugang zu lokalen Projektdateien. `WorkspaceTools` stellt Lese-, Such- und Änderungswerkzeuge bereit. Jede Änderung erzeugt zuerst einen `ChangePreview` mit Unified Diff; Schreiben, Umbenennen und Löschen lösen ohne `confirmed=True` einen Fehler aus.

## KI-Freigaben

`ai_access_grants` speichert pro Projekt explizit freigegebene Dateien und Ordner. `ProjectPanel` löst Freigabe und Widerruf direkt aus dem Dateibaum aus; eine Dialogbestätigung ist erforderlich. `AIContextProvider` löst diese Freigaben auf, liest ausschließlich lokale Vorschau-Dateitypen und begrenzt den übertragenen Kontext auf 48.000 Zeichen sowie 12.000 Zeichen je Datei. Nur dieser Kontext wird zusätzlich zum Chat an die fest konfigurierte lokale Ollama-API übergeben.

## KI-Kommunikation

`MainWindow.send_message` übergibt Chatnachrichten an `OllamaClient.stream_chat`. Der daraus erzeugte `OllamaStreamWorker` sendet einen JSON-POST an die feste lokale Ollama-Route `http://localhost:11434/api/chat` und verarbeitet den NDJSON-Stream. `OllamaClient` lehnt jeden anderen Endpunkt ab; die URL-Einstellung ist schreibgeschützt. Es gibt keine Cloud-Client-Bibliothek und keinen alternativen Antwortpfad.
