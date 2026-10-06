"""UI for persistent local read permissions outside the active project."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from forgeai.core.workspace_manager import WorkspaceManager


class AccessGrantsDialog(QDialog):
    """Manage file, folder and global read-only AI permissions."""

    def __init__(self, workspace: WorkspaceManager, parent=None):
        super().__init__(parent)
        self.workspace = workspace
        self.setWindowTitle("KI-Lesefreigaben")
        self.resize(720, 430)
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Diese Freigaben gelten nur für lokales Lesen durch Forge/Ollama. "
            "Schreibrechte bleiben weiterhin projektgebunden und bestätigungspflichtig."
        ))
        self.global_read = QCheckBox(
            "Globaler Lesezugriff: konkrete lokale Pfade ohne erneute Rückfrage lesen"
        )
        self.global_read.toggled.connect(self._toggle_global)
        layout.addWidget(self.global_read)

        self.list = QListWidget()
        layout.addWidget(self.list, 1)

        buttons = QHBoxLayout()
        file_button = QPushButton("Datei(en) freigeben …")
        folder_button = QPushButton("Ordner freigeben …")
        revoke_button = QPushButton("Ausgewählte Freigabe entfernen")
        close_button = QPushButton("Schließen")
        file_button.clicked.connect(self._grant_file)
        folder_button.clicked.connect(self._grant_folder)
        revoke_button.clicked.connect(self._revoke_selected)
        close_button.clicked.connect(self.accept)
        buttons.addWidget(file_button)
        buttons.addWidget(folder_button)
        buttons.addWidget(revoke_button)
        buttons.addStretch(1)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)

    def refresh(self) -> None:
        self.global_read.blockSignals(True)
        self.global_read.setChecked(self.workspace.global_read_access_enabled())
        self.global_read.blockSignals(False)
        self.list.clear()
        for row in self.workspace.external_ai_grants():
            kind = "Ordner" if row["grant_type"] == "directory" else "Datei"
            item = QListWidgetItem(f"{kind}: {row['absolute_path']}")
            item.setData(Qt.ItemDataRole.UserRole, row["absolute_path"])
            self.list.addItem(item)

    def _toggle_global(self, enabled: bool) -> None:
        if enabled:
            answer = QMessageBox.question(
                self,
                "Globalen Lesezugriff aktivieren",
                "Forge darf danach konkrete lokale Dateien und Ordner lesen, wenn ein Auftrag sie benötigt, "
                "ohne jedes Mal erneut zu fragen. Es werden keine Laufwerke automatisch gescannt und es "
                "werden keine Schreibrechte erteilt. Aktivieren?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                self.global_read.blockSignals(True)
                self.global_read.setChecked(False)
                self.global_read.blockSignals(False)
                return
        self.workspace.set_global_read_access(enabled)

    def _grant_file(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Datei(en) für Forge freigeben")
        for path in paths:
            self.workspace.grant_external_ai_access(path)
        if paths:
            self.refresh()

    def _grant_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Ordner für Forge freigeben")
        if path:
            self.workspace.grant_external_ai_access(path)
            self.refresh()

    def _revoke_selected(self) -> None:
        item = self.list.currentItem()
        if item is None:
            return
        path = item.data(Qt.ItemDataRole.UserRole)
        if path:
            self.workspace.revoke_external_ai_access(Path(path))
            self.refresh()
