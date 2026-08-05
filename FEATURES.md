# Features

## Projektverwaltung

- Projekte per Dialog öffnen oder schließen
- zuletzt geöffnete Projekte im Dateimenü
- Favoritenstatus pro Projekt
- persistierter, aktiver Projektmodus

## Projektindex und Dateiansicht

- rekursive Erfassung von Ordnern sowie Python, Markdown, JSON, YAML, XML, Lua und Textdateien
- persistierte Pfade, Typen, Größen und Indexzeitpunkte
- Dateibaum mit Öffnen, Aktualisieren und Explorer-Integration
- schreibgeschützte Dateivorschau mit grundlegender Syntaxhervorhebung
- Indexeinträge mit Größe, Änderungsdatum, Sprache und SHA-256-Hash
- lokale Python-Strukturanalyse für Module, Klassen, Importe und Abhängigkeiten

## Arbeitsumgebung

- Chatverlauf und Ollama-Streaming bleiben vollständig lokal
- Terminal führt PowerShell-Befehle im geöffneten Projekt aus
- Statusleiste zeigt Projekt, Modell, Ollama-Endpunkt, Git-Erkennung und Dateizahl
- Fenstergeometrie, Theme, Schriftgröße, Modell und weitere Einstellungen werden gespeichert

## Projektwissen und Aufgaben

- `ForgeBrain` speichert Architekturentscheidungen, Probleme, Aufgaben, Änderungen, Sprachen und Frameworks als lokale Datenstruktur
- Aufgaben enthalten Titel, Beschreibung, Priorität, Status, betroffene Dateien sowie Erstell- und Abschlusszeit
- Selbstanalyse erkennt ForgeAI als geöffnetes Projekt und erzeugt automatisch Projekt-, Modul- und Klassenübersichten

## Sichere Dateiwerkzeuge

- `read_file`, `read_directory`, `search_files` und `find_text` arbeiten ausschließlich im geöffneten lokalen Projekt
- `replace_text`, `create_file`, `rename_file` und `delete_file` erzeugen eine Vorschau mit Unified Diff
- Änderungen benötigen eine explizite Bestätigung; automatische Schreibvorgänge existieren nicht

## Lokale KI-Freigaben

- Dateien und Ordner im Projektbaum gezielt für die lokale KI freigeben
- Freigaben werden pro Projekt lokal gespeichert und sind jederzeit widerrufbar
- Ohne Freigabe wird kein Projektinhalt an den Chat-Kontext übergeben
