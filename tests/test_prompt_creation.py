"""Regression checks for direct prompt writing in the local chat."""

import ast
from pathlib import Path

import pytest

from forgeai.ai.prompts import PROMPT_CREATION_INSTRUCTIONS
from forgeai.ai.request_routing import (
    is_creative_prompt_request, is_project_change_request,
    is_standalone_prompt_request,
)


@pytest.mark.parametrize('user_text', [
    'erstelle prompt für frau im schlafzimmer erotisch',
    'Erstelle einen FLUX-Prompt für ein Schlafzimmer',
    'Gib mir einen Video-Prompt für Wan',
    'Schreibe einen Bildprompt für eine erwachsene Frau',
])
def test_creative_prompt_is_direct_chat(user_text):
    assert not is_project_change_request(user_text)
    assert is_creative_prompt_request(user_text)
    assert is_standalone_prompt_request(user_text)


@pytest.mark.parametrize('user_text', [
    'Erstelle einen Prompt und speichere ihn als Datei',
    'Ändere main.py und erstelle einen Prompt für den Kommentar',
    'Erstelle ein neues Spiel mit zehn Einheiten',
    'Wie war die letzte Projektanalyse?',
])
def test_other_requests_are_not_standalone_prompt_chat(user_text):
    assert not is_standalone_prompt_request(user_text)


def test_prompt_followup_keeps_history():
    request = 'Erstelle den gleichen Prompt wie zuvor mit warmem Licht'
    assert is_creative_prompt_request(request)
    assert not is_standalone_prompt_request(request)


def test_prompt_instructions_give_output_not_unfounded_policy():
    assert 'kopierbaren' in PROMPT_CREATION_INSTRUCTIONS
    assert 'erwachsenen Person' in PROMPT_CREATION_INSTRUCTIONS
    assert 'Sondergenehmigung' in PROMPT_CREATION_INSTRUCTIONS
    assert 'Grenzen des Modells bleiben bestehen' in PROMPT_CREATION_INSTRUCTIONS


def test_real_ui_uses_prompt_instructions_and_isolates_fresh_brief():
    path = Path(__file__).resolve().parents[1] / 'forgeai/ui/main_window.py'
    source = path.read_text(encoding='utf-8')
    ast.parse(source)
    assert 'is_creative_prompt_request(text)' in source
    assert 'PROMPT_CREATION_INSTRUCTIONS' in source
    assert 'if is_prompt_request and is_standalone_prompt_request(text):' in source
    assert 'messages.append({"role": "user", "content": text})' in source
    assert 'context, included_files = "", []' in source


def test_actual_send_message_sends_fresh_prompt_without_old_refusal_or_project_files():
    """Run the real send_message body without loading Qt or contacting Ollama."""
    from types import SimpleNamespace

    path = Path(__file__).resolve().parents[1] / 'forgeai/ui/main_window.py'
    module = ast.parse(path.read_text(encoding='utf-8'))
    main_window = next(node for node in module.body if isinstance(node, ast.ClassDef) and node.name == 'MainWindow')
    method = next(node for node in main_window.body if isinstance(node, ast.FunctionDef) and node.name == 'send_message')
    harness_module = ast.Module(body=[ast.ClassDef(name='Harness', bases=[], keywords=[], body=[method], decorator_list=[])], type_ignores=[])
    ns = {
        'SYSTEM_PROMPT': __import__('forgeai.ai.prompts', fromlist=['SYSTEM_PROMPT']).SYSTEM_PROMPT,
        'PROMPT_CREATION_INSTRUCTIONS': PROMPT_CREATION_INSTRUCTIONS,
        'is_creative_prompt_request': is_creative_prompt_request,
        'is_standalone_prompt_request': is_standalone_prompt_request,
        'is_local_read_request': __import__('forgeai.ai.request_routing', fromlist=['is_local_read_request']).is_local_read_request,
    }
    exec(compile(ast.fix_missing_locations(harness_module), str(path), 'exec'), ns)
    window = ns['Harness']()
    window.worker = None
    window.chat_id = 1
    window._pending_change_previews = None
    window._is_change_request = is_project_change_request
    window._action_response_format = lambda _: None
    window._is_analysis_request = lambda _: False
    window._context_hard_limit = lambda: 8192
    window.ollama_url = 'http://localhost:11434'
    window.model = 'local-test-model'
    window.logger = SimpleNamespace(info=lambda *args: None)
    window.workspace = SimpleNamespace(active_project='an active coding project')
    window.ai_context = SimpleNamespace(build=lambda *a, **k: (_ for _ in ()).throw(AssertionError('project files leaked into a standalone prompt')))

    rows = [{'role': 'user', 'content': 'erstelle prompt für frau im schlafzimmer erotisch'},
            {'role': 'assistant', 'content': 'Ich muss ethische Grenzen beachten; erst Genehmigung.'}]
    window.history = SimpleNamespace(
        add_message=lambda id, role, content: rows.append({'role': role, 'content': content}),
        messages=lambda id: rows,
        title_chat=lambda *args: None,
    )
    window.chat_view = SimpleNamespace(add_message=lambda *a: None, append_stream=lambda *a: None)
    window.input_bar = SimpleNamespace(set_busy=lambda value: None)

    captured = {}
    class FakeSignal:
        def connect(self, callback):
            pass
    class FakeWorker:
        token_received = FakeSignal()
        completed = FakeSignal()
        failed = FakeSignal()
        def start(self):
            captured['started'] = True
    def stream_chat(*args, **kwargs):
        captured['args'] = args
        captured['kwargs'] = kwargs
        return FakeWorker()
    window.ollama = SimpleNamespace(
        get_context_length=lambda *a: 8192,
        recommend_context_length=lambda *a, **k: {
            'recommended_context': 8192, 'context_length': 8192,
            'gpu_vram_total_bytes': None, 'system_ram_total_bytes': None,
            'system_ram_available_bytes': None, 'model_size_bytes': None, 'reason': 'test',
        },
        stream_chat=stream_chat,
    )
    window._response_done = lambda: None
    window._response_failed = lambda _: None
    window.send_message('erstelle prompt für frau im schlafzimmer erotisch')
    messages = captured['args'][2]
    assert len(messages) == 2
    assert messages[0]['role'] == 'system' and 'kopierbaren Prompt' in messages[0]['content']
    assert messages[1] == {'role': 'user', 'content': 'erstelle prompt für frau im schlafzimmer erotisch'}
    assert captured['args'][3] is None  # text response, not JSON-action schema
    assert captured['started']
