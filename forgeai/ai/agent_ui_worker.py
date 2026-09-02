from __future__ import annotations

import subprocess
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from .agent_contracts import AgentTask
from .agent_orchestrator import AgentOrchestrator
from .agent_planner import AgentPlanner
from .agent_repairer import AgentRepairer
from .agent_reviewer import AgentReviewer
from .agent_analyzer import AgentAnalyzer
from .agent_state import AgentRun, AgentState
from .model_router import ModelRouter
from .ollama_client import OllamaClient
from .ollama_provider import OllamaProvider


class AgentWorkflowWorker(QThread):
    """Runs planner/reviewer orchestration away from the Qt UI thread."""

    completed = Signal(object, object, object)
    failed = Signal(str)

    def __init__(
        self,
        task: AgentTask,
        project_context: str,
        model: str,
        base_url: str,
        review_enabled: bool = True,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.task = task
        self.project_context = project_context
        self.model = model
        self.base_url = base_url
        self.review_enabled = review_enabled

    def run(self) -> None:
        try:
            client = OllamaClient()
            provider = OllamaProvider(
                client=client,
                base_url=self.base_url,
            )

            router = ModelRouter()
            router.register_provider("ollama", provider)
            router.set_route("planner", "ollama", self.model)
            router.set_route("reviewer", "ollama", self.model)
            router.set_route("advisor", "ollama", self.model)
            router.set_route("repairer", "ollama", self.model)

            planner = AgentPlanner(router)
            reviewer = AgentReviewer(router)
            analyzer = AgentAnalyzer(router)
            repairer = AgentRepairer(router)

            run = AgentRun(task_id=self.task.task_id)
            orchestrator = AgentOrchestrator(
                run,
                planner=planner,
                reviewer=reviewer,
                analyzer=analyzer,
                repairer=repairer,
                review_enabled=self.review_enabled,
                require_user_approval=True,
            )

            orchestrator.start()

            while True:
                plan = orchestrator.plan(
                    self.task,
                    self.project_context,
                )

                if not self.review_enabled:
                    orchestrator.request_approval()
                    break

                orchestrator.begin_review()

                review = orchestrator.review(
                    self.project_context,
                )

                state = orchestrator.handle_review_result(review)

                if state == AgentState.ABORTED:
                    findings = "; ".join(review.findings) or "Keine weiteren Angaben."
                    raise RuntimeError(
                        f"Reviewer hat den Agentenplan abgelehnt: {findings}"
                    )

                if state == AgentState.PLANNING:
                    continue

                break

            self.completed.emit(
                orchestrator,
                self.task,
                plan,
            )

        except Exception as error:
            self.failed.emit(str(error))


class AgentVerificationWorker(QThread):
    """Runs the existing ForgeAI test runner outside the Qt UI thread."""

    completed = Signal(bool, int, str)
    failed = Signal(str)

    def __init__(
        self,
        project_path: str | Path,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.project_path = Path(project_path)
        self.test_output = ""
        self.exit_code: int | None = None

    def run(self) -> None:
        try:
            script = self.project_path / "scripts" / "run_tests.ps1"

            if not script.is_file():
                raise FileNotFoundError(
                    f"Test Runner nicht gefunden: {script}"
                )

            completed = subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(script),
                ],
                cwd=str(self.project_path),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            self.exit_code = completed.returncode
            self.test_output = (
                completed.stdout
                + (
                    "\n\n" + completed.stderr
                    if completed.stderr
                    else ""
                )
            ).strip()

            self.completed.emit(
                completed.returncode == 0,
                completed.returncode,
                self.test_output,
            )

        except Exception as error:
            self.failed.emit(str(error))

class AgentRecoveryWorker(QThread):
    """Runs failure analysis and repair planning outside the Qt UI thread."""

    completed = Signal(object, object, object)
    failed = Signal(str)

    def __init__(
        self,
        orchestrator: AgentOrchestrator,
        task: AgentTask,
        test_output: str,
        project_context: str,
        model: str,
        base_url: str,
        review_enabled: bool = True,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.orchestrator = orchestrator
        self.task = task
        self.test_output = test_output
        self.project_context = project_context
        self.model = model
        self.base_url = base_url
        self.review_enabled = review_enabled

    def run(self) -> None:
        try:
            client = OllamaClient()
            provider = OllamaProvider(
                client=client,
                base_url=self.base_url,
            )

            router = ModelRouter()
            router.register_provider("ollama", provider)
            router.set_route("planner", "ollama", self.model)
            router.set_route("reviewer", "ollama", self.model)
            router.set_route("advisor", "ollama", self.model)
            router.set_route("repairer", "ollama", self.model)

            analyzer = AgentAnalyzer(router)
            repairer = AgentRepairer(router)
            planner = AgentPlanner(router)
            reviewer = AgentReviewer(router)

            self.orchestrator.analyzer = analyzer
            self.orchestrator.repairer = repairer
            self.orchestrator.planner = planner
            self.orchestrator.reviewer = reviewer

            self.orchestrator.begin_analysis()

            analysis = self.orchestrator.analyze(
                self.task,
                self.test_output,
                self.project_context,
            )

            self.orchestrator.begin_repair()

            while True:
                plan = self.orchestrator.repair(
                    self.task,
                    self.project_context,
                    analysis,
                )

                if not self.review_enabled:
                    self.orchestrator.request_approval()
                    break

                self.orchestrator.begin_review()

                review = self.orchestrator.review(
                    self.project_context,
                )

                state = self.orchestrator.handle_review_result(review)

                if state == AgentState.ABORTED:
                    findings = (
                        "; ".join(review.findings)
                        or "Keine weiteren Angaben."
                    )
                    raise RuntimeError(
                        "Reviewer hat den Reparaturplan abgelehnt: "
                        f"{findings}"
                    )

                if state == AgentState.PLANNING:
                    plan = self.orchestrator.plan(
                        self.task,
                        self.project_context,
                    )
                    continue

                break

            self.completed.emit(
                self.orchestrator,
                analysis,
                plan,
            )

        except Exception as error:
            self.failed.emit(str(error))
