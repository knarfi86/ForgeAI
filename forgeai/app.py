import logging

from PySide6.QtWidgets import QApplication

from forgeai.config import Config
from forgeai.core.logging_setup import configure_logging
from forgeai.core.workspace_database import WorkspaceDatabase
from forgeai.ui.main_window import MainWindow


class ForgeAIApplication:
    def __init__(self, qt_app: QApplication):
        Config.ensure_directories()
        configure_logging(Config.LOG_PATH)
        logging.getLogger("forgeai").info("ForgeAI is starting")
        self.database = WorkspaceDatabase(Config.DATABASE_PATH)
        self.window = MainWindow(self.database)
        qt_app.aboutToQuit.connect(self.database.close)

    def show(self) -> None:
        self.window.show()
