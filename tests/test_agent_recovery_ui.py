from types import SimpleNamespace

import forgeai.ui.main_window as main_window_module
from forgeai.ai.agent_state import AgentState
from forgeai.ui.main_window import MainWindow


class _FakeSignal:
    def __init__(self):
        self.callback = None

    def connect(self, callback):
        self.callback = callback


class _FakeWorker:
    created = None

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.completed = _FakeSignal()
        self.failed = _FakeSignal()
        self.started = False
        self.deleted = False
        _FakeWorker.created = self

    def start(self):
        self.started = True

    def deleteLater(self):
        self.deleted = True


class _FakeInputBar:
    def __init__(self):
        self.busy_values = []

    def set_busy(self, value):
        self.busy_values.append(value)


class _FakeLogger:
    def error(self, *args, **kwargs):
        pass

    def info(self, *args, **kwargs):
        pass


def _make_window(orchestrator, task=None):
    window = MainWindow.__new__(MainWindow)
    window._agent_orchestrator = orchestrator
    window._agent_task = task or SimpleNamespace(task_id="task-1")
    window._agent_verification_worker = None
    window._agent_recovery_worker = None
    window._agent_project_context = "project-context"
    window.model = "test-model"
    window.ollama_url = "http://localhost:11434"
    window.agent_review_enabled = True
    window.workspace = SimpleNamespace(active_project="C:/project")
    window.input_bar = _FakeInputBar()
    window.logger = _FakeLogger()
    window.statuses = []
    window._set_agent_status = window.statuses.append
    return window


def test_verification_failure_starts_recovery(monkeypatch):
    class _FakeOrchestrator:
        def handle_verification_result(self, success, test_output):
            assert success is False
            assert test_output == "1 failed"
            return AgentState.ANALYZING

    window = _make_window(_FakeOrchestrator())

    calls = []

    def fake_start_recovery(test_output):
        calls.append(test_output)

    window._start_agent_recovery = fake_start_recovery

    window._agent_verification_finished(False, 1, "1 failed")

    assert calls == ["1 failed"]
    assert window._agent_verification_worker is None
    assert window.statuses[-1] == "Tests fehlgeschlagen, Analyse erforderlich"


def test_recovery_finished_routes_plan_to_shared_approval(monkeypatch):
    orchestrator = SimpleNamespace()
    window = _make_window(orchestrator)

    worker = _FakeWorker()
    window._agent_recovery_worker = worker

    plan = SimpleNamespace(
        proposed_changes=[],
        summary="Reparaturplan",
        rationale="Test",
    )
    analysis = SimpleNamespace()

    calls = []

    def fake_approval(plan_arg, *, dialog_title, dialog_intro):
        calls.append((plan_arg, dialog_title, dialog_intro))

    window._request_agent_plan_approval = fake_approval

    window._agent_recovery_finished(orchestrator, analysis, plan)

    assert window._agent_recovery_worker is None
    assert worker.deleted is True
    assert window._agent_orchestrator is orchestrator
    assert window._agent_plan is plan
    assert window.input_bar.busy_values[-1] is False
    assert calls == [
        (
            plan,
            "Reparaturplan freigeben",
            "Der Agent hat den fehlgeschlagenen Test analysiert und einen Reparaturplan erstellt.",
        )
    ]


def test_verification_worker_error_starts_recovery():
    class _FakeOrchestrator:
        run = SimpleNamespace(state=AgentState.TESTING)

        def handle_verification_result(self, success, test_output):
            assert success is False
            assert test_output == "Verification worker error: runner timeout"
            return AgentState.ANALYZING

    window = _make_window(_FakeOrchestrator())

    worker = _FakeWorker()
    window._agent_verification_worker = worker

    calls = []

    def fake_start_recovery(test_output):
        calls.append(test_output)

    window._start_agent_recovery = fake_start_recovery

    window._agent_verification_failed("runner timeout")

    assert calls == ["Verification worker error: runner timeout"]
    assert window._agent_verification_worker is None
    assert worker.deleted is True
    assert window.statuses[-1] == "Verifikationsfehler, Analyse erforderlich"



def test_noop_agent_plan_completes_without_approval_or_coder(monkeypatch):
    class _FakeOrchestrator:
        def __init__(self):
            self.completed = False
            self.run = SimpleNamespace(state=AgentState.PLANNING)

        def complete_without_changes(self):
            self.completed = True
            self.run.state = AgentState.COMPLETED
            return AgentState.COMPLETED

    orchestrator = _FakeOrchestrator()
    window = _make_window(orchestrator)

    window.chat_view = SimpleNamespace(pending=None)
    window.chat_id = None

    coder_calls = []
    window._start_agent_coder_stream = lambda: coder_calls.append(True)

    approval_calls = []
    monkeypatch.setattr(
        main_window_module.QMessageBox,
        "question",
        lambda *args, **kwargs: approval_calls.append(True),
    )

    plan = SimpleNamespace(
        proposed_changes=[],
        summary="Keine ?nderung erforderlich",
        rationale="Die gew?nschte Pr?fung ist bereits vorhanden.",
    )

    window._request_agent_plan_approval(
        plan,
        dialog_title="Agent-Plan freigeben",
        dialog_intro="Test",
    )

    assert orchestrator.completed is True
    assert orchestrator.run.state == AgentState.COMPLETED
    assert coder_calls == []
    assert approval_calls == []
    assert window.statuses[-1] == "Keine " + chr(0xE4) + "nderungen erforderlich"
    assert window.input_bar.busy_values[-1] is False
