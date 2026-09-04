from pathlib import Path


def write_utf8(path: str | Path, content: str) -> None:
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(normalized.encode("utf-8"))


def replace_marked_block(
    path: str | Path,
    start_marker: str,
    end_marker: str,
    replacement: str,
) -> None:
    target = Path(path)
    content = target.read_text(encoding="utf-8")

    start = content.find(start_marker)
    end = content.find(end_marker)

    if start < 0:
        raise RuntimeError(
            f"Start marker not found in {target}: {start_marker!r}"
        )

    if end < 0 or end < start:
        raise RuntimeError(
            f"End marker not found in {target}: {end_marker!r}"
        )

    end += len(end_marker)

    updated = (
        content[:start]
        + start_marker
        + "\n"
        + replacement.rstrip("\r\n")
        + "\n"
        + end_marker
        + content[end:]
    )

    write_utf8(target, updated)
