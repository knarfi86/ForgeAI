"""Project navigation panel for the right-hand workspace sidebar."""

from pathlib import Path

from PySide6.QtCore import QItemSelectionModel, Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog, QFileSystemModel, QHBoxLayout, QLabel, QMenu, QPushButton,
    QTreeView, QVBoxLayout, QWidget,
)

from forgeai.core.filesystem import FileSystem


class ProjectPanel(QWidget):
    """Presents an indexed project tree and provides file navigation actions."""

    open_project_requested = Signal(str)
    refresh_requested = Signal()
    file_open_requested = Signal(str)
    ai_access_grant_requested = Signal(str)
    ai_access_revoke_requested = Signal(str)
    ai_access_grant_many_requested = Signal(list)
    ai_access_revoke_many_requested = Signal(list)

    def __init__(self):
        super().__init__()
        self.project_path: Path | None = None
        self.filesystem = FileSystem()
        self.model = QFileSystemModel(self)
        self.model.setRootPath("")
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        heading = QHBoxLayout()
        self.project_name = QLabel("Kein Projekt geöffnet")
        self.open_button = QPushButton("Öffnen")
        self.refresh_button = QPushButton("Aktualisieren")
        self.open_button.clicked.connect(self.open_project)
        self.refresh_button.clicked.connect(self.refresh_requested)
        self.select_all_button = QPushButton("Alle auswählen")
        self.select_all_button.clicked.connect(self.select_all_files)
        heading.addWidget(self.project_name, 1)
        heading.addWidget(self.open_button)
        heading.addWidget(self.refresh_button)
        heading.addWidget(self.select_all_button)
        self.tree = QTreeView()
        self.tree.setModel(self.model)
        self.tree.setSelectionMode(QTreeView.SelectionMode.ExtendedSelection)
        self.model.setHeaderData(0, Qt.Orientation.Horizontal, "Name")
        self.model.setHeaderData(1, Qt.Orientation.Horizontal, "Größe")
        self.model.setHeaderData(2, Qt.Orientation.Horizontal, "Dateityp")
        self.model.setHeaderData(3, Qt.Orientation.Horizontal, "Geändert")
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_context_menu)
        self.tree.doubleClicked.connect(self._open_index)
        layout.addLayout(heading)
        layout.addWidget(self.tree, 1)

    def open_project(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Projekt auswählen")
        if folder:
            self.open_project_requested.emit(folder)

    def set_project(self, folder: str | Path) -> None:
        self.project_path = Path(folder)
        self.project_name.setText(self.project_path.name)
        self.tree.setRootIndex(self.model.index(str(self.project_path)))
        self.tree.setColumnWidth(0, 210)

    def show_context_menu(self, position) -> None:
        index = self.tree.indexAt(position)
        if not index.isValid():
            return
        selection = self.tree.selectionModel()
        if not selection.isSelected(index):
            selection.select(
                index,
                QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows,
            )
        paths = [self.model.filePath(selected) for selected in selection.selectedRows()]
        path = self.model.filePath(index)
        menu = QMenu(self)
        open_action = menu.addAction("Öffnen")
        refresh_action = menu.addAction("Aktualisieren")
        explorer_action = menu.addAction("Im Explorer anzeigen")
        menu.addSeparator()
        grant_action = menu.addAction("Für KI freigeben")
        revoke_action = menu.addAction("KI-Freigabe entfernen")
        suffix = "Dateien" if len(paths) > 1 else "Datei"
        grant_action.setText(f"{len(paths)} {suffix} für KI freigeben")
        revoke_action.setText(f"KI-Freigabe für {len(paths)} {suffix} entfernen")
        action = menu.exec(self.tree.viewport().mapToGlobal(position))
        if action == open_action:
            self._open_path(path)
        elif action == refresh_action:
            self.refresh_requested.emit()
        elif action == explorer_action:
            self.filesystem.show_in_explorer(path)
        elif action == grant_action:
            if len(paths) == 1:
                self.ai_access_grant_requested.emit(path)
            else:
                self.ai_access_grant_many_requested.emit(paths)
        elif action == revoke_action:
            if len(paths) == 1:
                self.ai_access_revoke_requested.emit(path)
            else:
                self.ai_access_revoke_many_requested.emit(paths)

    def select_all_files(self) -> None:
        """Select every project file for one shared context-menu operation."""
        if not self.project_path:
            return
        selection = self.tree.selectionModel()
        selection.clearSelection()
        for directory, _, names in self.filesystem.walk(self.project_path, set()):
            for name in names:
                index = self.model.index(str(directory / name))
                if index.isValid():
                    selection.select(
                        index,
                        QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows,
                    )

    def _open_index(self, index) -> None:
        self._open_path(self.model.filePath(index))

    def _open_path(self, path: str) -> None:
        if self.filesystem.is_file(path):
            self.file_open_requested.emit(path)
