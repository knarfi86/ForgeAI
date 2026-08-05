"""Durable project knowledge model, intentionally independent of AI execution."""

import json
from pathlib import Path

from forgeai.core.workspace_database import WorkspaceDatabase


class ForgeBrain:
    """Stores project knowledge for future local AI features."""

    FIELDS = ("languages", "frameworks", "architecture_decisions", "known_problems", "open_tasks", "last_changes")

    def __init__(self, database: WorkspaceDatabase):
        self.database = database

    def save(self, project_path: Path, project_name: str, **knowledge: list[str]) -> None:
        values = [json.dumps(knowledge.get(field, [])) for field in self.FIELDS]
        self.database.execute(
            "INSERT INTO project_knowledge(project_path,project_name,languages,frameworks,architecture_decisions,known_problems,open_tasks,last_changes) "
            "VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(project_path) DO UPDATE SET "
            "project_name=excluded.project_name,languages=excluded.languages,frameworks=excluded.frameworks,"
            "architecture_decisions=excluded.architecture_decisions,known_problems=excluded.known_problems,"
            "open_tasks=excluded.open_tasks,last_changes=excluded.last_changes,updated_at=CURRENT_TIMESTAMP",
            [str(project_path), project_name, *values],
        )

    def load(self, project_path: Path) -> dict[str, list[str]] | None:
        row = self.database.fetchone("SELECT * FROM project_knowledge WHERE project_path=?", (str(project_path),))
        if not row:
            return None
        return {field: json.loads(row[field]) for field in self.FIELDS}

    def save_analysis(self, analysis: dict) -> None:
        """Persist all locally derived project knowledge in one stable record."""
        self.database.execute(
            "INSERT INTO project_analysis(project_path,project_name,analysis_json) VALUES(?,?,?) "
            "ON CONFLICT(project_path) DO UPDATE SET project_name=excluded.project_name, "
            "analysis_json=excluded.analysis_json, analyzed_at=CURRENT_TIMESTAMP",
            (analysis["project_path"], analysis["project_name"], json.dumps(analysis)),
        )
        self.save(
            Path(analysis["project_path"]), analysis["project_name"],
            languages=analysis["languages"], architecture_decisions=analysis["architecture_files"],
            open_tasks=[task["title"] for task in analysis["open_tasks"]],
        )

    def load_analysis(self, project_path: Path) -> dict | None:
        row = self.database.fetchone("SELECT analysis_json FROM project_analysis WHERE project_path=?", (str(project_path),))
        return json.loads(row["analysis_json"]) if row else None
