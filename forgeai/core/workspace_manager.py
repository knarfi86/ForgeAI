"""Coordinates the active local project and its persisted workspace state."""

import logging
from pathlib import Path

from forgeai.core.ollama_manager import OllamaManager  # Importiere OllamaManager hier
from forgeai.core.file_indexer import FileIndexer
from forgeai.core.forge_brain import ForgeBrain
from forgeai.core.project_analyzer import ProjectAnalyzer
from forgeai.core.models import ProjectMode, ProjectStatistics
from forgeai.core.workspace_database import WorkspaceDatabase


class WorkspaceManager:
    """Owns opening, closing and querying the active project."""

    def __init__(self, database: WorkspaceDatabase, indexer: FileIndexer):
        self.database = database
        self.indexer = indexer
        self.filesystem = indexer.filesystem
        self.active_project: Path | None = None
        self.active_model: str | None = None  # Neues Attribut für das aktive Modell
        self.logger = logging.getLogger("forgeai.workspace")
        self.brain = ForgeBrain(database)
        self.analyzer = ProjectAnalyzer(database, indexer.filesystem)
        self._session_grants: set[Path] = set()  # Temporary grants for this session

    def open_project(self, path: str | Path) -> ProjectStatistics:
        project = self.filesystem.resolve(path)
        if not self.filesystem.is_directory(project):
            raise ValueError(f"Ungültiger Projektordner: {project}")
        self.database.upsert_project(str(project), project.name)
        self.active_project = project
        self._inherit_parent_ai_grants(project)
        statistics = self.indexer.index(project)
        if self.analyzer.is_self_project(project):
            self.brain.save_analysis(self.analyzer.analyze(project))
            self.logger.info("Created self-analysis for ForgeAI")
        self.logger.info("Opened project %s with %s indexed files", project, statistics.file_count)
        return statistics

    def close_project(self) -> None:
        if self.active_project:
            self.logger.info("Closed project %s", self.active_project)
        self.active_project = None
        self.active_model = None  # Setze das aktive Modell auf None bei Schließen des Projekts
        self._session_grants.clear()  # Clear session grants

    def refresh_index(self) -> ProjectStatistics | None:
        return self.indexer.index(self.active_project) if self.active_project else None

    def analyze_project(self) -> dict | None:
        """Refresh metadata and persist a deterministic local project analysis."""
        if not self.active_project:
            return None
        self.refresh_index()
        analysis = self.analyzer.analyze(self.active_project)
        self.brain.save_analysis(analysis)
        self.logger.info("Analysed project %s", self.active_project)
        return analysis

    def recent_projects(self):
        return self.database.fetchall(
            "SELECT p.path, p.name, s.is_favorite FROM projects p "
            "LEFT JOIN project_state s ON s.project_path=p.path "
            "ORDER BY s.is_favorite DESC, p.last_opened DESC"
        )

    def set_favorite(self, favorite: bool) -> None:
        if self.active_project:
            self.database.execute(
                "UPDATE project_state SET is_favorite=? WHERE project_path=?",
                (int(favorite), str(self.active_project)),
            )

    def project_mode(self) -> ProjectMode:
        if not self.active_project:
            return ProjectMode.READ_ONLY
        row = self.database.fetchone(
            "SELECT mode FROM project_state WHERE project_path=?", (str(self.active_project),)
        )
        return ProjectMode(row["mode"]) if row else ProjectMode.READ_ONLY

    def set_project_mode(self, mode: ProjectMode) -> None:
        if self.active_project:
            self.database.execute(
                "UPDATE project_state SET mode=? WHERE project_path=?",
                (mode.value, str(self.active_project)),
            )

    def grant_ai_access(self, path: str | Path) -> None:
        """Persist an explicit file or directory read grant for the active project."""
        if not self.active_project:
            raise ValueError("Kein Projekt geöffnet.")
        target = self.filesystem.resolve(path)
        if target != self.active_project and self.active_project not in target.parents:
            raise ValueError("KI-Freigaben sind auf das aktive Projekt beschränkt.")
        grant_type = "directory" if self.filesystem.is_directory(target) else "file"
        if not self.filesystem.is_file(target) and grant_type != "directory":
            raise FileNotFoundError(target)
        relative = target.relative_to(self.active_project).as_posix()
        self.database.execute(
            "INSERT INTO ai_access_grants(project_path,relative_path,grant_type) VALUES(?,?,?) "
            "ON CONFLICT(project_path,relative_path) DO UPDATE SET grant_type=excluded.grant_type",
            (str(self.active_project), relative, grant_type),
        )
        self.logger.info("Granted AI read access to %s", target)

    def revoke_ai_access(self, path: str | Path) -> None:
        if not self.active_project:
            return
        target = self.filesystem.resolve(path)
        if target != self.active_project and self.active_project not in target.parents:
            raise ValueError("KI-Freigaben sind auf das aktive Projekt beschränkt.")
        self.database.execute(
            "DELETE FROM ai_access_grants WHERE project_path=? AND relative_path=?",
            (str(self.active_project), target.relative_to(self.active_project).as_posix()),
        )
        self.logger.info("Revoked AI read access to %s", target)

    def ai_grants(self):
        if not self.active_project:
            return []
        return self.database.fetchall(
            "SELECT relative_path, grant_type, created_at FROM ai_access_grants WHERE project_path=? ORDER BY created_at",
            (str(self.active_project),),
        )

    def grant_session_access(self, path: str | Path) -> None:
        """Grant temporary access for this session only (until project closes)."""
        if not self.active_project:
            return
        target = self.filesystem.resolve(path)
        if target != self.active_project and self.active_project not in target.parents:
            return
        self._session_grants.add(target)
        self.logger.debug("Granted temporary session access to %s", target)

    def _inherit_parent_ai_grants(self, project: Path) -> None:
        """Reuse explicit parent-project grants when that project is opened as a workspace."""
        rows = self.database.fetchall(
            "SELECT project_path, relative_path, grant_type FROM ai_access_grants WHERE project_path != ?",
            (str(project),),
        )
        for row in rows:
            source_root = self.filesystem.resolve(row["project_path"])
            target = self.filesystem.resolve(source_root / row["relative_path"])
            if row["grant_type"] == "file" and project in target.parents:
                relative = target.relative_to(project).as_posix()
                grant_type = "file"
            elif row["grant_type"] == "directory" and (target == project or target in project.parents):
                relative = "."
                grant_type = "directory"
            elif row["grant_type"] == "directory" and project in target.parents:
                relative = target.relative_to(project).as_posix()
                grant_type = "directory"
            else:
                continue
            self.database.execute(
                "INSERT INTO ai_access_grants(project_path,relative_path,grant_type) VALUES(?,?,?) "
                "ON CONFLICT(project_path,relative_path) DO UPDATE SET grant_type=excluded.grant_type",
                (str(project), relative, grant_type),
            )

    def is_ai_path_granted(self, path: str | Path) -> bool:
        """Check a file or a path inside a granted directory is available to the AI.
        
        Includes both persistent grants and temporary session grants.
        For non-existent files (e.g., during CREATE operations), checks if the parent
        directory (or any ancestor) is a granted directory.
        """
        if not self.active_project:
            return False
        
        # Resolve the path to an absolute path without checking if it exists
        target = self.filesystem.resolve(path)
        
        # Security: ensure path is within active project
        if target != self.active_project and self.active_project not in target.parents:
            return False
        
        # Check session grants first (temporary)
        if target in self._session_grants:
            return True
        # Also check if target is within a session-granted directory
        for session_grant in self._session_grants:
            if target == session_grant or session_grant in target.parents:
                return True
        
        # Get relative path for grant checking
        relative = target.relative_to(self.active_project).as_posix()
        
        # Check persistent grants
        for grant in self.ai_grants():
            granted = grant["relative_path"]
            grant_type = grant["grant_type"]
            
            # File grants: exact match only (for existing files)
            if grant_type == "file":
                if relative == granted:
                    return True
            
            # Directory grants: also match children and non-existent paths within the directory
            elif grant_type == "directory":
                # Root grant matches everything within project
                if granted == ".":
                    return True
                
                # Exact directory match
                if relative == granted:
                    return True
                
                # Child of directory (existing or non-existent)
                if relative.startswith(f"{granted}/"):
                    return True
        
        # For non-existent files/directories, check if parent directory is granted
        if not self.filesystem.is_file(target) and not self.filesystem.is_directory(target):
            parent_parts = Path(relative).parts[:-1]
            if parent_parts:
                parent_relative = "/".join(parent_parts)
                for grant in self.ai_grants():
                    granted = grant["relative_path"]
                    grant_type = grant["grant_type"]
                    
                    if grant_type == "directory":
                        # Parent directory is granted
                        if parent_relative == granted:
                            return True
                        # Parent directory is within a granted directory
                        if parent_relative.startswith(f"{granted}/"):
                            return True
            else:
                # File in root - root must be granted as directory
                for grant in self.ai_grants():
                    if grant["grant_type"] == "directory" and grant["relative_path"] == ".":
                        return True
        
        return False

    def is_project_open(self) -> bool:
        """Check if a project is currently open."""
        return self.active_project is not None

    def set_active_model(self, model: str) -> None:
        """Set the active model for the current project."""
        if self.active_project:
            self.active_model = model
            self.logger.info("Set active model to %s for project %s", model, self.active_project)
        else:
            raise ValueError("Kein Projekt geöffnet.")

    def get_active_model(self) -> str | None:
        """Get the active model for the current project."""
        return self.active_model

    def analyze_with_ollama(self, base_url: str) -> dict:
        if not self.active_project:
            return {}
        ollama_manager = OllamaManager(base_url)
        return ollama_manager.analyze_project(base_url, str(self.active_project))
