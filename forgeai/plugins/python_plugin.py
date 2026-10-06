from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from forgeai.core.capability_registry import (
    PluginActionSpec,
    PluginCategory,
    PluginFactRequirement,
    PluginManifest,
    ResourceRequirements,
)
from forgeai.core.completion_gate import CompletionEvidenceCategory, CompletionEvidenceMode
from forgeai.core.fact_evidence_provider import (
    FactContext,
    FactObservation,
    FactQuery,
    FactSourceType,
    FactStatus,
    FunctionFactProvider,
)
from forgeai.core.plugin_manager import (
    CapabilityExecutionContext,
    CapabilityPlanStep,
    PluginManager,
)
from forgeai.core.verification_framework import (
    FunctionVerificationProvider,
    VerificationCheck,
    VerificationContext,
    VerificationProfile,
    VerificationResult,
    VerificationStatus,
)


PLUGIN_ID = "python"
FACT_PROVIDER_ID = "python.environment"
VERIFICATION_PROVIDER_ID = "python.verifier"
VERIFICATION_PROFILE_ID = "python-source"

_FACT_KEYS = (
    "python.available",
    "python.executable",
    "python.version",
    "python.pytest.available",
    "python.pytest.version",
    "python.project.markers",
)

_EXCLUDED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    "build",
    "dist",
    ".forge_patch_backups",
}

_PROJECT_MARKERS = (
    "pyproject.toml",
    "requirements.txt",
    "pytest.ini",
    "setup.py",
    "setup.cfg",
    "tox.ini",
)


@dataclass(frozen=True)
class PythonRuntime:
    executable: Path
    origin: str
    version: str


@dataclass(frozen=True)
class PythonExecutionResult:
    action: str
    success: bool
    exit_code: int
    output: str
    executable: str | None
    command: tuple[str, ...] = ()


