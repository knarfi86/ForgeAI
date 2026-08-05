"""SQLite persistence for workspace-specific ForgeAI state."""

from pathlib import Path

from forgeai.core.database import Database
from forgeai.core.models import ProjectMode


class WorkspaceDatabase(Database):
    """Extends the base chat database with local workspace records."""

    def __init__(self, path: Path):
        super().__init__(path)
        self._create_workspace_schema()

    def _create_workspace_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS project_files (
                id INTEGER PRIMARY KEY,
                project_path TEXT NOT NULL,
                relative_path TEXT NOT NULL,
                file_type TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                modified_at TEXT NOT NULL DEFAULT '',
                sha256 TEXT NOT NULL DEFAULT '',
                indexed_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(project_path, relative_path)
            );
            CREATE TABLE IF NOT EXISTS project_folders (
                id INTEGER PRIMARY KEY,
                project_path TEXT NOT NULL,
                relative_path TEXT NOT NULL,
                UNIQUE(project_path, relative_path)
            );
            CREATE TABLE IF NOT EXISTS project_state (
                project_path TEXT PRIMARY KEY,
                mode TEXT NOT NULL DEFAULT 'READ_ONLY',
                is_favorite INTEGER NOT NULL DEFAULT 0,
                last_opened_file TEXT,
                window_state BLOB
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY,
                project_path TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                priority TEXT NOT NULL DEFAULT 'MEDIUM',
                status TEXT NOT NULL DEFAULT 'TODO',
                affected_files TEXT NOT NULL DEFAULT '[]',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                completed_at TEXT
            );
            CREATE TABLE IF NOT EXISTS project_knowledge (
                project_path TEXT PRIMARY KEY,
                project_name TEXT NOT NULL,
                languages TEXT NOT NULL DEFAULT '[]',
                frameworks TEXT NOT NULL DEFAULT '[]',
                architecture_decisions TEXT NOT NULL DEFAULT '[]',
                known_problems TEXT NOT NULL DEFAULT '[]',
                open_tasks TEXT NOT NULL DEFAULT '[]',
                last_changes TEXT NOT NULL DEFAULT '[]',
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS project_analysis (
                project_path TEXT PRIMARY KEY,
                project_name TEXT NOT NULL,
                analysis_json TEXT NOT NULL,
                analyzed_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS ai_access_grants (
                id INTEGER PRIMARY KEY,
                project_path TEXT NOT NULL,
                relative_path TEXT NOT NULL,
                grant_type TEXT NOT NULL CHECK(grant_type IN ('file', 'directory')),
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(project_path, relative_path)
            );
            """
        )
        self._ensure_column("project_files", "modified_at", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("project_files", "sha256", "TEXT NOT NULL DEFAULT ''")
        self.connection.commit()

    def _ensure_column(self, table: str, column: str, definition: str) -> None:
        columns = {row["name"] for row in self.connection.execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            self.connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def upsert_project(self, path: str, name: str) -> None:
        self.execute(
            "INSERT INTO projects(path,name) VALUES(?,?) "
            "ON CONFLICT(path) DO UPDATE SET name=excluded.name, "
            "last_opened=CURRENT_TIMESTAMP",
            (path, name),
        )
        self.execute(
            "INSERT INTO project_state(project_path, mode) VALUES(?, ?) "
            "ON CONFLICT(project_path) DO NOTHING",
            (path, ProjectMode.READ_ONLY.value),
        )
