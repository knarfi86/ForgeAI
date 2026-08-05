"""Coordinates the active local project and its persisted workspace state."""

import logging
from pathlib import Path

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
        self.logger = logging.getLogger("forgeai.workspace")
        self.brain = ForgeBrain(database)
        self.analyzer = ProjectAnalyzer(database, indexer.filesystem)

    def open_project(self, path: str | Path) -> ProjectStatistics:
        project = self.filesystem.resolve(path)
        if not self.filesystem.is_directory(project):
            raise ValueError(f"Ungültiger Projektordner: {project}")
        self.database.upsert_project(str(project), project.name)
        self.active_project = project
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

    def is_project_open(self) -> bool:
        """Check if a project is currently open."""
        return self.active_project is not None
