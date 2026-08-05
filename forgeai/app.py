import sys
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout

class ForgeAIApplication(QMainWindow):
    def __init__(self, app, workspace_manager=None):
        super().__init__()
        self.app = app
        self.workspace_manager = workspace_manager
        
        # Hauptansicht
        main_widget = QWidget()
        layout = QVBoxLayout()
        
        if self.workspace_manager:
            # Hier könnte der Code für die Initialisierung des Workspaces stehen
            pass
        
        self.status_bar = None

    def show(self):
        super().show()

    def set_status_text(self, text):
        if not self.status_bar:
            self.status_bar = self.statusBar()
        
        if self.status_bar:
            self.status_bar.showMessage(text)
