from pathlib import Path

import pytest

PySide6 = pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication

from forgeai.core.file_indexer import FileIndexer
from forgeai.core.filesystem import FileSystem
from forgeai.core.workspace_database import WorkspaceDatabase
from forgeai.core.workspace_manager import WorkspaceManager
from forgeai.ui.access_grants_dialog import AccessGrantsDialog


def test_access_grants_dialog_reflects_global_and_external_grants(tmp_path: Path):
    app = QApplication.instance() or QApplication([])
    database = WorkspaceDatabase(tmp_path / "workspace.db")
    manager = WorkspaceManager(database, FileIndexer(database, FileSystem()))
    target = tmp_path / "file.txt"
    target.write_text("hello", encoding="utf-8")
    manager.grant_external_ai_access(target)
    manager.set_global_read_access(True)

    dialog = AccessGrantsDialog(manager)

    assert dialog.global_read.isChecked()
    assert dialog.list.count() == 1
    assert str(target.resolve()) in dialog.list.item(0).text()
    dialog.close()
    app.processEvents()
