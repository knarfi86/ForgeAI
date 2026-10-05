"""Install only the reviewed update, preserving unrelated project files."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent


def normalized(data):
    return data.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")


def digest(data):
    return hashlib.sha256(normalized(data).encode("utf-8")).hexdigest()


def safe_path(root, relative):
    target = (root / relative).resolve()
    if root not in target.parents:
        raise ValueError(f"Pfad ausserhalb des Zielordners: {relative}")
    return target


def prepare(root):
    if not (root / "forgeai" / "ui" / "main_window.py").is_file():
        raise ValueError(f"Kein ForgeAI-Projekt gefunden: {root}")
    manifest = json.loads((PACKAGE / "manifest.json").read_text(encoding="utf-8"))
    changes, conflicts = [], []
    for item in manifest["files"]:
        relative = item["path"]
        target = safe_path(root, relative)
        payload = safe_path((PACKAGE / "payload").resolve(), relative).read_bytes()
        if digest(payload) != item["new_sha256"]:
            raise ValueError(f"Update-Paket beschaedigt: {relative}")
        old = target.read_bytes() if target.is_file() else None
        if item["mode"] == "append":
            if old is None:
                conflicts.append(relative)
                continue
            current, block = normalized(old), normalized(payload).strip()
            if block in current:
                continue
            if "<!-- FORGE:RECOVERY_FOUNDATION:START -->" in current:
                conflicts.append(relative)
                continue
            new = (current.rstrip() + "\n\n" + block + "\n").encode("utf-8")
        else:
            if old is not None and digest(old) == item["new_sha256"]:
                continue
            expected = item.get("old_sha256")
            if (old is None and expected is not None) or (
                old is not None and (expected is None or digest(old) != expected)
            ):
                conflicts.append(relative)
                continue
            new = payload
        changes.append((relative, target, old, new))
    if conflicts:
        raise ValueError("Abweichender Dateistand; nichts wurde geaendert:\n- " + "\n- ".join(conflicts))
    return changes


def replace_bytes(target, data):
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".forge-update-" + uuid.uuid4().hex)
    try:
        temporary.write_bytes(data)
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()


def install(root, changes):
    backup_base = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "ForgeAI" / "UpdateBackups"
    backup = backup_base / (datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8])
    backup.mkdir(parents=True)
    for relative, _, old, _ in changes:
        if old is not None:
            saved = backup / relative
            saved.parent.mkdir(parents=True, exist_ok=True)
            saved.write_bytes(old)
    (backup / "restore-info.json").write_text(json.dumps({
        "project": str(root),
        "new_files": [relative for relative, _, old, _ in changes if old is None],
    }, indent=2), encoding="utf-8")
    applied = []
    try:
        for relative, target, old, new in changes:
            current = target.read_bytes() if target.is_file() else None
            if current != old:
                raise ValueError(f"Datei waehrend der Installation geaendert: {relative}")
            replace_bytes(target, new)
            applied.append((target, old))
    except Exception:
        for target, old in reversed(applied):
            if old is None:
                target.unlink()
            else:
                replace_bytes(target, old)
        raise
    print(f"Update installiert: {len(changes)} Dateien.", flush=True)
    print(f"Sicherung: {backup}", flush=True)
    return backup


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--check", action="store_true", help="Nur Dateistand pruefen")
    parser.add_argument("--skip-tests", action="store_true", help="Tests separat ausfuehren")
    args = parser.parse_args()
    root = args.project.expanduser().resolve()
    try:
        changes = prepare(root)
        if args.check:
            print(f"Kompatibel: {len(changes)} Dateien werden aktualisiert.")
            return 0
        if changes:
            install(root, changes)
        else:
            print("Update ist bereits installiert.", flush=True)
        if not args.skip_tests:
            print("Pruefe Python-Syntax und vollstaendige Testsuite ...", flush=True)
            for command in (
                [sys.executable, "-m", "compileall", "-q", "forgeai"],
                [sys.executable, "-m", "pytest", "-q"],
            ):
                result = subprocess.run(command, cwd=root)
                if result.returncode:
                    print("Update installiert; lokale Pruefung fehlgeschlagen. Ausgabe oben beachten.")
                    return 2
        print("Fertig. ForgeAI kann wieder gestartet werden.")
        return 0
    except (OSError, ValueError) as error:
        print(f"Installation gestoppt: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
