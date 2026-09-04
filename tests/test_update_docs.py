from pathlib import Path
import os
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


AUTO_BLOCKS = [
    (
        ROOT / "docs" / "CURRENT_STATE.md",
        "<!-- FORGE:AUTO:CURRENT_STATE:START -->",
        "<!-- FORGE:AUTO:CURRENT_STATE:END -->",
    ),
    (
        ROOT / "ARCHITECTURE.md",
        "<!-- FORGE:AUTO:ARCHITECTURE:START -->",
        "<!-- FORGE:AUTO:ARCHITECTURE:END -->",
    ),
]


def run_update_docs() -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = "utf-8"

    return subprocess.run(
        [sys.executable, "scripts/update_docs.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=environment,
        check=False,
    )


def get_auto_block(path: Path, start_marker: str, end_marker: str) -> str:
    content = path.read_text(encoding="utf-8")

    start = content.index(start_marker) + len(start_marker)
    end = content.index(end_marker)

    return content[start:end]


def test_update_docs_updates_auto_blocks_and_is_idempotent():
    reality_path = ROOT / "docs" / "AGENT_REALITY_MODEL.md"
    reality_before = reality_path.read_bytes()

    first = run_update_docs()

    assert first.returncode == 0, first.stderr
    assert "ForgeAI-Dokumentation synchronisiert." in first.stdout

    for path, start_marker, end_marker in AUTO_BLOCKS:
        content = path.read_text(encoding="utf-8")

        assert start_marker in content
        assert end_marker in content

        start = content.index(start_marker)
        end = content.index(end_marker)

        assert start < end

    assert reality_path.read_bytes() == reality_before

    current_state_block = get_auto_block(
        ROOT / "docs" / "CURRENT_STATE.md",
        "<!-- FORGE:AUTO:CURRENT_STATE:START -->",
        "<!-- FORGE:AUTO:CURRENT_STATE:END -->",
    )

    assert "forgeai/ai/agent_planner.py" in current_state_block
    assert "forgeai/ai/agent_reviewer.py" in current_state_block
    assert "forgeai/ui/main_window.py" not in current_state_block
    assert "- `ARCHITECTURE.md`" not in current_state_block
    assert "- `docs/CURRENT_STATE.md`" not in current_state_block

    snapshots = {
        path: path.read_bytes()
        for path, _, _ in AUTO_BLOCKS
    }

    second = run_update_docs()

    assert second.returncode == 0, second.stderr

    for path, _, _ in AUTO_BLOCKS:
        assert path.read_bytes() == snapshots[path]

    assert reality_path.read_bytes() == reality_before
