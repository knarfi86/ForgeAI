from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

TEXT_EXTENSIONS = {
    ".py", ".md", ".txt", ".json", ".yaml", ".yml",
    ".ps1", ".psm1", ".toml", ".ini", ".cfg"
}

MOJIBAKE_MARKERS = (
    "\ufffd",
    "\u00c3",
    "\u00c2",
    "\u00e2",
    "\u00f0",
)

def changed_files() -> list[Path]:
    result = subprocess.run(
        ["git", "status", "--short"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )

    files: list[Path] = []

    for line in result.stdout.splitlines():
        if len(line) < 4:
            continue

        path_text = line[3:].strip()

        if " -> " in path_text:
            path_text = path_text.split(" -> ", 1)[1]

        path = ROOT / path_text

        if path.is_file() and path.suffix.lower() in TEXT_EXTENSIONS:
            files.append(path)

    return files


errors: list[str] = []
files = changed_files()

print("=== ForgeAI Encoding Check ===")
print(f"Gepruefte geaenderte Textdateien: {len(files)}")

for path in files:
    raw = path.read_bytes()
    rel = path.relative_to(ROOT)

    if raw.startswith(b"\xef\xbb\xbf"):
        errors.append(f"{rel}: UTF-8 BOM gefunden")

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        errors.append(f"{rel}: kein gueltiges UTF-8 ({exc})")
        continue

    if "\ufffd" in text:
        errors.append(f"{rel}: Unicode-Ersatzzeichen U+FFFD gefunden")

    for marker in MOJIBAKE_MARKERS:
        if marker in text:
            errors.append(
                f"{rel}: moegliches Mojibake-Signal {marker!r}"
            )

if errors:
    print("FAILED")
    for error in errors:
        print(f"ERROR: {error}")
    sys.exit(1)

print("OK: UTF-8 gueltig, kein BOM und keine offensichtlichen "
      "Encoding-/Mojibake-Signale.")
