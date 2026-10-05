import json
from dataclasses import asdict
from types import SimpleNamespace

import forgeai.ai.agent_ui_worker as worker_module
import forgeai.ui.main_window as window_module
from forgeai.ai.agent_contracts import AgentPlan, AgentTask
from forgeai.ai.agent_orchestrator import AgentOrchestrator
from forgeai.ai.agent_state import AgentRun, AgentState
from forgeai.core.ai_context import AIContextProvider
from forgeai.core.file_indexer import FileIndexer
from forgeai.core.filesystem import FileSystem
from forgeai.core.workspace_database import WorkspaceDatabase
from forgeai.core.workspace_manager import WorkspaceManager
from forgeai.ui.main_window import MainWindow


def test_verification_history_tracks_same_changed_and_resolved_failure():
    run = AgentRun("task-1")
    orchestrator = AgentOrchestrator(run)
    orchestrator.current_plan = AgentPlan(
        summary="Fix movement",
        proposed_changes=[{"path": "main.py", "action": "replace"}],
    )
    outputs = [
        (False, 'File "/tmp/game/main.py", line 12\nKeyError: velocity'),
        (False, 'File "C:\\Game\\main.py", line 99\nKeyError: velocity'),
        (False, 'File "C:\\Game\\main.py", line 99\nKeyError: health'),
        (True, "2 passed in 0.1s"),
    ]
    for index, (success, output) in enumerate(outputs):
        if index:
            orchestrator.begin_repair()
        orchestrator.begin_execution()
        orchestrator.begin_testing()
        orchestrator.handle_verification_result(success, output)

    history = run.verification_history
    assert len(history) == 4
    assert history[0].failure_fingerprint == history[1].failure_fingerprint
    assert history[1].failure_fingerprint != history[2].failure_fingerprint
    assert history[3].failure_fingerprint is None
    assert [entry.execution_round for entry in history] == [1, 2, 3, 4]
    assert [entry.repair_attempt for entry in history] == [0, 1, 2, 3]
    assert history[0].planned_paths == ("main.py",)
    assert history[0].test_output == outputs[0][1]
    orchestrator.current_plan.proposed_changes[0]["path"] = "other.py"
    assert history[0].planned_paths == ("main.py",)
    json.dumps([asdict(entry) for entry in history])
    assert run.state == AgentState.COMPLETED


def test_out_of_state_verification_does_not_record_result():
    import pytest

    run = AgentRun("task-1")
    with pytest.raises(RuntimeError):
        AgentOrchestrator(run).handle_verification_result(False, "error")
    assert run.verification_history == []
    assert AgentRun("other-task").verification_history == []


def test_real_workspace_refresh_reaches_analyzer_repairer_reviewer_and_coder(tmp_path, monkeypatch):
    project = tmp_path / "game"
    project.mkdir()
    source = project / "main.py"
    source.write_text("OLD_SOURCE = True", encoding="utf-8")
    (project / "private.py").write_text("PRIVATE_SECRET = True", encoding="utf-8")
    db = WorkspaceDatabase(tmp_path / "workspace.db")
    fs = FileSystem()
    workspace = WorkspaceManager(db, FileIndexer(db, fs))
    workspace.open_project(project)
    workspace.grant_ai_access(source)
    provider = AIContextProvider(db, fs, workspace.ai_accessible_files)
    old_context, _ = provider.build(project)
    source.write_text("NEW_SOURCE = True", encoding="utf-8")
    new_file = project / "new.py"
    new_file.write_text("NEW_FILE = True", encoding="utf-8")
    workspace.grant_session_access(new_file)

    window = MainWindow.__new__(MainWindow)
    window.workspace = workspace
    window.ai_context = provider
    window._agent_project_context = old_context
    window._agent_num_ctx = 8192
    window._agent_reality = None
    window._agent_task = AgentTask(task_id="task-1", user_request="Fix movement")
    run = AgentRun("task-1", state=AgentState.TESTING)
    orchestrator = AgentOrchestrator(run)
    orchestrator.handle_verification_result(False, "KeyError: velocity")
    window._agent_orchestrator = orchestrator
    window._agent_recovery_worker = None
    window.model = "test-model"
    window.ollama_url = "http://localhost:11434"
    window.agent_review_enabled = True
    window.logger = SimpleNamespace(info=lambda *args: None, error=lambda *args: None)
    window.input_bar = SimpleNamespace(set_busy=lambda busy: None)
    window._set_agent_status = lambda text: None

    responses = iter([
        {"summary": "Missing velocity", "root_cause": "Key missing", "repair_requirements": ["Initialize velocity"]},
        {"summary": "Initialize", "proposed_changes": [{"action": "replace", "path": "main.py", "description": "Initialize velocity"}]},
        {"decision": "approve", "findings": [], "required_changes": [], "rationale": "Valid"},
    ])
    prompts = []

    def generate(self, *, prompt, **kwargs):
        prompts.append(prompt)
        return json.dumps(next(responses))

    monkeypatch.setattr(worker_module.OllamaClient, "generate", generate)

    class InlineRecoveryWorker(worker_module.AgentRecoveryWorker):
        def __init__(self, **kwargs):
            kwargs.pop("parent")
            super().__init__(**kwargs)

        def start(self):
            self.run()

    monkeypatch.setattr(window_module, "AgentRecoveryWorker", InlineRecoveryWorker)
    results, errors = [], []
    window._agent_recovery_finished = lambda *args: results.append(args)
    window._agent_recovery_failed = errors.append
    window._start_agent_recovery("KeyError: velocity")

    assert errors == []
    assert len(results) == 1
    assert len(prompts) == 3
    for prompt in prompts:
        assert "NEW_SOURCE = True" in prompt
        assert "NEW_FILE = True" in prompt
        assert "OLD_SOURCE = True" not in prompt
        assert "PRIVATE_SECRET" not in prompt
    # Coder consumes the same MainWindow context after repair approval.
    assert "NEW_SOURCE = True" in window._agent_project_context
    assert "NEW_FILE = True" in window._agent_project_context
    assert orchestrator.run.state == AgentState.APPROVAL_REQUIRED
    assert "new.py" in [row["relative_path"] for row in db.fetchall(
        "SELECT relative_path FROM project_files WHERE project_path=?", (str(project),)
    )]
    db.connection.close()
