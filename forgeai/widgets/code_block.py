from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QHBoxLayout, QPushButton, QPlainTextEdit, QVBoxLayout, QWidget


class CodeBlock(QWidget):
    def __init__(self, code: str, language: str = ""):
        super().__init__()
        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        copy_button = QPushButton("Kopieren")
        copy_button.clicked.connect(lambda: self._copy(code))
        header.addWidget(copy_button)
        header.addStretch()
        layout.addLayout(header)
        editor = QPlainTextEdit(code)
        editor.setReadOnly(True)
        editor.setFont(QFont("Consolas", 10))
        editor.setMaximumHeight(260)
        layout.addWidget(editor)

    def _copy(self, code: str) -> None:
        QApplication.clipboard().setText(code)
