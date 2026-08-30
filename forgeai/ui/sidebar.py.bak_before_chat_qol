from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QListWidget, QPushButton, QVBoxLayout, QWidget


class Sidebar(QWidget):
    new_chat_requested = Signal()
    delete_chat_requested = Signal(int)
    chat_selected = Signal(int)

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        new_button = QPushButton("+ Neuer Chat")
        new_button.clicked.connect(self.new_chat_requested)
        self.chats = QListWidget()
        delete_button = QPushButton("Löschen")
        delete_button.clicked.connect(self._delete_selected)
        self.chats.itemSelectionChanged.connect(self._select)
        layout.addWidget(new_button); layout.addWidget(self.chats, 1); layout.addWidget(delete_button)

    def populate(self, chats, selected_id: int | None = None) -> None:
        self.chats.blockSignals(True); self.chats.clear()
        for chat in chats:
            item = self._item(chat["title"], chat["id"]); self.chats.addItem(item)
            if chat["id"] == selected_id: self.chats.setCurrentItem(item)
        self.chats.blockSignals(False)

    def _item(self, text, identifier):
        from PySide6.QtWidgets import QListWidgetItem
        item = QListWidgetItem(text); item.setData(256, identifier); return item

    def _select(self):
        if item := self.chats.currentItem(): self.chat_selected.emit(item.data(256))

    def _delete_selected(self):
        if item := self.chats.currentItem(): self.delete_chat_requested.emit(item.data(256))
