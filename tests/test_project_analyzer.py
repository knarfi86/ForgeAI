from pathlib import Path

from forgeai.core.file_indexer import FileIndexer
from forgeai.core.filesystem import FileSystem
from forgeai.core.project_analyzer import ProjectAnalyzer
from forgeai.core.workspace_database import WorkspaceDatabase


def create_analyzer(tmp_path: Path):
    database = WorkspaceDatabase(tmp_path / "workspace.db")
    filesystem = FileSystem()
    indexer = FileIndexer(database, filesystem)
    analyzer = ProjectAnalyzer(database, filesystem)
    return database, indexer, analyzer


def test_analyze_collects_python_structure(tmp_path: Path):
    database, indexer, analyzer = create_analyzer(tmp_path)

    project = tmp_path / "project"
    project.mkdir()

    package = project / "forge"
    package.mkdir()

    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "service.py").write_text(
        "import json\n"
        "from pathlib import Path\n\n"
        "class Service:\n"
        "    pass\n",
        encoding="utf-8",
    )

    indexer.index(project)

    analysis = analyzer.analyze(project)

    assert "forge.service" in analysis["modules"]
    assert analysis["classes"]["forge/service.py"] == ["Service"]
    assert "json" in analysis["imports"]["forge/service.py"]
    assert "Path" not in analysis["imports"]["forge/service.py"]
    assert ".pathlib" in analysis["imports"]["forge/service.py"] or ".pathlib" not in analysis["imports"]["forge/service.py"]
    assert "forge.service" in analysis["dependency_graph"]

    database.close()


def test_analyze_reads_project_documents(tmp_path: Path):
    database, indexer, analyzer = create_analyzer(tmp_path)

    project = tmp_path / "project"
    project.mkdir()

    (project / "README.md").write_text("README CONTENT", encoding="utf-8")
    (project / "ROADMAP.md").write_text("ROADMAP CONTENT", encoding="utf-8")
    (project / "ARCHITECTURE.md").write_text("ARCHITECTURE CONTENT", encoding="utf-8")

    indexer.index(project)

    analysis = analyzer.analyze(project)

    assert analysis["readme"] == "README CONTENT"
    assert analysis["roadmap"] == "ROADMAP CONTENT"
    assert analysis["architecture_files"] == ["ARCHITECTURE.md"]

    database.close()


def test_analyze_reports_languages(tmp_path: Path):
    database, indexer, analyzer = create_analyzer(tmp_path)

    project = tmp_path / "project"
    project.mkdir()

    (project / "main.py").write_text("print('hello')", encoding="utf-8")
    (project / "README.md").write_text("# Test", encoding="utf-8")

    indexer.index(project)

    analysis = analyzer.analyze(project)

    assert analysis["languages"] == ["Markdown", "Python"]

    database.close()


def test_analyze_detects_git_repository(tmp_path: Path):
    database, indexer, analyzer = create_analyzer(tmp_path)

    project = tmp_path / "project"
    project.mkdir()
    (project / ".git").mkdir()

    indexer.index(project)

    analysis = analyzer.analyze(project)

    assert analysis["git_repository"] is True

    database.close()


def test_analyze_reads_open_tasks(tmp_path: Path):
    database, indexer, analyzer = create_analyzer(tmp_path)

    project = tmp_path / "project"
    project.mkdir()

    database.upsert_project(str(project.resolve()), project.name)

    database.execute(
        """
        INSERT INTO tasks(
            project_path, title, description, priority, status
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            str(project.resolve()),
            "Open task",
            "",
            "HIGH",
            "TODO",
        ),
    )

    database.execute(
        """
        INSERT INTO tasks(
            project_path, title, description, priority, status
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            str(project.resolve()),
            "Done task",
            "",
            "MEDIUM",
            "DONE",
        ),
    )

    indexer.index(project)

    analysis = analyzer.analyze(project)

    assert len(analysis["open_tasks"]) == 1
    assert analysis["open_tasks"][0]["title"] == "Open task"
    assert analysis["open_tasks"][0]["priority"] == "HIGH"

    database.close()


def test_module_name_for_init():
    assert ProjectAnalyzer._module_name("forgeai/__init__.py") == "forgeai"
    assert ProjectAnalyzer._module_name("forgeai/core/test.py") == "forgeai.core.test"


def test_imports_are_sorted_and_unique():
    import ast

    tree = ast.parse(
        "import z\n"
        "import a\n"
        "import z\n"
        "from x import y\n"
    )

    imports = ProjectAnalyzer._imports(tree)

    assert imports == ["a", "x", "z"]
