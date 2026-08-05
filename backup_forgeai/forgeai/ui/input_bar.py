from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QTextEdit, QWidget


class InputBar(QWidget):
    submitted = Signal(str)
    def __init__(self):
        super().__init__(); layout = QHBoxLayout(self)
        self.editor = QTextEdit(); self.editor.setPlaceholderText("Nachricht eingeben … (Enter zum Senden, Shift+Enter für Zeilenumbruch)")
        self.editor.setMaximumHeight(110); self.editor.installEventFilter(self)
        self.button = QPushButton("Senden"); self.button.clicked.connect(self.send)
        layout.addWidget(self.editor, 1); layout.addWidget(self.button)

    def eventFilter(self, watched, event):
        if watched is self.editor and event.type() == event.Type.KeyPress and event.key() in (Qt.Key_Return, Qt.Key_Enter) and not event.modifiers() & Qt.ShiftModifier:
            self.send(); return True
        return super().eventFilter(watched, event)

    def send(self):
        text = self.editor.toPlainText().strip()
        if text: self.editor.clear(); self.submitted.emit(text)

    def set_busy(self, busy: bool): self.button.setDisabled(busy); self.editor.setDisabled(busy)
