"""Persistence service for project tasks."""

import json
from pathlib import Path

from forgeai.core.models import TaskStatus
from forgeai.core.workspace_database import WorkspaceDatabase


class TaskManager:
    """Creates and updates independently tracked local development tasks."""

    def __init__(self, database: WorkspaceDatabase):
        self.database = database

    def create(self, project_path: Path, title: str, description: str, priority: str,
               affected_files: list[str]) -> int:
        cursor = self.database.execute(
            "INSERT INTO tasks(project_path,title,description,priority,affected_files) VALUES(?,?,?,?,?)",
            (str(project_path), title, description, priority, json.dumps(affected_files)),
        )
        return int(cursor.lastrowid)

    def list_for_project(self, project_path: Path):
        return self.database.fetchall(
            "SELECT * FROM tasks WHERE project_path=? ORDER BY status, created_at DESC",
            (str(project_path),),
        )

    def update_status(self, task_id: int, status: TaskStatus) -> None:
        completed = "CURRENT_TIMESTAMP" if status is TaskStatus.DONE else "NULL"
        self.database.execute(
            f"UPDATE tasks SET status=?, completed_at={completed} WHERE id=?", (status.value, task_id)
        )
