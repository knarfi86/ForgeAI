"""Composition root for ForgeAI's desktop interface."""

import base64
import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog, QLabel, QMainWindow, QMessageBox, QSplitter, QToolBar,
    QVBoxLayout, QWidget,
)

from forgeai.ai.change_actions import extract_change_previews
from forgeai.ai.ollama_client import OllamaClient
from forgeai.ai.prompts import SYSTEM_PROMPT
from forgeai.config import Config
from forgeai.core.ai_context import AIContextProvider
from forgeai.core.file_indexer import FileIndexer
from forgeai.core.history import History
from forgeai.core.models import ProjectMode
from forgeai.core.task_manager import TaskManager
from forgeai.core.workspace_database import WorkspaceDatabase
from forgeai.core.workspace_manager import WorkspaceManager
from forgeai.core.workspace_tools import ChangePreview, WorkspaceTools
from forgeai.ui.chat_view import ChatView
from forgeai.ui.file_viewer import FileViewer
from forgeai.ui.input_bar import InputBar
from forgeai.ui.project_panel import ProjectPanel
from forgeai.ui.settings_dialog import SettingsDialog
from forgeai.ui.sidebar import Sidebar
from forgeai.ui.tasks_dialog import TasksDialog
from forgeai.ui.terminal_panel import TerminalPanel


