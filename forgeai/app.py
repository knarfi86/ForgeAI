from PySide6.QtWidgets import QMainWindow, QLabel, QVBoxLayout, QWidget

class ForgeAIApplication(QMainWindow):
    def __init__(self, app, workspace_manager=None):
        super().__init__()
        self.app = app
        self.workspace_manager = workspace_manager
        
        # Hauptansicht
        main_widget = QWidget()
        layout = QVBoxLayout()
        
        if self.workspace_manager:
            info_label = QLabel(self.workspace_manager.get_workspace_info())
            layout.addWidget(info_label)
            
            file_list_label = QLabel(f"Files: {len(self.workspace_manager.list_project_files())}")
            layout.addWidget(file_list_label)
        
        main_widget.setLayout(layout)
        self.setCentralWidget(main_widget)
    
    def show(self):
        # Anzeigen der Hauptanwendung
        print("ForgeAI Application is running")
