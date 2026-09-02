from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from .agent_contracts import AgentTask
from .agent_orchestrator import AgentOrchestrator
from .agent_planner import AgentPlanner
from .agent_reviewer import AgentReviewer
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

            planner = AgentPlanner(router)
            reviewer = AgentReviewer(router)

            run = AgentRun(task_id=self.task.task_id)
            orchestrator = AgentOrchestrator(
                run,
                planner=planner,
                reviewer=reviewer,
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
                    raise RuntimeError(f"Reviewer hat den Agentenplan abgelehnt: {findings}")

                if state == AgentState.ABORTED:
                    findings = "; ".join(review.findings) or "Keine weiteren Angaben."
                    raise RuntimeError(f"Reviewer hat den Agentenplan abgelehnt: {findings}")

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