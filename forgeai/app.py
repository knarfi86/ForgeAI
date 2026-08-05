from pathlib import Path

from forgeai.ui.main_window import MainWindow
from forgeai.core.workspace_database import WorkspaceDatabase


class ForgeAIApplication:
    def __init__(self, app):
        self.app = app

        db_path = Path.home() / ".forgeai" / "forgeai.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)

        self.database = WorkspaceDatabase(db_path)

        self.window = MainWindow(self.database)

    def show(self):
        self.window.show()