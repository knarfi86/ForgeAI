import sys

from PySide6.QtWidgets import QApplication

from forgeai.app import ForgeAIApplication
from workspace_manager import WorkspaceManager


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("ForgeAI")
    
    # Initialisieren des WorkspaceManagers
    workspace_manager = WorkspaceManager()
    
    if not workspace_manager.is_workspace_open():
        print("No workspace is open. Please open a workspace first.")
        return 1
    
    application = ForgeAIApplication(app, workspace_manager)
    application.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
