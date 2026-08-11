from PySide6.QtWidgets import QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QSpinBox

from forgeai.config import Config
from forgeai.core.ollama_manager import OllamaManager
from forgeai.ui.model_selector import ModelSelector


class SettingsDialog(QDialog):
    def __init__(self, ollama_url: str, model: str, settings: dict[str, str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Einstellungen")
        layout = QFormLayout(self)

        # Ollama-Adresse
        self.url = QLineEdit(ollama_url)
        self.url.setReadOnly(True)
        layout.addRow("Ollama-Adresse", self.url)

        # Modell-Auswahl
        ollama_manager = OllamaManager(ollama_url)
        models = ollama_manager.list_models()
        if models:
            self.model_selector = ModelSelector(models, parent=self)
            self.model_selector.model_selected.connect(self._on_model_changed)
            layout.addRow("Modell", self.model_selector)
        else:
            self.model_selector = None
            layout.addRow("Keine verfügbaren Modelle")

        # Theme
        self.theme = QComboBox()
        self.theme.addItems(["Dunkel", "Hell"])
        self.theme.setCurrentText(settings.get("theme", "Dunkel"))
        layout.addRow("Theme", self.theme)

        # Schriftgröße
        self.font_size = QSpinBox()
        self.font_size.setRange(8, 24)
        self.font_size.setValue(int(settings.get("font_size", "10")))
        layout.addRow("Schriftgröße", self.font_size)

        # Automatisch speichern
        self.auto_save = QCheckBox()
        self.auto_save.setChecked(settings.get("auto_save", "true") == "true")
        layout.addRow("Automatisch speichern", self.auto_save)

        # Projektmodus
        self.project_mode = QComboBox()
        self.project_mode.addItems(["READ_ONLY", "PROPOSE", "WRITE_WITH_CONFIRMATION", "AUTO_WRITE"])
        self.project_mode.setCurrentText(settings.get("project_mode", "READ_ONLY"))
        layout.addRow("Projektmodus", self.project_mode)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def values(self):
        return {
            "ollama_url": self.url.text().strip(),
            "model": self.model_selector.model_combo.currentText() if self.model_selector else "",
            "theme": self.theme.currentText(),
            "font_size": str(self.font_size.value()),
            "auto_save": str(self.auto_save.isChecked()).lower(),
            "project_mode": self.project_mode.currentText(),
        }

    def _on_model_changed(self, model: str):
        print(f"Modell gewählt: {model}")