class PythonPlugin:
    """Script-first Python capability plugin used as Forge's reference plugin.

    The plugin does not plan or write source code. Planning remains a Forge Core
    concern. It supplies deterministic environment facts, verification checks and
    a narrow executor for explicit Python tool actions.
    """

    manifest = PluginManifest(
        plugin_id=PLUGIN_ID,
        name="Python Development",
        version="1.0.0",
        category=PluginCategory.DEVELOPMENT,
        capabilities=(
            "code.python.generate",
            "code.python.modify",
            "code.python.test",
            "code.python.debug",
        ),
        actions=(
            PluginActionSpec(
                action_id="inspect",
                capability_ids=("code.python.debug",),
                description="Lokalen Python-Interpreter und Laufzeitquelle prüfen.",
            ),
            PluginActionSpec(
                action_id="compile",
                capability_ids=("code.python.test",),
                description="Python-Quellen des Projekts syntaktisch kompilieren.",
            ),
            PluginActionSpec(
                action_id="test",
                capability_ids=("code.python.test",),
                description="Python-Testbestand des Projekts ausführen.",
            ),
        ),
        fact_requirements=(
            PluginFactRequirement(
                fact_key="python.available",
                provider_id=FACT_PROVIDER_ID,
                expected_value=True,
                max_age_seconds=30.0,
            ),
        ),
        verification_profiles=(VERIFICATION_PROFILE_ID,),
        model_roles=("coding", "reasoning"),
        task_hints=(
            "python",
            "pytest",
            ".py",
            "pip",
            "venv",
        ),
        project_markers=_PROJECT_MARKERS,
        resources=ResourceRequirements(
            gpu_required=False,
            min_vram_mb=0,
            min_ram_mb=0,
            exclusive_resources=(),
        ),
        description=(
            "Lokale Python-Entwicklung mit scriptbasierter Interpreter-/pytest-"
            "Erkennung, Syntaxprüfung und seriellen Tool-Aktionen."
        ),
    )

    def __init__(self, *, command_timeout_seconds: float = 30.0) -> None:
        if command_timeout_seconds <= 0:
            raise ValueError("command_timeout_seconds muss größer als 0 sein.")
        self.command_timeout_seconds = float(command_timeout_seconds)

    def register(self, manager: PluginManager) -> None:
        manager.register_plugin(
            self.manifest,
            executor=self.execute,
            fact_providers=(
                FunctionFactProvider(
                    provider_id=FACT_PROVIDER_ID,
                    source_type=FactSourceType.SCRIPT,
                    fact_keys=_FACT_KEYS,
                    callback=self.observe_fact,
                ),
            ),
            verification_providers=(
                FunctionVerificationProvider(
                    provider_id=VERIFICATION_PROVIDER_ID,
                    category=CompletionEvidenceCategory.TECHNICAL,
                    callback=self.verify,
                    mode=CompletionEvidenceMode.FACT,
                ),
            ),
            verification_profiles=(
                VerificationProfile(
                    profile_id=VERIFICATION_PROFILE_ID,
                    description=(
                        "Belegt den verwendbaren Python-Interpreter und kompiliert "
                        "die Python-Quellen des aktuellen Projekts."
                    ),
                    checks=(
                        VerificationCheck(
                            check_id="python-interpreter",
                            provider_id=VERIFICATION_PROVIDER_ID,
                            category=CompletionEvidenceCategory.TECHNICAL,
                            required=True,
                            description="Python-Interpreter lässt sich real ausführen.",
                        ),
                        VerificationCheck(
                            check_id="python-compile",
                            provider_id=VERIFICATION_PROVIDER_ID,
                            category=CompletionEvidenceCategory.TECHNICAL,
                            required=True,
                            description="Projektquellen lassen sich mit Python kompilieren.",
                        ),
                    ),
                ),
            ),
        )

    # ------------------------------------------------------------------ facts
    def observe_fact(self, context: FactContext, query: FactQuery) -> FactObservation:
        runtime = self._discover_runtime(context.project_root)

        if query.fact_key == "python.project.markers":
            if context.project_root is None or not context.project_root.is_dir():
                return FactObservation(
                    status=FactStatus.UNKNOWN,
                    summary="Kein aktuelles Projekt für Python-Projektmarker verfügbar.",
                    source_detail=FACT_PROVIDER_ID,
                    tool="filesystem scan",
                )
            markers = self._project_markers(context.project_root)
            return FactObservation(
                status=FactStatus.OBSERVED,
                value=markers,
                summary=(
                    "Python-Projektmarker: " + ", ".join(markers)
                    if markers
                    else "Keine deklarierten Python-Projektmarker im Projektroot gefunden."
                ),
                source_detail=str(context.project_root),
                tool="filesystem scan",
                details={"markers": markers},
            )

        if runtime is None:
            return FactObservation(
                status=FactStatus.ABSENT,
                value=False if query.fact_key == "python.available" else None,
                summary=(
                    "Kein Python-Interpreter in Projekt-venv, PATH oder Forge-Laufzeit gefunden."
                ),
                source_detail=FACT_PROVIDER_ID,
                tool="python discovery",
                authoritative_absence=False,
            )

        command = (str(runtime.executable), "--version")
        if query.fact_key == "python.available":
            return FactObservation(
                status=FactStatus.OBSERVED,
                value=True,
                summary=f"Python {runtime.version} bereit ({runtime.origin}).",
                source_detail=str(runtime.executable),
                tool="python",
                command=self._command_text(command),
                exit_code=0,
                details={"origin": runtime.origin, "version": runtime.version},
            )
        if query.fact_key == "python.executable":
            return FactObservation(
                status=FactStatus.OBSERVED,
                value=str(runtime.executable),
                summary=f"Python-Interpreter: {runtime.executable}",
                source_detail=str(runtime.executable),
                tool="python",
                command=self._command_text(command),
                exit_code=0,
                details={"origin": runtime.origin},
            )
        if query.fact_key == "python.version":
            return FactObservation(
                status=FactStatus.OBSERVED,
                value=runtime.version,
                summary=f"Python-Version: {runtime.version}",
                source_detail=str(runtime.executable),
                tool="python",
                command=self._command_text(command),
                exit_code=0,
                details={"origin": runtime.origin},
            )
        if query.fact_key in {"python.pytest.available", "python.pytest.version"}:
            pytest = self._probe_pytest(runtime)
            if query.fact_key == "python.pytest.available":
                return FactObservation(
                    status=FactStatus.OBSERVED,
                    value=pytest[0],
                    summary=(
                        f"pytest {pytest[1]} ist verfügbar."
                        if pytest[0]
                        else "pytest ist im ausgewählten Python-Interpreter nicht verfügbar."
                    ),
                    source_detail=str(runtime.executable),
                    tool="pytest",
                    command=self._command_text(
                        (str(runtime.executable), "-m", "pytest", "--version")
                    ),
                    exit_code=pytest[2],
                    details={"version": pytest[1]},
                )

            if pytest[0]:
                return FactObservation(
                    status=FactStatus.OBSERVED,
                    value=pytest[1],
                    summary=f"pytest-Version: {pytest[1]}",
                    source_detail=str(runtime.executable),
                    tool="pytest",
                    command=self._command_text(
                        (str(runtime.executable), "-m", "pytest", "--version")
                    ),
                    exit_code=pytest[2],
                )
            return FactObservation(
                status=FactStatus.ABSENT,
                value=None,
                summary="pytest-Modul im ausgewählten Interpreter nicht vorhanden.",
                source_detail=str(runtime.executable),
                tool="pytest",
                command=self._command_text(
                    (str(runtime.executable), "-m", "pytest", "--version")
                ),
                exit_code=pytest[2],
                authoritative_absence=pytest[3],
            )

        raise KeyError(f"Nicht unterstützter Python-Fact: {query.fact_key}")

    # ----------------------------------------------------------- verification
    def verify(
        self,
        context: VerificationContext,
        check: VerificationCheck,
    ) -> VerificationResult:
        project_root = context.project_root
        runtime = self._discover_runtime(project_root)

        if check.check_id == "python-interpreter":
            if runtime is None:
                return VerificationResult(
                    check_id=check.check_id,
                    provider_id=VERIFICATION_PROVIDER_ID,
                    category=CompletionEvidenceCategory.TECHNICAL,
                    status=VerificationStatus.UNKNOWN,
                    summary="Kein ausführbarer Python-Interpreter konnte belegt werden.",
                    source=VERIFICATION_PROVIDER_ID,
                    mode=CompletionEvidenceMode.FACT,
                )
            return VerificationResult(
                check_id=check.check_id,
                provider_id=VERIFICATION_PROVIDER_ID,
                category=CompletionEvidenceCategory.TECHNICAL,
                status=VerificationStatus.PASS,
                summary=f"Python {runtime.version} ist ausführbar.",
                source=VERIFICATION_PROVIDER_ID,
                mode=CompletionEvidenceMode.FACT,
                observed_value=str(runtime.executable),
                details={"origin": runtime.origin, "version": runtime.version},
            )

        if check.check_id == "python-compile":
            if runtime is None:
                return VerificationResult(
                    check_id=check.check_id,
                    provider_id=VERIFICATION_PROVIDER_ID,
                    category=CompletionEvidenceCategory.TECHNICAL,
                    status=VerificationStatus.UNKNOWN,
                    summary="Syntaxprüfung nicht möglich: Python-Interpreter fehlt.",
                    source=VERIFICATION_PROVIDER_ID,
                    mode=CompletionEvidenceMode.FACT,
                )
            if project_root is None or not project_root.is_dir():
                return VerificationResult(
                    check_id=check.check_id,
                    provider_id=VERIFICATION_PROVIDER_ID,
                    category=CompletionEvidenceCategory.TECHNICAL,
                    status=VerificationStatus.UNKNOWN,
                    summary="Syntaxprüfung nicht möglich: kein aktuelles Projekt.",
                    source=VERIFICATION_PROVIDER_ID,
                    mode=CompletionEvidenceMode.FACT,
                )

            result = self._compile_project(runtime, project_root)
            status = VerificationStatus.PASS if result.success else VerificationStatus.FAIL
            return VerificationResult(
                check_id=check.check_id,
                provider_id=VERIFICATION_PROVIDER_ID,
                category=CompletionEvidenceCategory.TECHNICAL,
                status=status,
                summary=(
                    "Python-Quellen wurden erfolgreich kompiliert."
                    if result.success
                    else "Python-Syntaxprüfung ist fehlgeschlagen."
                ),
                source=VERIFICATION_PROVIDER_ID,
                mode=CompletionEvidenceMode.FACT,
                observed_value=result.output,
                details={
                    "exit_code": result.exit_code,
                    "command": result.command,
                    "executable": result.executable,
                },
            )

        raise KeyError(f"Unbekannter Python-Verification-Check: {check.check_id}")

    # --------------------------------------------------------------- executor
    def execute(
        self,
        context: CapabilityExecutionContext,
        step: CapabilityPlanStep,
    ) -> PythonExecutionResult:
        runtime = self._discover_runtime(
            Path(context.project_path) if context.project_path else None
        )
        if runtime is None:
            return PythonExecutionResult(
                action="inspect",
                success=False,
                exit_code=-1,
                output="Kein ausführbarer Python-Interpreter gefunden.",
                executable=None,
            )

        action = (
            step.action_id.strip().casefold()
            if isinstance(step.action_id, str) and step.action_id.strip()
            else self._requested_action(context.metadata)
        )
        project_root = Path(context.project_path) if context.project_path else None

        if action == "inspect":
            output = (
                f"Python {runtime.version}\n"
                f"Executable: {runtime.executable}\n"
                f"Quelle: {runtime.origin}"
            )
            return PythonExecutionResult(
                action=action,
                success=True,
                exit_code=0,
                output=output,
                executable=str(runtime.executable),
                command=(str(runtime.executable), "--version"),
            )

        if project_root is None or not project_root.is_dir():
            return PythonExecutionResult(
                action=action,
                success=False,
                exit_code=-1,
                output="Für diese Python-Aktion ist ein aktuelles Projekt erforderlich.",
                executable=str(runtime.executable),
            )

        if action == "compile":
            return self._compile_project(runtime, project_root)
        if action == "test":
            return self._test_project(runtime, project_root)

        raise ValueError(
            f"Unzulässige Python-Aktion {action!r}. Erlaubt: inspect, compile, test."
        )

    # --------------------------------------------------------------- helpers
    def _discover_runtime(self, project_root: Path | None) -> PythonRuntime | None:
        candidates: list[tuple[Path, str]] = []
        if project_root is not None:
            for env_name in (".venv", "venv", "env"):
                candidates.extend(
                    [
                        (project_root / env_name / "Scripts" / "python.exe", f"project:{env_name}"),
                        (project_root / env_name / "bin" / "python", f"project:{env_name}"),
                    ]
                )

        for executable_name in ("python", "python3"):
            found = shutil.which(executable_name)
            if found:
                candidates.append((Path(found), f"PATH:{executable_name}"))

        if sys.executable:
            candidates.append((Path(sys.executable), "forge-runtime"))

        seen: set[str] = set()
        for executable, origin in candidates:
            key = os.path.normcase(os.path.abspath(str(executable)))
            if key in seen:
                continue
            seen.add(key)
            if not executable.is_file():
                continue
            probed = self._probe_python(executable)
            if probed is not None:
                return PythonRuntime(executable=executable, origin=origin, version=probed)
        return None

    def _probe_python(self, executable: Path) -> str | None:
        try:
            completed = subprocess.run(
                [str(executable), "--version"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=min(self.command_timeout_seconds, 10.0),
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if completed.returncode != 0:
            return None
        raw = (completed.stdout or completed.stderr).strip()
        if raw.casefold().startswith("python "):
            raw = raw.split(None, 1)[1]
        return raw or "unbekannt"

    def _probe_pytest(self, runtime: PythonRuntime) -> tuple[bool, str | None, int, bool]:
        command = [str(runtime.executable), "-m", "pytest", "--version"]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=min(self.command_timeout_seconds, 15.0),
            )
        except (OSError, subprocess.SubprocessError):
            return False, None, -1, False

        output = (completed.stdout + "\n" + completed.stderr).strip()
        if completed.returncode == 0:
            first_line = output.splitlines()[0] if output else "pytest"
            version = first_line.removeprefix("pytest ").strip() or first_line
            return True, version, completed.returncode, False

        absent = "No module named pytest" in output or "No module named 'pytest'" in output
        return False, None, completed.returncode, absent

    def _compile_project(self, runtime: PythonRuntime, project_root: Path) -> PythonExecutionResult:
        python_files = tuple(self._iter_python_files(project_root))
        if not python_files:
            return PythonExecutionResult(
                action="compile",
                success=True,
                exit_code=0,
                output="Keine Python-Dateien für die Syntaxprüfung gefunden.",
                executable=str(runtime.executable),
                command=(),
            )

        failures: list[str] = []
        checked = 0
        for path in python_files:
            command = [str(runtime.executable), "-m", "py_compile", str(path)]
            try:
                completed = subprocess.run(
                    command,
                    cwd=str(project_root),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=self.command_timeout_seconds,
                )
            except subprocess.TimeoutExpired:
                failures.append(f"{path.relative_to(project_root)}: Timeout")
                continue
            except OSError as error:
                failures.append(f"{path.relative_to(project_root)}: {error}")
                continue

            checked += 1
            if completed.returncode != 0:
                output = (completed.stdout + "\n" + completed.stderr).strip()
                failures.append(
                    f"{path.relative_to(project_root)}:\n{output or 'py_compile fehlgeschlagen'}"
                )

        success = not failures
        output = (
            f"{checked} Python-Datei(en) geprüft."
            if success
            else "\n\n".join(failures)
        )
        return PythonExecutionResult(
            action="compile",
            success=success,
            exit_code=0 if success else 1,
            output=output,
            executable=str(runtime.executable),
            command=(str(runtime.executable), "-m", "py_compile", "<project python files>"),
        )

    def _test_project(self, runtime: PythonRuntime, project_root: Path) -> PythonExecutionResult:
        tests_dir = project_root / "tests"
        has_tests = tests_dir.is_dir() and any(tests_dir.rglob("*.py"))
        if not has_tests:
            return PythonExecutionResult(
                action="test",
                success=True,
                exit_code=0,
                output="Kein Python-Testbestand im Ordner tests gefunden.",
                executable=str(runtime.executable),
                command=(),
            )

        pytest_available, _, _, _ = self._probe_pytest(runtime)
        if pytest_available:
            command = [str(runtime.executable), "-m", "pytest", "-q"]
        else:
            command = [
                str(runtime.executable),
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests",
            ]

        try:
            completed = subprocess.run(
                command,
                cwd=str(project_root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=max(self.command_timeout_seconds, 300.0),
            )
            output = (completed.stdout + "\n" + completed.stderr).strip()
            return PythonExecutionResult(
                action="test",
                success=completed.returncode == 0,
                exit_code=completed.returncode,
                output=output,
                executable=str(runtime.executable),
                command=tuple(command),
            )
        except subprocess.TimeoutExpired as error:
            partial = "\n".join(
                part.decode("utf-8", errors="replace") if isinstance(part, bytes) else str(part)
                for part in (error.stdout, error.stderr)
                if part
            ).strip()
            return PythonExecutionResult(
                action="test",
                success=False,
                exit_code=-1,
                output=(
                    "Python-Testlauf hat das Zeitlimit überschritten."
                    + (f"\n\n{partial}" if partial else "")
                ),
                executable=str(runtime.executable),
                command=tuple(command),
            )

    @staticmethod
    def _requested_action(metadata: Mapping[str, object]) -> str:
        actions = metadata.get("plugin_actions")
        if isinstance(actions, Mapping):
            value = actions.get(PLUGIN_ID)
            if value is not None:
                return str(value).strip().casefold()
        value = metadata.get("python_action")
        if value is not None:
            return str(value).strip().casefold()
        return "inspect"

    @staticmethod
    def _project_markers(project_root: Path) -> tuple[str, ...]:
        return tuple(marker for marker in _PROJECT_MARKERS if (project_root / marker).is_file())

    @staticmethod
    def _iter_python_files(project_root: Path):
        for path in sorted(project_root.rglob("*.py")):
            try:
                relative_parts = path.relative_to(project_root).parts[:-1]
            except ValueError:
                continue
            if any(part in _EXCLUDED_DIRS for part in relative_parts):
                continue
            if path.is_file():
                yield path

    @staticmethod
    def _command_text(command: tuple[str, ...] | list[str]) -> str:
        return subprocess.list2cmdline(list(command))


def register_python_plugin(manager: PluginManager) -> PythonPlugin:
    plugin = PythonPlugin()
    plugin.register(manager)
    return plugin
