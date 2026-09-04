from pathlib import Path

from scripts.doc_tools import replace_marked_block, write_utf8


def test_write_utf8_uses_utf8_without_bom_and_lf(tmp_path: Path):
    target = tmp_path / "docs.md"

    write_utf8(target, "Zeile 1\nZeile 2\n")

    raw = target.read_bytes()

    assert raw.startswith(b"\xef\xbb\xbf") is False
    assert b"\r\n" not in raw
    assert raw.decode("utf-8") == "Zeile 1\nZeile 2\n"


def test_replace_marked_block_replaces_only_marked_section(tmp_path: Path):
    target = tmp_path / "docs.md"

    write_utf8(
        target,
        """Vorher
<!-- FORGE:START -->
Alter Stand: ?berholt
<!-- FORGE:END -->
Nachher
""",
    )

    replace_marked_block(
        target,
        "<!-- FORGE:START -->",
        "<!-- FORGE:END -->",
        "Neuer Stand: ge?ndert",
    )

    content = target.read_text(encoding="utf-8")

    assert "Alter Stand: ?berholt" not in content
    assert "Neuer Stand: ge?ndert" in content
    assert content.startswith("Vorher\n")
    assert content.endswith("Nachher\n")


def test_replace_marked_block_is_idempotent(tmp_path: Path):
    target = tmp_path / "docs.md"

    write_utf8(
        target,
        """Vorher
<!-- FORGE:START -->
Alter Stand
<!-- FORGE:END -->
Nachher
""",
    )

    replace_marked_block(
        target,
        "<!-- FORGE:START -->",
        "<!-- FORGE:END -->",
        "Neuer Stand",
    )

    first = target.read_bytes()

    replace_marked_block(
        target,
        "<!-- FORGE:START -->",
        "<!-- FORGE:END -->",
        "Neuer Stand",
    )

    second = target.read_bytes()

    assert first == second


def test_replace_marked_block_requires_markers(tmp_path: Path):
    target = tmp_path / "docs.md"
    write_utf8(target, "Kein Marker\n")

    try:
        replace_marked_block(
            target,
            "<!-- FORGE:START -->",
            "<!-- FORGE:END -->",
            "Neuer Stand",
        )
    except RuntimeError as exc:
        assert "Start marker not found" in str(exc)
    else:
        raise AssertionError("Fehlender Anchor wurde nicht erkannt.")
