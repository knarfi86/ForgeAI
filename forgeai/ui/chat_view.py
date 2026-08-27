from PySide6.QtWidgets import QScrollArea, QVBoxLayout, QWidget

from forgeai.core.workspace_tools import ChangePreview
from forgeai.ui.change_proposal import ChangeProposal
from forgeai.widgets.markdown_view import MarkdownView


class ChatView(QScrollArea):
    def __init__(self):
        super().__init__(); self.setWidgetResizable(True)
        self.container = QWidget(); self.layout = QVBoxLayout(self.container); self.layout.addStretch()
        self.setWidget(self.container); self.pending = None

    def clear_messages(self):
        while self.layout.count() > 1:
            item = self.layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self.pending = None

    def add_message(self, role: str, content: str) -> MarkdownView:
        view = MarkdownView(content)
        view.setObjectName("userMessage" if role == "user" else "assistantMessage")
        self.layout.insertWidget(self.layout.count() - 1, view)
        self.pending = view if role == "assistant" else None
        self._scroll_bottom(); return view

    def append_stream(self, text: str) -> None:
        if self.pending:
            content = self.pending.content + text
            self.pending.set_streaming_content(content)
            self._scroll_bottom()

    def add_change_proposal(self, previews: list[ChangePreview], apply_changes) -> None:
        proposal = ChangeProposal(previews, apply_changes)
        proposal.setObjectName("assistantMessage")
        self.layout.insertWidget(self.layout.count() - 1, proposal)
        self._scroll_bottom()

    def _scroll_bottom(self):
        bar = self.verticalScrollBar(); bar.setValue(bar.maximum())
