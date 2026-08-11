"""Chat-local presentation of unapplied AI file changes."""

from collections.abc import Callable

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

from forgeai.core.workspace_tools import ChangePreview


class ChangeProposal(QWidget):
    """Shows previews and applies them only after the user clicks the button."""

    def __init__(self, previews: list[ChangePreview], apply_changes: Callable[[], tuple[bool, str]]):
        super().__init__()
        self.apply_changes = apply_changes
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(QLabel(f"{len(previews)} vorgeschlagene Dateiänderung(en)"))
        changed_files = "\n".join(f"• {preview.path.name}" for preview in previews)
        files_label = QLabel(f"Betroffene Dateien:\n{changed_files}")
        files_label.setWordWrap(True)
        layout.addWidget(files_label)
        self.diff = QPlainTextEdit("\n".join(preview.diff or f"Neue Datei: {preview.path}" for preview in previews))
        self.diff.setReadOnly(True)
        self.diff.setMaximumHeight(240)
        layout.addWidget(self.diff)
        actions = QHBoxLayout()
        self.status = QLabel("Noch nicht angewendet")
        self.apply_button = QPushButton("Änderungen anwenden")
        self.apply_button.clicked.connect(self._apply)
        actions.addWidget(self.status, 1)
        actions.addWidget(self.apply_button)
        layout.addLayout(actions)

    def _apply(self) -> None:
        success, message = self.apply_changes()
        self.status.setText(message)
        if success:
            self.apply_button.setDisabled(True)
