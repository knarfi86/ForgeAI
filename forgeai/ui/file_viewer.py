"""Read-only source viewer with lightweight syntax highlighting."""

from pathlib import Path

from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWidgets import QPlainTextEdit, QVBoxLayout, QWidget

from forgeai.core.filesystem import FileSystem


class SyntaxHighlighter(QSyntaxHighlighter):
    """Highlights common source tokens without requiring external lexers."""

    KEYWORDS = ("class", "def", "return", "if", "else", "for", "while", "import", "from", "try", "except", "True", "False", "None")

    def __init__(self, document):
        super().__init__(document)
        self.keyword_format = QTextCharFormat()
        self.keyword_format.setForeground(QColor("#8ab4f8"))
        self.keyword_format.setFontWeight(QFont.Weight.Bold)
        self.string_format = QTextCharFormat()
        self.string_format.setForeground(QColor("#a8d08d"))
        self.comment_format = QTextCharFormat()
        self.comment_format.setForeground(QColor("#7f8c8d"))

    def highlightBlock(self, text: str) -> None:  # noqa: N802 - Qt API name
        for keyword in self.KEYWORDS:
            expression = QRegularExpression(rf"\b{keyword}\b")
            match = expression.globalMatch(text)
            while match.hasNext():
                item = match.next()
                self.setFormat(item.capturedStart(), item.capturedLength(), self.keyword_format)
        for expression, text_format in ((QRegularExpression(r"['\"].*?['\"]"), self.string_format),
                                        (QRegularExpression(r"#.*$"), self.comment_format)):
            match = expression.globalMatch(text)
            while match.hasNext():
                item = match.next()
                self.setFormat(item.capturedStart(), item.capturedLength(), text_format)


class FileViewer(QWidget):
    """Displays previewable project files; it deliberately offers no editing."""

    def __init__(self):
        super().__init__()
        self.filesystem = FileSystem()
        self.editor = QPlainTextEdit()
        self.editor.setReadOnly(True)
        self.editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.highlighter = SyntaxHighlighter(self.editor.document())
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.editor)

    def open_file(self, path: str | Path) -> None:
        file_path = Path(path)
        if not self.filesystem.is_previewable(file_path):
            self.editor.setPlainText("Dieser Dateityp wird noch nicht als Text angezeigt.")
            return
        try:
            self.editor.setPlainText(self.filesystem.read_text(file_path))
        except OSError as error:
            self.editor.setPlainText(f"Datei kann nicht gelesen werden:\n{error}")
