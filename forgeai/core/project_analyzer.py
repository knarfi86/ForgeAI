"""Local, deterministic project analysis without any AI or network access."""

import ast
from collections import defaultdict
from pathlib import Path

from forgeai.core.filesystem import FileSystem
from forgeai.core.workspace_database import WorkspaceDatabase


class ProjectAnalyzer:
    """Builds structural project knowledge from indexed files and documents."""

    DOCUMENTS = ("README.md", "ROADMAP.md", "ARCHITECTURE.md", "FEATURES.md", "TASKS.md")

    def __init__(self, database: WorkspaceDatabase, filesystem: FileSystem | None = None):
        self.database = database
        self.filesystem = filesystem or FileSystem()

    def analyze(self, project_path: str | Path) -> dict:
        root = self.filesystem.resolve(project_path)
        records = self.database.fetchall(
            "SELECT relative_path, file_type FROM project_files WHERE project_path=? ORDER BY relative_path",
            (str(root),),
        )
        documents = self._documents(root)
        classes, imports, modules, graph = self._python_structure(root, records)
        languages = sorted({row["file_type"] for row in records})
        folders = [row["relative_path"] for row in self.database.fetchall(
            "SELECT relative_path FROM project_folders WHERE project_path=? ORDER BY relative_path", (str(root),)
        )]
        return {
            "project_name": root.name,
            "project_path": str(root),
            "files": [row["relative_path"] for row in records],
            "folders": folders,
            "classes": classes,
            "imports": imports,
            "modules": modules,
            "languages": languages,
            "git_repository": self.filesystem.is_directory(root / ".git"),
            "documents": documents,
            "readme": documents.get("README.md", ""),
            "architecture_files": [name for name in ("ARCHITECTURE.md", "FEATURES.md") if name in documents],
            "roadmap": documents.get("ROADMAP.md", ""),
            "tasks": documents.get("TASKS.md", ""),
            "dependency_graph": dict(graph),
            "is_self_project": self.is_self_project(root),
            "open_tasks": self._open_tasks(str(root)),
        }

    def _documents(self, root: Path) -> dict[str, str]:
        return {name: self.filesystem.read_text(root / name) for name in self.DOCUMENTS
                if self.filesystem.is_file(root / name)}

    def _python_structure(self, root: Path, records) -> tuple[dict[str, list[str]], dict[str, list[str]], list[str], dict[str, list[str]]]:
        classes: dict[str, list[str]] = {}
        imports: dict[str, list[str]] = {}
        modules: list[str] = []
        graph: defaultdict[str, list[str]] = defaultdict(list)
        for record in records:
            relative_path = record["relative_path"]
            if not relative_path.endswith(".py"):
                continue
            source = self.filesystem.read_text(root / relative_path)
            module = self._module_name(relative_path)
            modules.append(module)
            try:
                tree = ast.parse(source, filename=relative_path)
            except SyntaxError:
                classes[relative_path] = []
                imports[relative_path] = []
                continue
            classes[relative_path] = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
            imported = self._imports(tree)
            imports[relative_path] = imported
            graph[module] = imported
        return classes, imports, modules, graph

    @staticmethod
    def _module_name(relative_path: str) -> str:
        path = Path(relative_path).with_suffix("")
        return ".".join(path.parts[:-1] if path.name == "__init__" else path.parts)

    @staticmethod
    def _imports(tree: ast.AST) -> list[str]:
        result: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                result.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                prefix = "." * node.level
                result.append(f"{prefix}{node.module or ''}")
        return sorted(set(result))

    def _open_tasks(self, project_path: str) -> list[dict[str, str]]:
        return [dict(row) for row in self.database.fetchall(
            "SELECT title, priority, status FROM tasks WHERE project_path=? AND status != 'DONE' ORDER BY created_at DESC",
            (project_path,),
        )]

    def is_self_project(self, root: str | Path) -> bool:
        root = self.filesystem.resolve(root)
        source_root = self.filesystem.resolve(Path(__file__).parents[2])
        return root == source_root or (root.name.casefold() == "forgeai" and self.filesystem.is_directory(root / "forgeai"))
