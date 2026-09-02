from forgeai.ai.agent_ui_worker import AgentVerificationWorker


def test_verification_worker_is_constructible(tmp_path):
    worker = AgentVerificationWorker(tmp_path)

    assert worker.project_path == tmp_path
    assert worker.test_output == ""
    assert worker.exit_code is None


def test_verification_worker_requires_existing_test_runner(tmp_path):
    worker = AgentVerificationWorker(tmp_path)

    errors = []
    worker.failed.connect(errors.append)

    worker.run()

    assert errors
    assert "Test Runner nicht gefunden" in errors[0]
