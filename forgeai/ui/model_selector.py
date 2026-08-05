from PySide6.QtWidgets import QWidget, QVBoxLayout, QComboBox

class ModelSelector(QWidget):
    model_selected = Signal(str)

    def __init__(self, models: list[str], parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        
        # Modell-Auswahl
        self.model_combo = QComboBox()
        self.model_combo.addItems(models)
        self.model_combo.currentIndexChanged.connect(self._on_model_changed)
        self.layout.addWidget(self.model_combo)

    def _on_model_changed(self, index: int):
        model = self.model_combo.itemText(index)
        self.model_selected.emit(model)
