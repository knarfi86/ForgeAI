from forgeai.core.project_evidence import ProjectEvidence


class FakeAnalyzer:
    def analyze(self, project_path):
        return {
            "project_path": str(project_path),
            "project_name": "demo",
            "files": ["main.py"],
            "classes": {"main.py": ["Game"]},
            "imports": {"main.py": ["pygame"]},
        }

    def evidence_summary(self, project_path):
        return {
            "project_path": str(project_path),
            "functions": {"main.py": ["run"]},
            "event_handlers": {
                "main.py": [
                    "pygame.MOUSEBUTTONDOWN",
                    "pygame.MOUSEBUTTONDOWN",
                ]
            },
            "event_retrievals": {
                "main.py": ["pygame.event.get"],
            },
        }


def test_project_evidence_contains_deterministic_facts():
    evidence = ProjectEvidence.from_analyzer(FakeAnalyzer(), "C:/demo")

    assert evidence.project_path == "C:/demo"

    assert evidence.matching("file", "main.py")
    assert evidence.matching("class", "Game")
    assert evidence.matching("function", "run")
    assert evidence.matching("import", "pygame")

    assert evidence.count(
        "event_handler",
        "pygame.MOUSEBUTTONDOWN",
    ) == 2

    assert evidence.count(
        "event_retrieval",
        "pygame.event.get",
    ) == 1

    assert all(item.confidence.value == "high" for item in evidence.evidence)

def test_project_evidence_contains_module_import_and_dependency_facts():
    class Analyzer:
        def analyze(self, project_path):
            return {
                "project_path": str(project_path),
                "project_name": "demo",
                "files": ["main.py", "game.py"],
                "classes": {},
                "imports": {
                    "main.py": ["pygame", "game"],
                    "game.py": [],
                },
                "modules": ["main", "game"],
                "dependency_graph": {
                    "main": ["pygame", "game"],
                    "game": [],
                },
            }

        def evidence_summary(self, project_path):
            return {
                "project_path": str(project_path),
                "functions": {},
                "event_handlers": {},
                "event_retrievals": {},
                "syntax_errors": {},
            }

    from forgeai.core.project_evidence import ProjectEvidence

    evidence = ProjectEvidence.from_analyzer(Analyzer(), "C:/demo")

    assert evidence.matching("module", "main")
    assert evidence.matching("module", "game")
    assert evidence.matching("import", "pygame")
    assert evidence.matching("import", "game")
    assert evidence.matching("dependency", "main -> pygame")
    assert evidence.matching("dependency", "main -> game")


def test_project_evidence_contains_syntax_error_facts():
    class Analyzer:
        def analyze(self, project_path):
            return {
                "project_path": str(project_path),
                "project_name": "demo",
                "files": ["main.py"],
                "classes": {"main.py": []},
                "imports": {"main.py": []},
                "modules": ["main"],
                "dependency_graph": {},
            }

        def evidence_summary(self, project_path):
            return {
                "project_path": str(project_path),
                "functions": {"main.py": []},
                "event_handlers": {"main.py": []},
                "event_retrievals": {"main.py": []},
                "syntax_errors": {
                    "main.py": "invalid syntax",
                },
            }

    from forgeai.core.project_evidence import ProjectEvidence

    evidence = ProjectEvidence.from_analyzer(Analyzer(), "C:/demo")

    matches = evidence.matching(
        "syntax_error",
        "invalid syntax",
        scope="main.py",
    )

    assert len(matches) == 1
