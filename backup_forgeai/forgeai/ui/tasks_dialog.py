"""Small local task-management dialog for the active project."""

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout,
    QLineEdit, QListWidget, QListWidgetItem, QPushButton, QTextEdit,
    QVBoxLayout,
)

from forgeai.core.task_manager import TaskManager


class TasksDialog(QDialog):
    """Allows local tasks to be recorded and their status to be updated."""

    def __init__(self, manager: TaskManager, project_path: Path, parent=None):
        super().__init__(parent)
        self.manager, self.project_path = manager, project_path
        self.setWindowTitle(f"Aufgaben – {project_path.name}")
        self.resize(620, 420)
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        self.tasks = QListWidget()
        form = QFormLayout()
        self.title = QLineEdit()
        self.description = QTextEdit()
        self.description.setFixedHeight(70)
        self.priority = QComboBox()
        self.priority.addItems(["LOW", "MEDIUM", "HIGH", "CRITICAL"])
        form.addRow("Titel", self.title)
        form.addRow("Beschreibung", self.description)
        form.addRow("Priorität", self.priority)
        add_button = QPushButton("Aufgabe anlegen")
        add_button.clicked.connect(self.create_task)
        done_button = QPushButton("Als erledigt markieren")
        done_button.clicked.connect(self.mark_done)
        buttons = QHBoxLayout()
        buttons.addWidget(add_button)
        buttons.addWidget(done_button)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        layout.addWidget(self.tasks, 1)
        layout.addLayout(form)
        layout.addLayout(buttons)
        layout.addWidget(close)

    def refresh(self) -> None:
        self.tasks.clear()
        for task in self.manager.list_for_project(self.project_path):
            item = QListWidgetItem(f"[{task['status']}] {task['priority']}: {task['title']}")
            item.setData(256, task["id"])
            self.tasks.addItem(item)

    def create_task(self) -> None:
        title = self.title.text().strip()
        if not title:
            return
        self.manager.create(self.project_path, title, self.description.toPlainText().strip(), self.priority.currentText(), [])
        self.title.clear()
        self.description.clear()
        self.refresh()

    def mark_done(self) -> None:
        item = self.tasks.currentItem()
        if item:
            from forgeai.core.models import TaskStatus
            self.manager.update_status(item.data(256), TaskStatus.DONE)
            self.refresh()
