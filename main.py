import sys

from PySide6.QtWidgets import QApplication

from forgeai.app import ForgeAIApplication
from workspace_manager import WorkspaceManager


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("ForgeAI")
    
    # Initialisieren des WorkspaceManagers
    workspace_manager = WorkspaceManager()
    
    application = ForgeAIApplication(app, workspace_manager)
    application.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