class MainWindow(QMainWindow):
    """Coordinates UI components while services retain workspace state."""

    AI_CONTROL_FILES = {
        "forgeai/ai/change_actions.py",
        "forgeai/core/filesystem.py",
        "forgeai/core/workspace_tools.py",
        "forgeai/ui/change_proposal.py",
        "forgeai/ui/chat_view.py",
        "forgeai/ui/main_window.py",
    }

    def __init__(self, database: WorkspaceDatabase):
        super().__init__()
        self.database = database
        self.logger = logging.getLogger("forgeai.ui")
        self.history = History(database)
        self.workspace = WorkspaceManager(database, FileIndexer(database))
        self.ai_context = AIContextProvider(database, self.workspace.filesystem)
        self.tasks = TaskManager(database)
        self.ollama = OllamaClient()
        self.worker = None
        self.chat_id: int | None = None
        self._pending_user_request = ""
        self._stream_is_action = False
        self.ollama_url = Config.LOCAL_OLLAMA_URL
        self._save_setting("ollama_url", self.ollama_url)
        self.model = self._setting("model", Config.DEFAULT_MODEL)
        self.setWindowTitle(Config.APP_NAME)
        self.setMinimumSize(1000, 650)
        self.resize(1600, 900)
        self._build_ui()
        self._build_menus()
        self._apply_theme()
        self._restore_window()
        self.new_chat()

    def _build_ui(self) -> None:
        toolbar = QToolBar("ForgeAI")
        toolbar.setMovable(False)
        toolbar.addWidget(QLabel("  ForgeAI — lokale KI-Entwicklungsumgebung"))
        self.addToolBar(toolbar)
        self.sidebar = Sidebar()
        self.chat_view = ChatView()
        self.project_panel = ProjectPanel()
        self.file_viewer = FileViewer()
        self.terminal = TerminalPanel()
        self.input_bar = InputBar()
        self.sidebar.new_chat_requested.connect(self.new_chat)
        self.sidebar.delete_chat_requested.connect(self.delete_chat)
        self.sidebar.chat_selected.connect(self.load_chat)
        self.input_bar.submitted.connect(self.send_message)
        self.project_panel.open_project_requested.connect(self.open_project)
        self.project_panel.refresh_requested.connect(self.refresh_index)
        self.project_panel.file_open_requested.connect(self.open_file)
        self.project_panel.ai_access_grant_requested.connect(self.grant_ai_access)
        self.project_panel.ai_access_revoke_requested.connect(self.revoke_ai_access)
        self.project_panel.ai_access_grant_many_requested.connect(self.grant_ai_access_many)
        self.project_panel.ai_access_revoke_many_requested.connect(self.revoke_ai_access_many)
        center_split = QSplitter(Qt.Orientation.Vertical)
        center_split.addWidget(self.chat_view)
        center_split.addWidget(self.file_viewer)
        center_split.setSizes([430, 260])
        top = QSplitter(Qt.Orientation.Horizontal)
        top.addWidget(self.sidebar)
        top.addWidget(center_split)
        top.addWidget(self.project_panel)
        top.setSizes([240, 900, 380])
        lower = QSplitter(Qt.Orientation.Vertical)
        lower.addWidget(top)
        lower.addWidget(self.terminal)
        lower.setSizes([660, 200])
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(lower, 1)
        layout.addWidget(self.input_bar)
        self.setCentralWidget(central)
        self.project_status = QLabel("Projekt: keines")
        self.model_status = QLabel()
        self.backend_status = QLabel("Backend: Ollama lokal")
        self.ollama_status = QLabel("Ollama: unbekannt")
        self.git_status = QLabel("Git: –")
        self.file_status = QLabel("Dateien: 0")
        self.workspace_status = QLabel("Workspace: lokal")
        self.index_status = QLabel("Index: bereit")
        for label in (self.workspace_status, self.project_status, self.index_status, self.backend_status, self.ollama_status, self.model_status, self.git_status, self.file_status):
            self.statusBar().addPermanentWidget(label)
        self._update_status()

    def _build_menus(self) -> None:
        file_menu = self.menuBar().addMenu("Datei")
        file_menu.addAction("Projekt öffnen", self.choose_project)
        file_menu.addAction("Projekt schließen", self.close_project)
        self.recent_menu = file_menu.addMenu("Zuletzt geöffnet")
        self.recent_menu.aboutToShow.connect(self.populate_recent_projects)
        file_menu.addAction("Einstellungen", self.show_settings)
        file_menu.addSeparator()
        file_menu.addAction("Beenden", self.close)
        project_menu = self.menuBar().addMenu("Projekt")
        project_menu.addAction("Projekt analysieren", self.analyze_project)
        project_menu.addAction("Index aktualisieren", self.refresh_index)
        project_menu.addAction("Favorit umschalten", self.toggle_favorite)
        project_menu.addAction("Projektinformationen", self.show_project_information)
        tools_menu = self.menuBar().addMenu("Werkzeuge")
        tools_menu.addAction("Terminal", self.focus_terminal)
        tools_menu.addAction("Aufgaben", self.show_tasks)
        tools_menu.addAction("Logs", self.show_logs)
        ai_menu = self.menuBar().addMenu("KI")
        ai_menu.addAction("Modell wechseln", self.show_settings)
        ai_menu.addAction("Systemprompt", self.show_system_prompt)
        ai_menu.addAction("Kontext anzeigen", self.show_context)
        ollama_menu = self.menuBar().addMenu("Ollama")
        ollama_menu.addAction("Projekt analysieren mit Ollama", self.analyze_project_with_ollama)

    def _apply_theme(self) -> None:
        font_size = self._setting("font_size", "10")
        theme = self._setting("theme", "Dunkel")
        if theme == "Hell":
            self.setStyleSheet(f"QWidget {{ font-family: 'Segoe UI'; font-size: {font_size}pt; }}")
            return
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{ background: #171a1f; color: #e6edf3; font-family: 'Segoe UI'; font-size: {font_size}pt; }}
            QTextEdit, QPlainTextEdit, QTextBrowser, QListWidget, QTreeView, QLineEdit {{ background: #20252b; color: #e6edf3; border: 1px solid #343b45; border-radius: 5px; padding: 5px; }}
            QPushButton {{ background: #2d6cdf; color: white; border: 0; border-radius: 5px; padding: 7px 10px; }}
            QPushButton:hover {{ background: #3c7aed; }} QPushButton:disabled {{ background: #4b5563; }}
            QToolBar, QMenuBar, QStatusBar {{ background: #20252b; border-bottom: 1px solid #343b45; spacing: 8px; }}
            #userMessage {{ background: #1e3a5f; border-radius: 8px; }} #assistantMessage {{ background: #20252b; border-radius: 8px; }}
        """)

    def _setting(self, key: str, default: str) -> str:
        row = self.database.fetchone("SELECT value FROM settings WHERE key=?", (key,))
        return row["value"] if row else default

    def _save_setting(self, key: str, value: str) -> None:
        self.database.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))

    def _restore_window(self) -> None:
        saved = self._setting("window_geometry", "")
        if saved:
            self.restoreGeometry(base64.b64decode(saved.encode("ascii")))

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API name
        self._save_setting("window_geometry", base64.b64encode(bytes(self.saveGeometry())).decode("ascii"))
        event.accept()

    def refresh_chats(self) -> None:
        self.sidebar.populate(self.history.list_chats(), self.chat_id)

    def new_chat(self) -> None:
        self.chat_id = self.history.create_chat()
        self.chat_view.clear_messages()
        self.refresh_chats()

    def delete_chat(self, chat_id: int) -> None:
        self.history.delete_chat(chat_id)
        if chat_id == self.chat_id:
            self.new_chat()
        else:
            self.refresh_chats()

    def load_chat(self, chat_id: int) -> None:
        self.chat_id = chat_id
        self.chat_view.clear_messages()
        for message in self.history.messages(chat_id):
            self.chat_view.add_message(message["role"], message["content"])

    def send_message(self, text: str) -> None:
        if self.worker and self.worker.isRunning() or self.chat_id is None:
            return
        self.history.add_message(self.chat_id, "user", text)
        self._pending_user_request = text
        self._stream_is_action = self._action_response_format(text) is not None
        if len(self.history.messages(self.chat_id)) == 1:
            self.history.title_chat(self.chat_id, text[:42])
        self.chat_view.add_message("user", text)
        self.chat_view.add_message("assistant", "")
        messages = [{"role": "system", "content": SYSTEM_PROMPT + self._change_action_instructions()}]

        model_context_length = self.ollama.get_context_length(
            self.ollama_url,
            self.model,
        ) or 32_768

        # Reserve 20 % for system instructions, chat history and model output.
        num_ctx = max(8_192, int(model_context_length * 0.80))

        # Use 60 % of the remaining request budget for approved project files.
        project_context_tokens = max(4_096, int(num_ctx * 0.60))
        per_file_tokens = max(2_048, project_context_tokens // 2)

        context, included_files = self.ai_context.build(
            self.workspace.active_project,
            max_context_tokens=project_context_tokens,
            max_file_tokens=per_file_tokens,
        )

        self.logger.info(
            "Model %s advertises %s context tokens; using num_ctx=%s, project_context=%s, per_file=%s",
            self.model,
            model_context_length,
            num_ctx,
            project_context_tokens,
            per_file_tokens,
        )
        self.logger.info("Approved files sent to Ollama: %s", included_files)
        if context:
            messages.append({"role": "system", "content": context})
            self.logger.info("Sent %s approved local files to Ollama", len(included_files))
        messages += [{"role": row["role"], "content": row["content"]} for row in self.history.messages(self.chat_id)]
        response_format = self._action_response_format(text)

        self.worker = self.ollama.stream_chat(
            self.ollama_url,
            self.model,
            messages,
            response_format,
            num_ctx=num_ctx,
        )

        if not self._stream_is_action:
            self.worker.token_received.connect(self.chat_view.append_stream)
        self.worker.completed.connect(self._response_done)
        self.worker.failed.connect(self._response_failed)
        self.input_bar.set_busy(True)
        self.worker.start()

    def _response_done(self) -> None:
        if not self.worker:
            self._response_failed("Keine Ollama-Antwort erhalten.")
            return

        if self._stream_is_action:
            raw_content = self.worker.content
        else:
            raw_content = self.chat_view.pending.content if self.chat_view.pending else ""

        if self._stream_is_action:
            content, previews = self._prepare_model_changes(raw_content)
        else:
            content, previews = raw_content, []

        if self.chat_view.pending:
            self.chat_view.pending.set_content(content)

        if content and self.chat_id is not None:
            self.history.add_message(self.chat_id, "assistant", content)

        self.input_bar.set_busy(False)
        self.refresh_chats()

        if previews:
            self.chat_view.add_change_proposal(
                previews,
                lambda: self._apply_change_previews(previews),
            )

        self._stream_is_action = False

    def _action_response_format(self, request: str) -> dict | None:
        """Force structured local-model output for requests that change project files."""
        if not self.workspace.active_project or self.workspace.project_mode() not in {
            ProjectMode.WRITE_WITH_CONFIRMATION, ProjectMode.AUTO_WRITE,
        }:
            return None
        request = request.casefold()
        change_verbs = ("erstelle", "erstell", "anlegen", "anlege", "ändere", "aendere", "bearbeite", "füge", "fuege", "verbessere", "implementiere")
        if not any(verb in request for verb in change_verbs):
            return None
        return {
            "type": "object",
            "properties": {
                "actions": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "oneOf": [
                            {
                                "type": "object",
                                "properties": {
                                    "operation": {"type": "string", "enum": ["create"]},
                                    "path": {"type": "string"},
                                    "content": {"type": "string"},
                                },
                                "required": ["operation", "path", "content"],
                            },
                            {
                                "type": "object",
                                "properties": {
                                    "operation": {"type": "string", "enum": ["create_directory"]},
                                    "path": {"type": "string"},
                                },
                                "required": ["operation", "path"],
                            },
                            {
                                "type": "object",
                                "properties": {
                                    "operation": {"type": "string", "enum": ["replace"]},
                                    "path": {"type": "string"},
                                    "old": {"type": "string"},
                                    "new": {"type": "string"},
                                },
                                "required": ["operation", "path", "old", "new"],
                            },
                        ],
                    },
                },
            },
            "required": ["actions"],
        }

    def _change_action_instructions(self) -> str:
        if not self.workspace.active_project or self.workspace.project_mode() not in {
            ProjectMode.WRITE_WITH_CONFIRMATION, ProjectMode.AUTO_WRITE,
        }:
            return "\n\nDu darfst keine Dateien \u00e4ndern; liefere nur Erkl\u00e4rungen oder Vorschl\u00e4ge."

        return """
WICHTIG: Wenn eine Datei erstellt oder ge\u00e4ndert werden soll, MUSST du eine JSON-Antwort
mit einer actions-Liste ausgeben. Erkl\u00e4rung oder Beispielcode allein reicht nicht
und wird nicht als Datei\u00e4nderung ausgef\u00fchrt.

Das Format ist immer:

{
  "actions": [
    {
      "operation": "create",
      "path": "datei.txt",
      "content": "Inhalt"
    }
  ]
}

Erlaubte Operationen:
- create: Erstellt eine neue Datei.
- create_directory: Erstellt ein neues Verzeichnis.
- replace: Ersetzt exakt vorhandenen Text in einer bestehenden Datei.

Beispiele:

{
  "actions": [
    {
      "operation": "create",
      "path": "datei.txt",
      "content": "Inhalt"
    }
  ]
}

{
  "actions": [
    {
      "operation": "create_directory",
      "path": "neuer-ordner"
    }
  ]
}

{
  "actions": [
    {
      "operation": "replace",
      "path": "datei.py",
      "old": "alter Text",
      "new": "neuer Text"
    }
  ]
}

Regeln:
- Nur create, create_directory und replace verwenden.
- Nur relative Pfade innerhalb des ge\u00f6ffneten Projekts verwenden.
- Niemals absolute Pfade verwenden.
- Keine Dateien l\u00f6schen oder umbenennen.
- Keine pathlib-, open(), write_text(), shutil-, os- oder sonstigen
  Dateischreiboperationen ausgeben.
- Bei bestehenden Dateien immer replace verwenden, wenn vorhandener Inhalt
  ge\u00e4ndert werden soll.
- Das Feld old muss exakt einem bereits vorhandenen zusammenh\u00e4ngenden Textabschnitt
  der Datei entsprechen.
- new darf nur die vom Benutzer gew\u00fcnschte \u00c4nderung enthalten.
- Niemals bereits vorhandene Funktionen, Klassen, Imports oder Dokumentation
  doppelt einf\u00fcgen.
- Vor jeder \u00c4nderung den vorhandenen Dateiinhalt ber\u00fccksichtigen.
- \u00c4ndere nur das, was der Benutzer verlangt.
- Bei mehreren \u00c4nderungen alle Aktionen gemeinsam in der actions-Liste ausgeben.
- Verwende nur Dateien oder Verzeichnisse, die der Benutzer f\u00fcr die KI freigegeben hat.
- Au\u00dferhalb einer erforderlichen Datei\u00e4nderung darfst du normale Erkl\u00e4rungen geben.
"""

    def _prepare_model_changes(self, response: str) -> tuple[str, list[ChangePreview]]:
        """Turn model actions into validated previews without writing any files."""
        project = self.workspace.active_project
        if not project or self.workspace.project_mode() not in {
            ProjectMode.WRITE_WITH_CONFIRMATION, ProjectMode.AUTO_WRITE,
        }:
            return response, []
        visible, previews, errors = extract_change_previews(
            response, WorkspaceTools(project, self.workspace.filesystem)
        )
        permitted_previews: list[ChangePreview] = []
        for preview in previews:
            if self._is_ai_control_file(preview.path):
                errors.append(f"Die KI-Schreibfunktion selbst darf nicht verändert werden: {preview.path.name}.")
                continue
            permitted_previews.append(preview)
        if self.workspace.project_mode() == ProjectMode.AUTO_WRITE and permitted_previews:
            success, message = self._apply_change_previews(permitted_previews)
            visible += f"\n\n*{message}*"
            if success:
                permitted_previews = []
        if errors:
            visible += "\n\n**Dateiänderung nicht vorbereitet:** " + " | ".join(errors)
        return visible, permitted_previews

    def _apply_change_previews(self, previews: list[ChangePreview]) -> tuple[bool, str]:
        """Apply user-approved previews through the existing WorkspaceTools gateway."""
        project = self.workspace.active_project
        if not project:
            return False, "Kein Projekt geöffnet."
        applied = 0
        errors: list[str] = []
        tools = WorkspaceTools(project, self.workspace.filesystem)
        for preview in previews:
            if self._is_ai_control_file(preview.path):
                errors.append(f"Die KI-Schreibfunktion selbst darf nicht verändert werden: {preview.path.name}.")
                continue
            try:
                self.workspace.grant_session_access(preview.path)
                if not self.workspace.is_ai_path_granted(preview.path):
                    errors.append(f"Keine KI-Freigabe für {preview.path.relative_to(project)}.")
                    continue
                tools.apply(preview, confirmed=True)
                applied += 1
            except (OSError, PermissionError) as error:
                errors.append(str(error))
        if applied:
            self.refresh_index()
        if errors:
            return False, f"{applied} Änderung(en) angewendet; Fehler: {' | '.join(errors)}"
        return True, f"{applied} Dateiänderung(en) wurden angewendet."

    @classmethod
    def _is_ai_control_file(cls, path: Path) -> bool:
        source_root = Path(__file__).resolve().parents[2]
        return path.resolve() in {source_root / relative for relative in cls.AI_CONTROL_FILES}

    def _response_failed(self, error: str) -> None:
        self.logger.error("Ollama request failed: %s", error)
        if self.chat_view.pending:
            self.chat_view.pending.set_content(f"**Fehler:** {error}\n\nStarte Ollama und prüfe die Einstellungen.")
        self.input_bar.set_busy(False)

    def choose_project(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            "Projekt auswählen",
            "",
            QFileDialog.Option.DontUseNativeDialog,
        )
        if folder:
            self.open_project(folder)

    def open_project(self, path: str) -> None:
        try:
            statistics = self.workspace.open_project(path)
        except ValueError as error:
            self.logger.warning("Project could not be opened: %s", error)
            QMessageBox.warning(self, "Projekt öffnen", str(error))
            return
        if self.workspace.ai_grants() and self.workspace.project_mode() == ProjectMode.READ_ONLY:
            self.workspace.set_project_mode(ProjectMode.WRITE_WITH_CONFIRMATION)
        self.project_panel.set_project(path)
        self.terminal.set_working_directory(path)
        self._update_status(statistics.file_count, "indexiert")

    def close_project(self) -> None:
        self.workspace.close_project()
        self.project_panel.project_name.setText("Kein Projekt geöffnet")
        self._update_status()

    def refresh_index(self) -> None:
        statistics = self.workspace.refresh_index()
        if statistics:
            self._update_status(statistics.file_count, "indexiert")

    def analyze_project(self) -> None:
        analysis = self.workspace.analyze_project()
        if not analysis:
            QMessageBox.information(self, "Projekt analysieren", "Bitte öffne zuerst ein Projekt.")
            return
        self._update_status(len(analysis["files"]), "analysiert")
        message = (
            f"{analysis['project_name']}: {len(analysis['files'])} Dateien, "
            f"{len(analysis['modules'])} Python-Module, "
            f"{sum(len(items) for items in analysis['classes'].values())} Klassen"
        )
        if analysis["is_self_project"]:
            message += "\nForgeAI analysiert gerade seinen eigenen Quellcode."
        QMessageBox.information(self, "Projektanalyse", message)

    def analyze_project_with_ollama(self) -> None:
        if not self.workspace.active_project:
            QMessageBox.information(self, "Ollama Projektanalyse", "Kein Projekt geöffnet.")
            return
        analysis = self.workspace.analyze_with_ollama(Config.LOCAL_OLLAMA_URL)
        if not analysis:
            QMessageBox.information(self, "Ollama Projektanalyse", "Analyse fehlgeschlagen.")
            return
        self._update_status(len(analysis["files"]), "analysiert mit Ollama")
        message = (
            f"{analysis['project_name']}: {len(analysis['files'])} Dateien, "
            f"{len(analysis['modules'])} Python-Module, "
            f"{sum(len(items) for items in analysis['classes'].values())} Klassen"
        )
        if analysis["is_self_project"]:
            message += "\nForgeAI analysiert gerade seinen eigenen Quellcode."
        QMessageBox.information(self, "Ollama Projektanalyse", message)

    def show_project_information(self) -> None:
        if not self.workspace.active_project:
            QMessageBox.information(self, "Projektinformationen", "Kein Projekt geöffnet.")
            return
        analysis = self.workspace.brain.load_analysis(self.workspace.active_project)
        if not analysis:
            QMessageBox.information(self, "Projektinformationen", "Noch keine Analyse vorhanden.")
            return
        QMessageBox.information(
            self, "Projektinformationen",
            f"Name: {analysis['project_name']}\nDateien: {len(analysis['files'])}\n"
            f"Ordner: {len(analysis['folders'])}\nSprachen: {', '.join(analysis['languages'])}\n"
            f"Git: {'ja' if analysis['git_repository'] else 'nein'}\n"
            f"Selbstanalyse: {'ja' if analysis['is_self_project'] else 'nein'}",
        )

    def open_file(self, path: str) -> None:
        self.file_viewer.open_file(path)
        if self.workspace.active_project:
            self.database.execute("UPDATE project_state SET last_opened_file=? WHERE project_path=?", (path, str(self.workspace.active_project)))

    def grant_ai_access(self, path: str) -> None:
        target_name = self.workspace.filesystem.resolve(path).name
        answer = QMessageBox.question(
            self, "KI-Freigabe", 
            f"{target_name} für die lokale KI freigeben? Der Inhalt wird nur an Ollama auf diesem Computer übergeben.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            # DEBUG: Temporarily output path and active_project before grant
            print(f"[DEBUG grant_ai_access] path={path}")
            print(f"[DEBUG grant_ai_access] active_project={self.workspace.active_project}")
            self.logger.info("[DEBUG grant_ai_access] path=%s", path)
            self.logger.info("[DEBUG grant_ai_access] active_project=%s", self.workspace.active_project)
            
            self.workspace.grant_ai_access(path)
            if self.workspace.project_mode() == ProjectMode.READ_ONLY:
                self.workspace.set_project_mode(ProjectMode.WRITE_WITH_CONFIRMATION)
            self._update_status()

    def revoke_ai_access(self, path: str) -> None:
        self.workspace.revoke_ai_access(path)
        self._update_status()

    def grant_ai_access_many(self, paths: list[str]) -> None:
        answer = QMessageBox.question(
            self, "KI-Freigabe",
            f"{len(paths)} Dateien für die lokale KI freigeben? Die Inhalte werden nur an Ollama auf diesem Computer übergeben.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            for path in paths:
                self.workspace.grant_ai_access(path)
            if self.workspace.project_mode() == ProjectMode.READ_ONLY:
                self.workspace.set_project_mode(ProjectMode.WRITE_WITH_CONFIRMATION)
            self._update_status()

    def revoke_ai_access_many(self, paths: list[str]) -> None:
        for path in paths:
            self.workspace.revoke_ai_access(path)
        self._update_status()

    def populate_recent_projects(self) -> None:
        self.recent_menu.clear()
        for project in self.workspace.recent_projects():
            self.recent_menu.addAction(project["name"], lambda checked=False, path=project["path"]: self.open_project(path))

    def toggle_favorite(self) -> None:
        if not self.workspace.active_project:
            return
        row = self.database.fetchone("SELECT is_favorite FROM project_state WHERE project_path=?", (str(self.workspace.active_project),))
        self.workspace.set_favorite(not bool(row["is_favorite"]))

    def focus_terminal(self) -> None:
        self.terminal.command.setFocus()

    def show_tasks(self) -> None:
        if self.workspace.active_project:
            TasksDialog(self.tasks, self.workspace.active_project, self).exec()

    def show_logs(self) -> None:
        self.file_viewer.open_file(Config.LOG_PATH)

    def show_system_prompt(self) -> None:
        QMessageBox.information(self, "Systemprompt", SYSTEM_PROMPT)

    def show_context(self) -> None:
        project = self.workspace.active_project
        text = f"Projekt: {project or 'keines'}\nModus: {self.workspace.project_mode().value}\nModell: {self.model}"
        QMessageBox.information(self, "Kontext", text)

    def _update_status(self, file_count: int = 0, index_state: str = "bereit") -> None:
        project = self.workspace.active_project
        self.workspace_status.setText("Workspace: lokal")
        grant_count = len(self.workspace.ai_grants())
        self.workspace_status.setText(f"Workspace: lokal | KI-Freigaben: {grant_count}")
        self.index_status.setText(f"Index: {index_state}")
        self.backend_status.setText("Backend: Ollama lokal")
        self.project_status.setText(f"Projekt: {project.name if project else 'keines'}")
        self.model_status.setText(f"Modell: {self.model}")
        self.ollama_status.setText(f"Ollama: {self.ollama_url}")
        git_available = project and self.workspace.filesystem.is_directory(project / ".git")
        self.git_status.setText(f"Git: {'Projekt' if git_available else '–'}")
        self.file_status.setText(f"Dateien: {file_count}")

    def show_settings(self) -> None:
        settings = {row["key"]: row["value"] for row in self.database.fetchall("SELECT key, value FROM settings")}
        if self.workspace.active_project:
            settings["project_mode"] = self.workspace.project_mode().value
        dialog = SettingsDialog(self.ollama_url, self.model, settings, self)
        if dialog.exec():
            values = dialog.values()
            self.ollama_url, self.model = Config.LOCAL_OLLAMA_URL, values["model"]
            for key, value in values.items():
                self._save_setting(key, value)
            if self.workspace.active_project:
                self.workspace.set_project_mode(ProjectMode(values["project_mode"]))
            self._apply_theme()
            self._update_status()
