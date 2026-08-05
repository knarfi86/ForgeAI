class WorkspaceManager:
    def __init__(self):
        # Initialisierung des Workspaces
        self.workspace = {}
    
    def add_file(self, path, content):
        # Fügt eine Datei zum Workspace hinzu
        self.workspace[path] = content
    
    def get_file(self, path):
        # Gibt den Inhalt einer Datei zurück
        return self.workspace.get(path, None)
    
    def is_workspace_open(self):
        # Überprüft, ob der Workspace leer ist oder nicht
        return bool(self.workspace)
    
    def get_workspace_info(self):
        # Gibt Informationen über das geöffnete Projekt zurück
        if not self.is_workspace_open():
            return "No workspace is open."
        
        info = "Open Workspace:\n"
        for path, content in self.workspace.items():
            info += f"{path}:\n{content}\n\n"
        return info
