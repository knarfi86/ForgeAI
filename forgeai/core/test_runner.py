from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TestRunResult:
    success: bool
    exit_code: int
    output: str
    runner: str


class ProjectTestRunner:
    """Detect and execute a suitable test runner for a local project."""

    def __init__(self, project_path: str | Path) -> None:
        self.project_path = Path(project_path)

    def run(self) -> TestRunResult:
        runner_name, command = self._detect()

        completed = subprocess.run(
            command,
            cwd=str(self.project_path),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        output = (
            completed.stdout
            + ("\n\n" + completed.stderr if completed.stderr else "")
        ).strip()

        return TestRunResult(
            success=completed.returncode == 0,
            exit_code=completed.returncode,
            output=output,
            runner=runner_name,
        )

    def _detect(self) -> tuple[str, list[str]]:
        script = self.project_path / "scripts" / "run_tests.ps1"

        if script.is_file():
            return (
                "powershell",
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(script),
                ],
            )

        python = self._find_python()

        if python is not None and self._has_python_tests():
            if self._python_has_pytest(python):
                return "pytest", [
                    str(python),
                    "-m",
                    "pytest",
                    "-q",
                ]

            return "unittest", [
                str(python),
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests",
            ]

        raise FileNotFoundError(
            f"Kein unterstuetzter Test Runner im Projekt gefunden: "
            f"{self.project_path}"
        )

    def _find_python(self) -> Path | None:
        candidates = [
            self.project_path / ".venv" / "Scripts" / "python.exe",
            self.project_path / "venv" / "Scripts" / "python.exe",
        ]

        for candidate in candidates:
            if candidate.is_file():
                return candidate

        system_python = shutil.which("python")
        return Path(system_python) if system_python else None

    def _has_python_tests(self) -> bool:
        tests_dir = self.project_path / "tests"

        if not tests_dir.is_dir():
            return False

        return any(
            path.is_file() and path.suffix == ".py"
            for path in tests_dir.rglob("*.py")
        )

    @staticmethod
    def _python_has_pytest(python: Path) -> bool:
        completed = subprocess.run(
            [
                str(python),
                "-m",
                "pytest",
                "--version",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        return completed.returncode == 0
