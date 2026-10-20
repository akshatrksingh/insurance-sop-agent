"""CP0 SAFE-04 and MEM-04 tests via Streamlit AppTest."""


from apphelpers import all_text, make_app, state_of
from conftest import ROOT, SENTINEL
from failhelpers import EXC_FACTORIES, boom_backend

def test_safe_04_token_absent_from_ui_logs_and_state(monkeypatch, fake_backend, log_capture):
    """SAFE-04: token never in UI text, session state, or logs (success path)."""
    at = make_app().run()
    at.chat_input[0].set_value('hello').run()
    assert SENTINEL not in all_text(at)
    assert SENTINEL not in repr(state_of(at))
    assert SENTINEL not in '\n'.join(log_capture)


def test_safe_04_token_absent_on_auth_failure_path(monkeypatch, log_capture):
    """SAFE-04: a rejected token (fake client raising the openai 401) gives a plain error and the token is in no UI text, state, or log."""
    boom_backend(monkeypatch, EXC_FACTORIES['openai.AuthenticationError'], 'both')
    at = make_app().run()
    at.chat_input[0].set_value('hello').run()
    assert not at.exception
    t = all_text(at)
    assert SENTINEL not in t and 'Traceback' not in t
    assert SENTINEL not in repr(state_of(at))
    assert SENTINEL not in '\n'.join(log_capture)
    assert len(at.error) == 1


def test_safe_04_token_absent_when_typed_in_sidebar(monkeypatch, no_key, log_capture):
    """SAFE-04: sidebar token (fake client raising the openai 401) never echoed in UI or logs."""
    boom_backend(monkeypatch, EXC_FACTORIES['openai.AuthenticationError'], 'both')
    monkeypatch.delenv('LLM_API_KEY', raising=False)
    at = make_app().run()
    at.sidebar.text_input[0].set_value(SENTINEL).run()
    at.chat_input[0].set_value('hello').run()
    t = all_text(at)
    assert SENTINEL not in t
    assert SENTINEL not in '\n'.join(log_capture)
    assert at.error and not at.exception


def test_safe_04_token_not_in_session_view(monkeypatch):
    """SAFE-04 / guidelines: Session and view never hold the token."""
    from insurance_claims.llm import FakeLLM
    from insurance_claims.orchestrator import handle_turn, new_session
    monkeypatch.setenv('LLM_API_KEY', SENTINEL)
    s = new_session()
    handle_turn(s, 'hello', FakeLLM())
    assert SENTINEL not in s.view().model_dump_json()
    assert SENTINEL not in repr(s)


def test_safe_04_logs_have_no_caller_text_or_pii(monkeypatch, log_capture):
    """SAFE-04: logs never contain PII or caller text."""
    from insurance_claims.llm import FakeLLM
    from insurance_claims.orchestrator import handle_turn, new_session
    pii = 'Margaret Chen 650 521 2836 margaret@example.com POL-9921 4472'
    s = new_session()
    handle_turn(s, pii, FakeLLM())
    joined = '\n'.join(log_capture)
    for frag in ('Margaret', '650 521 2836', 'margaret@example.com', 'POL-9921', '4472'):
        assert frag not in joined, frag


def test_safe_04_traceback_not_shown_on_llm_exception(monkeypatch):
    """SAFE-04: an exception carrying the token inside a client call is not shown."""
    import insurance_claims.llm as llm

    class Boom(llm.FakeLLM):
        def reply(self, *a, **k):
            raise RuntimeError(f'failure with {SENTINEL}')

        def extract(self, *a, **k):
            raise RuntimeError(f'failure with {SENTINEL}')

    monkeypatch.setenv('LLM_API_KEY', SENTINEL)
    monkeypatch.setattr(llm, 'OpenAICompatLLM', type('B', (Boom,), {'__init__': lambda self, *a, **k: None}))
    at = make_app().run()
    at.chat_input[0].set_value('hello').run()
    t = all_text(at)
    assert SENTINEL not in t and 'Traceback' not in t
    assert not at.exception


def test_mem_04_nothing_written_to_disk(fake_backend, tmp_path):
    """MEM-04: a chat turn writes no new files under the repo (excluding caches)."""
    def snap():
        return {p for p in ROOT.rglob('*') if p.is_file()
                and not {'goaly-venv', '__pycache__', '.pytest_cache', '.git'} & set(p.parts)}
    before = snap()
    at = make_app().run()
    at.chat_input[0].set_value('hello').run()
    assert snap() - before == set()

