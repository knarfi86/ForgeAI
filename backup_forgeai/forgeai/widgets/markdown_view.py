import re

import markdown
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QTextBrowser, QVBoxLayout, QWidget

from forgeai.widgets.code_block import CodeBlock


class MarkdownView(QWidget):
    def __init__(self, content: str = ""):
        super().__init__()
        self.content = content
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(8, 8, 8, 8)
        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(True)
        self.browser.setFont(QFont("Segoe UI", 10))
        self.layout.addWidget(self.browser)
        self._render()

    def set_content(self, content: str) -> None:
        self.content = content
        self._render()

    def _render(self) -> None:
        blocks = re.findall(r"```(?:([^\n]*))?\n(.*?)```", self.content, re.S)
        body = re.sub(r"```.*?```", "", self.content, flags=re.S)
        rendered = markdown.markdown(body, extensions=["fenced_code", "tables", "nl2br"])
        self.browser.setHtml(f"<style>body{{color:#e6edf3;background:#20252b}} code{{background:#15191d;padding:2px}}</style>{rendered}")
        for index in reversed(range(self.layout.count())):
            item = self.layout.itemAt(index).widget()
            if item and item is not self.browser:
                item.deleteLater()
        for language, code in blocks:
            self.layout.addWidget(CodeBlock(code, language))
