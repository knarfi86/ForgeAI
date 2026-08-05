import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget

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
        
        if not self.workspace_manager or not self.workspace_manager.is_workspace_open():
            label = QLabel("Kein Projekt geöffnet")
            layout.addWidget(label)
        
        main_widget.setLayout(layout)
        self.setCentralWidget(main_widget)
    
    def show(self):
        super().show()

    def set_status_text(self, text):
        pass
    
    def closeEvent(self, event):
        # Ignoriere das Schließen des Fensters
        event.ignore()
