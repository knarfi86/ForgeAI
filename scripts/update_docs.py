from pathlib import Path
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


def count_tests() -> int:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
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
    plan = []

    capture = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("## Nächste Ausbaustufen"):
            capture = True
            continue

        if capture and stripped.startswith("## "):
            break

        if capture and stripped.startswith("- "):
            plan.append(stripped)

    if not plan:
        return ["- Aktueller Plan ist in ROADMAP.md dokumentiert."]

    return plan


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

current_state_body = """### Automatisch synchronisierter Arbeitsstand

#### Aktuell geänderte Dateien

""" + build_changed_files_section(changed_files) + """

#### Teststand

- Pytest-Testfaelle: **%d**

#### Aktueller Plan

""" % tests + build_plan_section(current_plan) + """

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
