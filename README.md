# ForgeAI

ForgeAI ist eine vollständig lokale KI-Entwicklungsumgebung für Windows. Die Desktop-Anwendung kombiniert PySide6, lokale Ollama-Modelle, SQLite und Git-Statusinformationen; sie verwendet weder Webserver noch Browserkomponenten oder Cloud-APIs.

Die KI-Kommunikation ist fest auf `http://localhost:11434/api/chat` begrenzt. ForgeAI akzeptiert keine Remote-Endpunkte und verwendet keine OpenAI-, GPT-, LiteLLM- oder anderen Cloud-Clients. Standardmodell ist `qwen2.5-coder:latest`; das gewählte lokale Modell erscheint in der Statusleiste.

## Voraussetzungen

- Python 3.11 oder neuer
- [Ollama](https://ollama.com) mit einem lokalen Modell, etwa `qwen2.5-coder:latest`

## Installation und Start

```powershell
cd C:\Users\frank\Desktop\ForgeAI
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
ollama serve
python main.py
```

## Aktueller Funktionsumfang

- Lokaler, streamender Ollama-Chat mit SQLite-Verlauf
- Explizite KI-Freigaben für einzelne Dateien oder Ordner direkt im Projektbaum
- Projekt öffnen, schließen, zuletzt geöffnete Projekte und Favoriten
- Rekursiver Dateindex für Python, Markdown, JSON, YAML, XML, Lua und Textdateien
- Rechter Projektbaum mit Dateigröße, Typ, Kontextmenü und schreibgeschützter Syntaxvorschau
- Lokale Aufgabenverwaltung und dauerhaftes ForgeBrain-Projektwissen
- PowerShell-Terminal im Projektordner, Git-Statusanzeige und lokale Logs
- Persistente Einstellungen für Fenstergröße, Ollama, Theme, Schriftgröße, Speichern und Projektmodus

Weitere technische Details stehen in [ARCHITECTURE.md](ARCHITECTURE.md), der geplante Ausbau in [ROADMAP.md](ROADMAP.md).

## KI-Freigaben

ForgeAI liest Projektinhalte für den Chat nur nach einer expliziten Freigabe. Im Kontextmenü einer Datei oder eines Ordners im rechten Projektbaum **Für KI freigeben** auswählen und den Dialog bestätigen. Die Freigabe wird lokal pro Projekt gespeichert; mit **KI-Freigabe entfernen** kann sie jederzeit widerrufen werden. Nur freigegebene, lesbare Textdateien werden innerhalb fester Größenlimits an die lokale Ollama-Instanz übergeben.

## Prüfung

Nach der Installation lässt sich die Anwendung mit `python main.py` starten. Für eine automatisierte Initialisierungsprüfung ohne sichtbares Fenster kann unter Windows `QT_QPA_PLATFORM=offscreen` gesetzt werden. Die Anwendung benötigt ausschließlich die Abhängigkeiten aus `requirements.txt`; PySide6 stellt die native Qt-Oberfläche bereit und Markdown die Chat-Darstellung.
