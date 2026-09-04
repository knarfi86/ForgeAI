from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(ROOT / "scripts"))

from doc_tools import write_utf8


def run(command: list[str]) -> str:
    result = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return result.stdout.strip()


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


def exists(relative_path: str) -> bool:
    return (ROOT / relative_path).exists()


def has_text(relative_path: str, needle: str) -> bool:
    path = ROOT / relative_path

    if not path.exists():
        return False

    return needle in path.read_text(encoding="utf-8")


def replace_block(
    path: Path,
    start_marker: str,
    end_marker: str,
    body: str,
    anchor: str,
) -> None:
    content = path.read_text(encoding="utf-8")

    block = (
        start_marker
        + "\n"
        + body.rstrip()
        + "\n"
        + end_marker
    )

    start = content.find(start_marker)
    end = content.find(end_marker)

    if start >= 0 and end >= start:
        end += len(end_marker)
        updated = content[:start] + block + content[end:]
    else:
        anchor_pos = content.find(anchor)

        if anchor_pos < 0:
            raise RuntimeError(
                f"Anchor nicht gefunden in {path}: {anchor!r}"
            )

        insert_at = anchor_pos + len(anchor)

        updated = (
            content[:insert_at]
            + "\n\n"
            + block
            + content[insert_at:]
        )

    if updated != content:
        write_utf8(path, updated)


tests = count_tests()

reality_model = exists("forgeai/core/agent_reality.py")
orchestrator = exists("forgeai/ai/agent_orchestrator.py")
reality_events = (
    reality_model
    and has_text(
        "forgeai/core/agent_reality.py",
        "def record_run_state(",
    )
)
orchestrator_reality = (
    orchestrator
    and has_text(
        "forgeai/ai/agent_orchestrator.py",
        "self.reality",
    )
)
encoding_gate = exists("scripts/check_encoding.py")
doc_tools = exists("scripts/doc_tools.py")
doc_sync = exists("scripts/update_docs.py")
test_runner = exists("scripts/run_tests.ps1")

current_state_items = [
    "- Pytest-Testfaelle: **%d**" % tests,
]

if reality_model:
    current_state_items.append(
        "- Agent Reality Datenmodell: **implementiert**"
    )

if reality_events:
    current_state_items.append(
        "- Reality-State-Events: **implementiert**"
    )

if orchestrator_reality:
    current_state_items.append(
        "- AgentOrchestrator-Reality-Anbindung: **vorhanden**"
    )

if encoding_gate:
    current_state_items.append(
        "- Encoding-Gate: `scripts/check_encoding.py` **vorhanden**"
    )

if doc_tools and doc_sync:
    current_state_items.append(
        "- Automatische Doku-Pflege: **vorhanden**"
    )

if test_runner:
    current_state_items.append(
        "- Automatisierter Test-Runner: **vorhanden**"
    )

current_state_body = """### Automatisch gepflegter Projektstand

Die folgenden Fakten werden direkt aus dem Repository ermittelt:

""" + "\n".join(current_state_items) + """

Dieser Abschnitt beschreibt den technisch belegbaren Stand.
Architekturentscheidungen, Begr?ndungen und strategische Planung
bleiben in den manuell gepflegten Abschnitten erhalten.
"""

reality_items = []

if reality_model:
    reality_items.append(
        "- `AgentReality`-Datenmodell: implementiert"
    )

if reality_events:
    reality_items.append(
        "- `AgentReality.record_run_state()`: implementiert"
    )

if orchestrator_reality:
    reality_items.append(
        "- `AgentOrchestrator` kann Reality-State-Events aufzeichnen"
    )

reality_items.append(
    "- Automatisch ermittelte Testbasis: **%d Testfaelle**" % tests
)

reality_body = """### Automatisch ermittelter Implementierungsstand

""" + "\n".join(reality_items) + """

Die Eintr\u00e4ge dieses Abschnitts werden aus dem vorhandenen Code- und
Testbestand abgeleitet. Manuelle Architektur- und Modellentscheidungen
werden nicht \u00fcberschrieben.
"""

architecture_items = [
    "- `AgentRun` bleibt die autoritative Laufzeitinstanz.",
]

if reality_model:
    architecture_items.append(
        "- Der Reality Layer bildet den Laufzeitstatus strukturiert ab."
    )

if reality_events:
    architecture_items.append(
        "- Runtime-Zustands\u00e4nderungen k\u00f6nnen als `AgentEvent` beobachtet werden."
    )

if orchestrator_reality:
    architecture_items.append(
        "- Der Orchestrator kann Reality-Beobachtungen optional aufzeichnen."
    )

architecture_body = """### Automatischer Reality-Status

""" + "\n".join(architecture_items) + """

Diese automatische Zusammenfassung enth\u00e4lt nur aus dem Repository
ableitbare technische Fakten.
"""

replace_block(
    ROOT / "docs" / "CURRENT_STATE.md",
    "<!-- FORGE:AUTO:CURRENT_STATE:START -->",
    "<!-- FORGE:AUTO:CURRENT_STATE:END -->",
    current_state_body,
    "### Reality-Layer-Event-Projektion",
)

replace_block(
    ROOT / "docs" / "AGENT_REALITY_MODEL.md",
    "<!-- FORGE:AUTO:REALITY_MODEL:START -->",
    "<!-- FORGE:AUTO:REALITY_MODEL:END -->",
    reality_body,
    "## AgentRun-Projection",
)

replace_block(
    ROOT / "ARCHITECTURE.md",
    "<!-- FORGE:AUTO:ARCHITECTURE:START -->",
    "<!-- FORGE:AUTO:ARCHITECTURE:END -->",
    architecture_body,
    "## AgentRun und RunReality",
)

print("ForgeAI-Dokumentation synchronisiert.")
print(f"Pytest-Testfaelle: {tests}")
print(f"Reality Model: {'ja' if reality_model else 'nein'}")
print(f"Reality Events: {'ja' if reality_events else 'nein'}")
print(f"Orchestrator-Reality: {'ja' if orchestrator_reality else 'nein'}")
