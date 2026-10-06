import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from forgeai.ui import settings_dialog as settings_module


def test_settings_dialog_preserves_selected_primary_model(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(
        settings_module.OllamaClient,
        "list_models",
        lambda self, base_url: ["qwen-small:latest", "gpt-oss:20b"],
    )

    dialog = settings_module.SettingsDialog(
        "http://localhost:11434",
        "gpt-oss:20b",
        {"theme": "Dunkel", "project_mode": "READ_ONLY"},
    )
    try:
        assert dialog.values()["model"] == "gpt-oss:20b"
        layout = dialog.layout()
        labels = []
        for index in range(layout.count()):
            item = layout.itemAt(index)
            widget = item.widget() if item is not None else None
            if widget is not None and hasattr(widget, "text"):
                labels.append(widget.text())
        assert "Primärmodell" in labels
        assert "Modellstrategie" in labels
    finally:
        dialog.close()
        app.processEvents()
