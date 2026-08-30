from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class Sidebar(QWidget):
    new_chat_requested = Signal()
    delete_chats_requested = Signal(list)
    delete_all_chats_requested = Signal()
    chat_selected = Signal(int)

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        new_button = QPushButton("+ Neuer Chat")
        new_button.clicked.connect(self.new_chat_requested)

        self.chats = QListWidget()
        self.chats.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.chats.itemSelectionChanged.connect(self._select)

        delete_button = QPushButton("\u0041usgew\u00e4hlte l\u00f6schen")
        delete_button.clicked.connect(self._delete_selected)

        delete_all_button = QPushButton("Alle Chats l\u00f6schen")
        delete_all_button.clicked.connect(self._delete_all)

        layout.addWidget(new_button)
        layout.addWidget(self.chats, 1)
        layout.addWidget(delete_button)
        layout.addWidget(delete_all_button)

    def populate(self, chats, selected_id: int | None = None) -> None:
        self.chats.blockSignals(True)
        self.chats.clear()

        for chat in chats:
            item = self._item(chat["title"], chat["id"])
            self.chats.addItem(item)

            if chat["id"] == selected_id:
                item.setSelected(True)
                self.chats.setCurrentItem(item)

        self.chats.blockSignals(False)

    def _item(self, text, identifier):
        from PySide6.QtWidgets import QListWidgetItem

        item = QListWidgetItem(text)
        item.setData(256, identifier)
        return item

    def _select(self):
        if item := self.chats.currentItem():
            self.chat_selected.emit(item.data(256))

    def _delete_selected(self):
        items = self.chats.selectedItems()
        if not items:
            return

        chat_ids = [item.data(256) for item in items]
        self.delete_chats_requested.emit(chat_ids)

    def _delete_all(self):
        if self.chats.count() == 0:
            return

        self.delete_all_chats_requested.emit()
