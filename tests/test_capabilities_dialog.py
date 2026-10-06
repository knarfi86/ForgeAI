from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from forgeai.core.capability_registry import CapabilityRegistry, PluginManifest
from forgeai.core.plugin_manager import PluginManager
from forgeai.ui.capabilities_dialog import CapabilitiesDialog


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_capabilities_dialog_handles_empty_registry():
    _app()
    manager = PluginManager(CapabilityRegistry())
    dialog = CapabilitiesDialog(manager)
    assert dialog.table is None
    dialog.close()


def test_capabilities_dialog_applies_user_permissions(tmp_path):
    _app()
    manager = PluginManager(CapabilityRegistry())
    manager.register_plugin(
        PluginManifest(
            plugin_id="python",
            name="Python",
            version="1",
            capabilities=("code.python",),
        )
    )
    dialog = CapabilitiesDialog(manager, project_path=tmp_path)
    enabled, autonomous, project_auto = dialog._rows["python"]
    enabled.setChecked(True)
    autonomous.setChecked(True)
    assert project_auto is not None
    project_auto.setChecked(False)

    dialog.apply_preferences()

    prefs = manager.preferences("python")
    assert prefs.enabled is True
    assert prefs.autonomous is True
    assert prefs.autonomous_for(tmp_path) is False
    dialog.close()


def test_capabilities_dialog_shows_python_plugin_ready_status(tmp_path):
    from forgeai.core.fact_evidence_provider import FactRegistry, FactService
    from forgeai.core.verification_framework import VerificationRegistry
    from forgeai.plugins.python_plugin import register_python_plugin

    _app()
    manager = PluginManager(
        CapabilityRegistry(),
        fact_service=FactService(FactRegistry()),
        verification_registry=VerificationRegistry(),
    )
    register_python_plugin(manager)

    dialog = CapabilitiesDialog(manager, project_path=tmp_path)
    assert dialog.table is not None
    assert dialog.table.item(0, 0).text().startswith("Python Development")
    assert dialog.table.item(0, 2).text() == "Bereit"
    dialog.close()
