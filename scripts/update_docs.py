from pathlib import Path
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(ROOT / "scripts"))

from doc_tools import replace_marked_block


def run(command: list[str]) -> str:
    result = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return result.stdout.rstrip(chr(13)+chr(10))


def get_project_python() -> str:
    if os.name == "nt":
        candidate = ROOT / ".venv" / "Scripts" / "python.exe"
    else:
        candidate = ROOT / ".venv" / "bin" / "python"

    if candidate.is_file():
        return str(candidate)

    return sys.executable



def get_agent_status() -> list[str]:
    """Erzeugt einen deterministischen Agentenstatus aus dem Quellcode."""
    import ast

    def defines(path: Path, *, classes=(), functions=()) -> bool:
        if not path.is_file():
            return False

        try:
            source = path.read_text(encoding="utf-8")
            source = source.lstrip("\ufeff")
            tree = ast.parse(source)
        except (OSError, SyntaxError, UnicodeDecodeError):
            return False

        class_names = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef)
        }

        function_names = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }

        return (
            all(name in class_names for name in classes)
            and all(name in function_names for name in functions)
        )

    def contains(path: Path, *needles: str) -> bool:
        if not path.is_file():
            return False

        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return False

        return all(needle in source for needle in needles)

    agent_dir = ROOT / "forgeai" / "ai"
    core_dir = ROOT / "forgeai" / "core"

    components = [
        ("AgentRun", agent_dir / "agent_state.py", ("AgentRun",)),
        ("AgentPlanner", agent_dir / "agent_planner.py", ("AgentPlanner",)),
        ("AgentReviewer", agent_dir / "agent_reviewer.py", ("AgentReviewer",)),
        ("AgentOrchestrator", agent_dir / "agent_orchestrator.py", ("AgentOrchestrator",)),
        ("AgentVerificationWorker", agent_dir / "agent_ui_worker.py", ("AgentVerificationWorker",)),
        ("AgentAnalyzer", agent_dir / "agent_analyzer.py", ("AgentAnalyzer",)),
        ("AgentRepairer", agent_dir / "agent_repairer.py", ("AgentRepairer",)),
        ("AgentRecoveryWorker", agent_dir / "agent_ui_worker.py", ("AgentRecoveryWorker",)),
        ("AgentReality", core_dir / "agent_reality.py", ("AgentReality",)),
    ]

    result = []

    for name, path, classes in components:
        present = defines(path, classes=classes)
        status = "implementiert" if present else "nicht nachgewiesen"
        result.append(f"- `{name}`: **{status}**")

    orchestrator = agent_dir / "agent_orchestrator.py"
    worker = agent_dir / "agent_ui_worker.py"

    plan_review_approval = (
        defines(
            orchestrator,
            functions=(
                "plan",
                "begin_review",
                "handle_review_result",
                "request_approval",
            ),
        )
        and contains(
            worker,
            "orchestrator.plan(",
            "orchestrator.begin_review(",
            "orchestrator.handle_review_result(",
            "orchestrator.request_approval(",
        )
    )

    execution_testing = (
        defines(
            orchestrator,
            functions=("approve", "begin_execution", "begin_testing"),
        )
        and defines(
            worker,
            classes=("AgentVerificationWorker",),
        )
    )

    recovery_chain = contains(
        worker,
        "self.orchestrator.begin_analysis()",
        "self.orchestrator.analyze(",
        "self.orchestrator.begin_repair()",
        "self.orchestrator.repair(",
        "self.orchestrator.begin_review()",
        "self.orchestrator.handle_repair_review_result(",
    )

    reality_integration = contains(
        orchestrator,
        "reality: AgentReality | None = None",
        "self._record_reality_state(",
    )

    result.extend(
        [
            (
                "- `Plan -> Review -> Approval`: **integriert**"
                if plan_review_approval
                else "- `Plan -> Review -> Approval`: **nicht nachgewiesen**"
            ),
            (
                "- `Approval -> Execute -> Test`: **teilintegriert**"
                if execution_testing
                else "- `Approval -> Execute -> Test`: **nicht nachgewiesen**"
            ),
            (
                "- `Test -> Analyze -> Repair -> Review`: **integriert im Recovery-Pfad**"
                if recovery_chain
                else "- `Test -> Analyze -> Repair -> Review`: **nicht nachgewiesen**"
            ),
            "- `vollstaendiger End-to-End-Agentenworkflow`: **teilintegriert**",
            (
                "- `AgentReality-Anbindung`: **teilintegriert**"
                if reality_integration
                else "- `AgentReality-Anbindung`: **nicht integriert**"
            ),
        ]
    )

    return result

