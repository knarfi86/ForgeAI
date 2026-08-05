import sys
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout

class WorkspaceManager:
    def __init__(self):
        self.is_open = False
    
    def open_workspace(self):
        # Logik zur Öffnung des Workspaces
        self.is_open = True
    
    def is_workspace_open(self):
        return self.is_open


class ForgeAIApplication(QMainWindow):
    def __init__(self, app, workspace_manager=None):
        super().__init__()
        self.app = app
        self.workspace_manager = workspace_manager
        
        # Hauptansicht
        main_widget = QWidget()
        layout = QVBoxLayout()
        
        if self.workspace_manager:
            if not self.workspace_manager.is_workspace_open():
                message_box = QMessageBox()
                message_box.setIcon(QMessageBox.Information)
                message_box.setText("No workspace is open. Please open a workspace first.")
                message_box.setWindowTitle("Workspace Not Open")
                message_box.setStandardButtons(QMessageBox.Ok)
                
                if message_box.exec() == QMessageBox.Ok:
                    return
        
        self.status_bar = None

    def show(self):
        super().show()

    def set_status_text(self, text):
        if not self.status_bar:
            self.status_bar = self.statusBar()
        
        if self.status_bar:
            self.status_bar.showMessage(text)
