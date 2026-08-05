from PySide6.QtWidgets import QMainWindow

class ForgeAIApplication(QMainWindow):
    def __init__(self, app, workspace_manager=None):
        super().__init__()
        self.app = app
        self.workspace_manager = workspace_manager
    
    def show(self):
        # Anzeigen der Hauptanwendung
        print("ForgeAI Application is running")
