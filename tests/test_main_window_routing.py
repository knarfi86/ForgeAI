from types import SimpleNamespace

from forgeai.ui.main_window import MainWindow


class _FakeWorker:
    content = "Normale Analyseantwort"


class _FakeSignal:
    def connect(self, callback):
        self.callback = callback


class _FakeInputBar:
    def __init__(self):
        self.busy_values = []

    def set_busy(self, value):
        self.busy_values.append(value)


class _FakePending:
    def __init__(self):
        self.content = None

    def set_content(self, content):
        self.content = content


class _FakeChatView:
    def __init__(self):
        self.pending = _FakePending()
        self.proposals = []

    def add_change_proposal(self, *args):
        self.proposals.append(args)


class _FakeHistory:
    def __init__(self):
        self.messages_added = []

    def add_message(self, chat_id, role, content):
        self.messages_added.append((chat_id, role, content))


def _make_window():
    window = MainWindow.__new__(MainWindow)
    window.worker = _FakeWorker()
    window.chat_id = 1
    window._stream_is_action = False
    window._pending_change_previews = None
    window.chat_view = _FakeChatView()
    window.history = _FakeHistory()
    window.input_bar = _FakeInputBar()
    window.refresh_chats = lambda: None

    return window


def test_analysis_response_never_prepares_change_previews(monkeypatch):
    window = _make_window()

    calls = []

    def forbidden_prepare(response):
        calls.append(response)
        raise AssertionError(
            "_prepare_model_changes darf bei einer Analyseantwort nicht aufgerufen werden"
        )

    window._prepare_model_changes = forbidden_prepare

    window._response_done()

    assert calls == []
    assert window._pending_change_previews is None
    assert window.chat_view.pending.content == "Normale Analyseantwort"
    assert window._stream_is_action is False
