import sys

from PySide6.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget, QPushButton, QMessageBox

from forgeai.app import ForgeAIApplication
from workspace_manager import WorkspaceManager


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("ForgeAI")
    
    # Initialisieren des WorkspaceManagers
    workspace_manager = WorkspaceManager()
    
    # Anzeigen der Statusleiste
    status_bar = QMainWindow().statusBar()
    status_bar.showMessage("No project open")
    
    if not workspace_manager.is_workspace_open():
        message_box = QMessageBox()
        message_box.setIcon(QMessageBox.Information)
        message_box.setText("No workspace is open. Please open a workspace first.")
        message_box.setWindowTitle("Workspace Not Open")
        message_box.setStandardButtons(QMessageBox.Ok)
        
        if message_box.exec() == QMessageBox.Ok:
            return 0
    
    application = ForgeAIApplication(app, workspace_manager)
    application.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
