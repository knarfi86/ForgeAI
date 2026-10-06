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
        self.active_model: str | None = None  # Neues Attribut für das aktive Modell
        self.logger = logging.getLogger("forgeai.workspace")
        self.brain = ForgeBrain(database)
        self.analyzer = ProjectAnalyzer(database, indexer.filesystem)
        self._session_grants: dict[Path, str] = {}  # path -> file/directory, session-only

    def open_project(self, path: str | Path) -> ProjectStatistics:
        project = self.filesystem.resolve(path)
        if not self.filesystem.is_directory(project):
            raise ValueError(f"Ungültiger Projektordner: {project}")
        self.database.upsert_project(str(project), project.name)
        self._session_grants.clear()
        self.active_project = project
        statistics = self.indexer.index(project)
        analysis = self.analyzer.analyze(project)
        self.brain.save_analysis(analysis)
        self.logger.info("Created project analysis for %s", project)
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
        relative = target.relative_to(self.active_project).as_posix()
        row = self.database.fetchone(
            "SELECT grant_type FROM ai_access_grants WHERE project_path=? AND relative_path=?",
            (str(self.active_project), relative),
        )
        self.database.execute(
            "DELETE FROM ai_access_grants WHERE project_path=? AND relative_path=?",
            (str(self.active_project), relative),
        )
        if row:
            self._purge_legacy_inherited_copies(
                self.active_project,
                target,
                row["grant_type"],
            )
        self.logger.info("Revoked AI read access to %s", target)

    def _purge_legacy_inherited_copies(
        self,
        source_root: Path,
        source_target: Path,
        grant_type: str,
    ) -> None:
        """Remove child rows created by the pre-dynamic inheritance implementation.

        Older ForgeAI builds copied inherited grants into nested project rows and
        lost their provenance. When the source grant is revoked we prefer the safe
        outcome: matching descendant copies are removed as well.
        """
        project_rows = self.database.fetchall(
            "SELECT DISTINCT project_path FROM ai_access_grants WHERE project_path != ?",
            (str(source_root),),
        )
        for project_row in project_rows:
            child_root = self.filesystem.resolve(project_row["project_path"])
            if child_root == source_root or source_root not in child_root.parents:
                continue

            if grant_type == "file":
                if child_root not in source_target.parents:
                    continue
                child_relative = source_target.relative_to(child_root).as_posix()
            elif source_target == child_root or source_target in child_root.parents:
                child_relative = "."
            elif child_root in source_target.parents:
                child_relative = source_target.relative_to(child_root).as_posix()
            else:
                continue

            self.database.execute(
                "DELETE FROM ai_access_grants "
                "WHERE project_path=? AND relative_path=? AND grant_type=?",
                (str(child_root), child_relative, grant_type),
            )

    def ai_grants(self):
        """Return grants explicitly stored for the active project.

        Inherited parent grants are deliberately not copied into the child project.
        Use ``effective_ai_grants`` when evaluating access.
        """
        if not self.active_project:
            return []
        return self.database.fetchall(
            "SELECT relative_path, grant_type, created_at FROM ai_access_grants WHERE project_path=? ORDER BY created_at",
            (str(self.active_project),),
        )

    def effective_ai_grants(self) -> list[dict[str, str]]:
        """Return direct plus dynamically inherited project read grants.

        A parent-project grant may cover a nested project, but it is never persisted
        as a new child grant. Revoking the parent therefore removes the inherited
        permission immediately.
        """
        if not self.active_project:
            return []

        root = self.active_project
        rows = self.database.fetchall(
            "SELECT project_path, relative_path, grant_type, created_at "
            "FROM ai_access_grants ORDER BY created_at, project_path, relative_path"
        )
        result: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()

        for row in rows:
            source_root = self.filesystem.resolve(row["project_path"])
            source_target = self.filesystem.resolve(source_root / row["relative_path"])
            grant_type = row["grant_type"]

            if source_root == root:
                relative = row["relative_path"]
                origin = "direct"
            elif grant_type == "file" and root in source_target.parents:
                relative = source_target.relative_to(root).as_posix()
                origin = "inherited"
            elif grant_type == "directory" and (
                source_target == root or source_target in root.parents
            ):
                relative = "."
                origin = "inherited"
            elif grant_type == "directory" and root in source_target.parents:
                relative = source_target.relative_to(root).as_posix()
                origin = "inherited"
            else:
                continue

            key = (relative, grant_type)
            if key in seen:
                continue
            seen.add(key)
            result.append(
                {
                    "relative_path": relative,
                    "grant_type": grant_type,
                    "origin": origin,
                    "source_project": str(source_root),
                }
            )

        return result

    def ai_accessible_files(self) -> list[Path]:
        """Return all existing files currently permitted for AI context access."""
        if not self.active_project:
            return []

        root = self.active_project
        result: list[Path] = []
        seen: set[Path] = set()

        targets: list[tuple[Path, str]] = []

        for row in self.effective_ai_grants():
            target = self.filesystem.resolve(root / row["relative_path"])
            if target != root and root not in target.parents:
                continue
            targets.append((target, row["grant_type"]))

        for target, grant_type in sorted(
            self._session_grants.items(),
            key=lambda item: item[0].as_posix().casefold(),
        ):
            if target == root or root in target.parents:
                targets.append((target, grant_type))

        for target, grant_type in targets:
            if grant_type == "file":
                candidates = [target] if self.filesystem.is_file(target) else []
            elif grant_type == "directory":
                if not self.filesystem.is_directory(target):
                    continue
                try:
                    candidates = [
                        directory / name
                        for directory, _, names in self.filesystem.walk(
                            target,
                            FileIndexer.IGNORED_DIRECTORIES,
                        )
                        for name in names
                    ]
                except FileNotFoundError:
                    candidates = []
            else:
                continue

            for candidate in candidates:
                if (
                    self.filesystem.is_file(candidate)
                    and candidate not in seen
                    and candidate != root
                ):
                    seen.add(candidate)
                    result.append(candidate)

        return result


    def grant_external_ai_access(self, path: str | Path) -> None:
        """Persist read-only AI access to one local file or directory.

        External grants never confer project write permission.
        """
        target = self.filesystem.resolve(path)
        if self.filesystem.is_directory(target):
            grant_type = "directory"
        elif self.filesystem.is_file(target):
            grant_type = "file"
        else:
            raise FileNotFoundError(target)
        self.database.execute(
            "INSERT INTO ai_external_access_grants(absolute_path,grant_type) VALUES(?,?) "
            "ON CONFLICT(absolute_path) DO UPDATE SET grant_type=excluded.grant_type",
            (str(target), grant_type),
        )
        self.logger.info("Granted external AI read access to %s", target)

    def revoke_external_ai_access(self, path: str | Path) -> None:
        target = self.filesystem.resolve(path)
        self.database.execute(
            "DELETE FROM ai_external_access_grants WHERE absolute_path=?",
            (str(target),),
        )
        self.logger.info("Revoked external AI read access to %s", target)

    def external_ai_grants(self):
        return self.database.fetchall(
            "SELECT absolute_path, grant_type, created_at "
            "FROM ai_external_access_grants ORDER BY created_at, absolute_path"
        )

    def read_grants(self) -> list[dict[str, str]]:
        """Return user-manageable persistent read grants from both scopes."""
        result: list[dict[str, str]] = []
        if self.active_project:
            for row in self.ai_grants():
                target = self.filesystem.resolve(
                    self.active_project / row["relative_path"]
                )
                result.append(
                    {
                        "scope": "project",
                        "path": str(target),
                        "grant_type": row["grant_type"],
                    }
                )
        for row in self.external_ai_grants():
            result.append(
                {
                    "scope": "external",
                    "path": row["absolute_path"],
                    "grant_type": row["grant_type"],
                }
            )
        return result

    def revoke_read_access(self, path: str | Path, *, scope: str | None = None) -> None:
        """Revoke a persistent read grant without conflating read and write modes."""
        target = self.filesystem.resolve(path)
        if scope == "project":
            self.revoke_ai_access(target)
            return
        if scope == "external":
            self.revoke_external_ai_access(target)
            return

        if self.active_project and (
            target == self.active_project or self.active_project in target.parents
        ):
            relative = target.relative_to(self.active_project).as_posix()
            direct = self.database.fetchone(
                "SELECT 1 FROM ai_access_grants WHERE project_path=? AND relative_path=?",
                (str(self.active_project), relative),
            )
            if direct:
                self.revoke_ai_access(target)
                return
        self.revoke_external_ai_access(target)

    def set_global_read_access(self, enabled: bool) -> None:
        """Allow concrete local read requests without per-path approval.

        This setting never grants write access and never triggers disk-wide scans.
        """
        self.database.execute(
            "INSERT INTO settings(key,value) VALUES('ai_global_read_access',?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            ("true" if enabled else "false",),
        )
        self.logger.info("Global AI read access set to %s", enabled)

    def global_read_access_enabled(self) -> bool:
        row = self.database.fetchone(
            "SELECT value FROM settings WHERE key='ai_global_read_access'"
        )
        return bool(row and str(row["value"]).casefold() in {"1", "true", "yes", "on"})

    def is_read_path_granted(self, path: str | Path) -> bool:
        """Check project, external or global read permission for an existing path."""
        target = self.filesystem.resolve(path)
        if not self.filesystem.is_file(target) and not self.filesystem.is_directory(target):
            return False

        if self.active_project and (target == self.active_project or self.active_project in target.parents):
            if self.is_ai_path_granted(target):
                return True

        if self.global_read_access_enabled():
            return True

        for grant in self.external_ai_grants():
            granted = self.filesystem.resolve(grant["absolute_path"])
            if grant["grant_type"] == "file" and target == granted:
                return True
            if grant["grant_type"] == "directory" and (target == granted or granted in target.parents):
                return True
        return False

    def grant_read_access(self, path: str | Path) -> None:
        """Grant read access in the narrowest appropriate scope."""
        target = self.filesystem.resolve(path)
        if self.active_project and (target == self.active_project or self.active_project in target.parents):
            self.grant_ai_access(target)
            return
        self.grant_external_ai_access(target)

    def expand_read_targets(self, paths: list[str | Path]) -> list[Path]:
        """Expand concrete, already-authorized read targets into files for context."""
        result: list[Path] = []
        seen: set[Path] = set()
        for raw in paths:
            target = self.filesystem.resolve(raw)
            if not self.is_read_path_granted(target):
                continue
            if self.filesystem.is_file(target):
                candidates = [target]
            elif self.filesystem.is_directory(target):
                try:
                    candidates = [
                        directory / name
                        for directory, _, names in self.filesystem.walk(
                            target,
                            FileIndexer.IGNORED_DIRECTORIES,
                        )
                        for name in names
                    ]
                except (FileNotFoundError, PermissionError, OSError):
                    candidates = []
            else:
                candidates = []
            for candidate in candidates:
                candidate = self.filesystem.resolve(candidate)
                if candidate not in seen and self.filesystem.is_file(candidate):
                    seen.add(candidate)
                    result.append(candidate)
        return result

    def grant_session_access(self, path: str | Path) -> None:
        """Grant a typed, temporary project permission until the project closes.

        Existing directories grant their children. Files and non-existent change
        targets are exact-file grants and therefore cannot accidentally authorize
        synthetic descendants such as ``file.txt/child``.
        """
        if not self.active_project:
            return
        target = self.filesystem.resolve(path)
        if target != self.active_project and self.active_project not in target.parents:
            return
        grant_type = "directory" if self.filesystem.is_directory(target) else "file"
        self._session_grants[target] = grant_type
        self.logger.debug("Granted temporary %s session access to %s", grant_type, target)

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
        
        # Check typed session grants first (temporary).
        for session_grant, grant_type in self._session_grants.items():
            if grant_type == "file" and target == session_grant:
                return True
            if grant_type == "directory" and (
                target == session_grant or session_grant in target.parents
            ):
                return True
        
        # Get relative path for grant checking
        relative = target.relative_to(self.active_project).as_posix()
        
        # Check persistent grants
        for grant in self.effective_ai_grants():
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
                for grant in self.effective_ai_grants():
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
                for grant in self.effective_ai_grants():
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
        """Return the existing local analysis; Ollama has no project-analysis API."""
        if not self.active_project:
            return {}
        return self.analyze_project() or {}
