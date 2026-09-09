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

def test_analysis_response_format_is_structured():
    schema = MainWindow._analysis_response_format(
        "analysiere das aktuelle projekt"
    )

    assert schema is not None
    assert schema["type"] == "object"
    assert "claims" in schema["properties"]
    assert schema["properties"]["claims"]["type"] == "array"

    item = schema["properties"]["claims"]["items"]

    assert "claim_type" in item["properties"]
    assert "statement" in item["properties"]
    assert "target" in item["properties"]
    assert "source_file" in item["properties"]
    assert "category" in item["properties"]


def test_non_analysis_has_no_analysis_response_format():
    assert (
        MainWindow._analysis_response_format("zeige mir die datei")
        is None
    )

def test_analysis_instructions_require_structured_claim_json():
    instructions = MainWindow._analysis_instructions()

    assert '"claims"' in instructions
    assert "claim_type" in instructions
    assert "target" in instructions
    assert "source_file" in instructions
    assert "source_line" in instructions
    assert "ForgeAI prüft jeden Claim" in instructions
    assert "JSON-actions" in instructions
    assert "ChangePreview" in instructions


def test_analysis_instructions_do_not_treat_model_as_final_validator():
    instructions = MainWindow._analysis_instructions()

    assert "Du bist NICHT die Instanz" in instructions
    assert "Die endgültige Einstufung übernimmt ForgeAI" in instructions
    assert "keine sichere Einstufung" not in instructions.casefold()

def test_structured_analysis_response_is_processed_as_claim_payload():
    from forgeai.core.evidence_validator import ClaimStatus, ClaimType
    from forgeai.core.project_evidence import ProjectEvidence

    window = MainWindow.__new__(MainWindow)

    window.workspace = type(
        "Workspace",
        (),
        {
            "active_project": "C:/demo",
            "analyzer": None,
        },
    )()

    class Analyzer:
        def analyze(self, project_path):
            return {
                "project_path": str(project_path),
                "project_name": "demo",
                "files": ["main.py"],
                "classes": {},
                "imports": {},
            }

        def evidence_summary(self, project_path):
            return {
                "project_path": str(project_path),
                "functions": {},
                "event_handlers": {
                    "main.py": [
                        "pygame.MOUSEBUTTONDOWN",
                        "pygame.MOUSEBUTTONDOWN",
                    ]
                },
                "event_retrievals": {},
                "syntax_errors": {},
            }

    window.workspace.analyzer = Analyzer()

    from forgeai.core.evidence_validator import EvidenceValidator

    window.evidence_validator = EvidenceValidator()

    response = """{
      "claims": [
        {
          "claim_type": "duplicate_event_handler",
          "statement": "Doppelte MOUSEBUTTONDOWN-Verarbeitung.",
          "target": "pygame.MOUSEBUTTONDOWN",
          "source_file": "main.py",
          "source_line": null,
          "category": "error"
        }
      ]
    }"""

    result = window._validate_analysis_response(response)

    assert "Doppelte MOUSEBUTTONDOWN-Verarbeitung." in result
    assert "BELEGT" in result
    assert "evidence:" in result.casefold()