def count_tests() -> int:
    python_executable = get_project_python()

    result = subprocess.run(
        [python_executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )

    for line in result.stdout.splitlines():
        if " tests collected" in line:
            value = line.split(" ", 1)[0]
            if value.isdigit():
                return int(value)

    return 0


def get_changed_files() -> list[str]:
    output = run(
        [
            "git",
            "status",
            "--short",
            "--untracked-files=all",
        ]
    )

    ignored = {
        'ARCHITECTURE.md',
        'docs/CURRENT_STATE.md',
    }

    files = []

    for line in output.splitlines():
        if not line:
            continue

        if len(line) >= 4:
            path = line[3:].rstrip()
            if path not in ignored:
                files.append(path)

    return files


def get_recent_commits(limit: int = 5) -> list[str]:
    output = run(
        [
            "git",
            "log",
            f"-{limit}",
            "--oneline",
            "--decorate",
        ]
    )

    return output.splitlines() if output else []


def get_current_plan() -> list[str]:
    roadmap = ROOT / "ROADMAP.md"

    if not roadmap.exists():
        return ["- ROADMAP.md nicht gefunden."]

    content = roadmap.read_text(encoding="utf-8")
    lines = content.splitlines()

    def collect_checkboxes(start_heading: str) -> list[str]:
        items = []
        capture = False
        current = None

        for line in lines:
            stripped = line.strip()

            if stripped == start_heading:
                capture = True
                current = None
                continue

            if capture and stripped.startswith("## "):
                break

            if capture and stripped.startswith("### "):
                if stripped != start_heading:
                    break

            if not capture:
                continue

            if stripped.startswith("- [ ]"):
                if current is not None:
                    items.append(current)

                current = stripped
                continue

            # Nur eingerueckte Fortsetzungszeilen gehoeren zum vorherigen
            # Markdown-Listenpunkt.
            if current is not None and line.startswith((" ", "\t")) and stripped:
                current += " " + stripped
                continue

            if current is not None and stripped:
                items.append(current)
                current = None

        if current is not None:
            items.append(current)

        return items

    # Aktuelle Roadmap-Struktur
    plan = collect_checkboxes("### Noch offene Integrationsarbeiten")

    if plan:
        return plan

    # Klassische Roadmap-Struktur
    plan = []
    capture = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("## N\u00e4chste Ausbaustufen"):
            capture = True
            continue

        if capture and stripped.startswith("## "):
            break

        if capture and stripped.startswith("- "):
            plan.append(stripped)

    if plan:
        return plan

    return ["- Aktueller Plan ist in ROADMAP.md dokumentiert."]


def build_changed_files_section(files: list[str]) -> str:
    if not files:
        return "- Keine uncommitteten Änderungen."

    return "\n".join(f"- `{path}`" for path in files)


def build_history_section(commits: list[str]) -> str:
    if not commits:
        return "- Keine Git-Historie verfügbar."

    return "\n".join(f"- `{commit}`" for commit in commits)


def build_plan_section(plan: list[str]) -> str:
    return "\n".join(plan)


tests = count_tests()
changed_files = get_changed_files()
recent_commits = get_recent_commits()
current_plan = get_current_plan()
agent_status = get_agent_status()

current_state_body = """### Automatisch synchronisierter Arbeitsstand

#### Aktuell geänderte Dateien

""" + build_changed_files_section(changed_files) + """

#### Teststand

- Pytest-Testfaelle: **%d**

#### Aktueller Plan

""" % tests + build_plan_section(current_plan) + """

#### Agentenstatus

""" + "\n".join(agent_status) + """

#### Letzte relevante Commits

""" + build_history_section(recent_commits) + """

Dieser Abschnitt wird automatisch aus dem lokalen Git- und Teststand
sowie aus der aktuellen ROADMAP.md erzeugt.
Manuell gepflegte Dokumentation außerhalb dieses Blocks bleibt erhalten.
"""

architecture_body = """### Automatische Änderungsübersicht

#### Aktuell betroffene Dateien

""" + build_changed_files_section(changed_files) + """

#### Letzte relevante Commits

""" + build_history_section(recent_commits) + """

Diese Übersicht dokumentiert nur den aktuell sichtbaren Entwicklungsstand.
Architekturentscheidungen und Begründungen bleiben in den manuell
gepflegten Abschnitten von ARCHITECTURE.md erhalten.
"""

replace_marked_block(
    ROOT / "docs" / "CURRENT_STATE.md",
    "<!-- FORGE:AUTO:CURRENT_STATE:START -->",
    "<!-- FORGE:AUTO:CURRENT_STATE:END -->",
    current_state_body,
)

replace_marked_block(
    ROOT / "ARCHITECTURE.md",
    "<!-- FORGE:AUTO:ARCHITECTURE:START -->",
    "<!-- FORGE:AUTO:ARCHITECTURE:END -->",
    architecture_body,
)

print("ForgeAI-Dokumentation synchronisiert.")
print(f"Geänderte Dateien: {len(changed_files)}")
print(f"Pytest-Testfaelle: {tests}")
print(f"Commits erfasst: {len(recent_commits)}")
print(f"Planpunkte erfasst: {len(current_plan)}")
