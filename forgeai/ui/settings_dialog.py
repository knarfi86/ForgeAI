from PySide6.QtWidgets import QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QSpinBox

from forgeai.config import Config


class SettingsDialog(QDialog):
    def __init__(self, ollama_url: str, model: str, models: list[str], settings: dict[str, str], parent=None):
        super().__init__(parent); self.setWindowTitle("Einstellungen")
        layout = QFormLayout(self); self.url = QLineEdit(Config.LOCAL_OLLAMA_URL); self.url.setReadOnly(True); self.model = QComboBox(); self.model.setEditable(True)
        self.model.addItems(models or [model]); self.model.setCurrentText(model)
        self.theme = QComboBox(); self.theme.addItems(["Dunkel", "Hell"])
        self.theme.setCurrentText(settings.get("theme", "Dunkel"))
        self.font_size = QSpinBox(); self.font_size.setRange(8, 24); self.font_size.setValue(int(settings.get("font_size", "10")))
        self.auto_save = QCheckBox(); self.auto_save.setChecked(settings.get("auto_save", "true") == "true")
        self.project_mode = QComboBox(); self.project_mode.addItems(["READ_ONLY", "PROPOSE", "WRITE_WITH_CONFIRMATION"])
        self.project_mode.setCurrentText(settings.get("project_mode", "READ_ONLY"))
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        layout.addRow("Ollama-Adresse", self.url); layout.addRow("Modell", self.model); layout.addRow("Theme", self.theme)
        layout.addRow("Schriftgröße", self.font_size); layout.addRow("Automatisch speichern", self.auto_save); layout.addRow("Projektmodus", self.project_mode); layout.addRow(buttons)

    def values(self):
        return {
            "ollama_url": Config.LOCAL_OLLAMA_URL, "model": self.model.currentText().strip(),
            "theme": self.theme.currentText(), "font_size": str(self.font_size.value()),
            "auto_save": str(self.auto_save.isChecked()).lower(), "project_mode": self.project_mode.currentText(),
        }
