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

    DEFAULT_TIMEOUT_SECONDS = 300

    def __init__(
        self,
        project_path: str | Path,
        timeout_seconds: int | float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.project_path = Path(project_path)
        self.timeout_seconds = float(timeout_seconds)

        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds muss größer als 0 sein.")

    def run(self) -> TestRunResult:
        runner_name, command = self._detect()

        try:
            completed = subprocess.run(
                command,
                cwd=str(self.project_path),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired as error:
            partial_output = ""

            if error.stdout:
                partial_output += str(error.stdout)

            if error.stderr:
                if partial_output:
                    partial_output += "\n\n"
                partial_output += str(error.stderr)

            timeout_message = (
                f"Testlauf mit Runner '{runner_name}' hat das Zeitlimit "
                f"von {self.timeout_seconds:g} Sekunden überschritten."
            )

            output = (
                f"{timeout_message}\n\n"
                f"{partial_output.strip()}"
            ).strip()

            return TestRunResult(
                success=False,
                exit_code=-1,
                output=output,
                runner=runner_name,
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
            timeout=10,
        )

        return completed.returncode == 0
