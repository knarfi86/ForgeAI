import subprocess
from pathlib import Path


class GitManager:
    def status(self, project_path: str | Path) -> str:
        return self._run(project_path, ["status", "--short"])

    def commit(self, project_path: str | Path, message: str) -> str:
        self._run(project_path, ["add", "-A"])
        return self._run(project_path, ["commit", "-m", message])

    def _run(self, project_path: str | Path, args: list[str]) -> str:
        result = subprocess.run(["git", *args], cwd=project_path, capture_output=True, text=True)
        return result.stdout + result.stderr
