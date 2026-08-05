# CHANGELOG

## 0.1.0 - 2023-04-01

### Added
- `get_workspace_info()` method to `WorkspaceManager` class.
- `list_project_files()` method to `WorkspaceManager` class.
- `read_file(path)` method to `WorkspaceManager` class.
- Automatic use of these tools when the user asks about files or the project.
- Friendly message if no project is open and an option to open a project.
- Display of workspace, project name, and number of indexed files in the status bar.

### Changed
- Updated `main.py` to check for an open workspace before starting the application.
- Updated `workspace_manager.py` to include new methods and functionality.
- Updated `forgeai/app.py` to use the new tools and display information in the status bar.
