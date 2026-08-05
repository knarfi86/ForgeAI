from PySide6.QtWidgets import QMainWindow

class ForgeAIApplication(QMainWindow):
    def __init__(self, app, workspace_manager=None):
        super().__init__()
        self.app = app
        self.workspace_manager = workspace_manager
    
    def show(self):
        # Anzeigen der Hauptanwendung
        print("ForgeAI Application is running")
        
        if self.workspace_manager:
            workspace_info = self.workspace_manager.get_workspace_info()
            print(workspace_info)
