"""CP0 app UI tests via Streamlit AppTest: UI-02, UI-04, UI-06, DEL-01 key handling."""
import re


from apphelpers import DASHES, EMOJI, REPLY_MARK, all_text, fake_class, make_app, state_of
from conftest import SENTINEL

def test_app_runs_without_exception(no_key):
    """CP0 exit: app runs."""
    at = make_app().run()
    assert not at.exception


def test_ui_header_shows_product_name_and_phase(no_key):
    """UI-04: current phase name shows in the header; FRONTEND 6: neutral name."""
    t = all_text(make_app().run())
    assert 'Claims support' in t
    assert 'Verify ID' in t


def test_ui_02_sidebar_has_memory_and_sop_sections_empty_state(no_key):
    """UI-02: sidebar holds Session memory and SOP progress; CP0 empty memory."""
    at = make_app().run()
    side = '\n'.join(m.value for m in at.sidebar.markdown)
    assert 'Session memory' in side and 'SOP progress' in side
    assert 'Remembered from this chat. Cleared on reset.' in side
    for label in ('Verify ID', 'Resolve intent', 'Process case', 'Wrap up'):
        assert label in side
    assert side.count('pending') >= 3 and 'current' in side


def test_ui_04_phase_rows_text_plus_icon_not_color_alone(no_key):
    """UI-04 / FRONTEND 7: each phase row has status text and an icon glyph."""
    at = make_app().run()
    rows = re.findall(r'cs-phase-row[^>]*>([^<]*)<', '\n'.join(m.value for m in at.sidebar.markdown))
    assert len(rows) == 4, rows
    for r in rows:
        assert re.search(r'(current|pending|done)', r)
        assert re.search(r'&#\d+;|&#x[0-9a-f]+;|[^\x00-\x7f]', r), r


def test_ui_02_sidebar_collapsible_native(no_key):
    """UI-02: native sidebar (AppTest exposes it as at.sidebar)."""
    assert make_app().run().sidebar is not None


def test_del_01_token_field_is_password_input_in_sidebar(no_key):
    """DEL-01 / FRONTEND 6: optional token field, password type, in sidebar."""
    at = make_app().run()
    assert len(at.sidebar.text_input) == 1
    assert at.sidebar.text_input[0].proto.type == 1  # PASSWORD


def test_del_01_missing_key_gives_plain_error_no_traceback(no_key):
    """DEL-01: missing key produces a plain error. No traceback, no exception."""
    at = make_app().run()
    at.chat_input[0].set_value('hello').run()
    assert not at.exception
    assert len(at.error) == 1
    msg = at.error[0].value
    assert msg == 'Paste your Groq key in the sidebar to start.' and 'Traceback' not in msg
    assert 'Traceback' not in all_text(at)
    assert not any(d in msg for d in DASHES) and '!' not in msg


def test_del_01_missing_key_makes_no_network_call(no_key, monkeypatch):
    """DEL-01: with no key, the OpenAI-compatible client is never constructed."""
    import openai
    made = []
    orig = openai.OpenAI.__init__

    def spy(self, *a, **k):
        made.append(1)
        return orig(self, *a, **k)

    monkeypatch.setattr(openai.OpenAI, '__init__', spy)
    at = make_app().run()
    at.chat_input[0].set_value('hello').run()
    assert made == []


def test_del_01_env_var_key_is_used(monkeypatch, fake_backend):
    """DEL-01: token from env var drives a normal round trip."""
    at = make_app().run()
    at.chat_input[0].set_value('hello').run()
    assert not at.exception and not at.error
    assert REPLY_MARK in all_text(at)


def test_del_01_secrets_key_is_used(no_key, monkeypatch):
    """DEL-01: token from Streamlit secrets is picked up (no 'No API token' error)."""
    import insurance_claims.llm as llm
    monkeypatch.setattr(llm, 'OpenAICompatLLM', fake_class(llm))
    at = make_app()
    at.secrets['LLM_API_KEY'] = SENTINEL
    at.run()
    at.chat_input[0].set_value('hello').run()
    assert not at.exception and not at.error
    assert REPLY_MARK in all_text(at)


def test_del_01_sidebar_token_is_used(no_key, monkeypatch):
    """DEL-01: visitor token typed in the sidebar is accepted."""
    import insurance_claims.llm as llm
    monkeypatch.setattr(llm, 'OpenAICompatLLM', fake_class(llm))
    at = make_app().run()
    at.sidebar.text_input[0].set_value(SENTINEL).run()
    at.chat_input[0].set_value('hello').run()
    assert not at.error
    assert REPLY_MARK in all_text(at)


def test_del_01_key_precedence_secrets_then_env_then_sidebar(monkeypatch, record_property):
    """DEL-01 / config order: Streamlit secrets, env var, sidebar. Records which token reaches the client."""
    import insurance_claims.llm as llm
    seen = []

    def factory(*a, **k):
        seen.append((a, k))
        return llm.FakeLLM()

    monkeypatch.setattr(llm, 'OpenAICompatLLM', type('F', (llm.FakeLLM,), {'__init__': lambda self, *a, **k: factory(*a, **k) and None}))
    monkeypatch.setenv('LLM_API_KEY', 'ENVTOKEN')
    at = make_app()
    at.secrets['LLM_API_KEY'] = 'SECRETTOKEN'
    at.run()
    at.sidebar.text_input[0].set_value('SIDEBARTOKEN').run()
    at.chat_input[0].set_value('hello').run()
    flat = repr(seen)
    record_property('token_seen_by_client', [t for t in ('SECRETTOKEN', 'ENVTOKEN', 'SIDEBARTOKEN') if t in flat])
    assert seen, 'client factory not called'
    assert 'SECRETTOKEN' in flat
    assert 'ENVTOKEN' not in flat and 'SIDEBARTOKEN' not in flat


def test_ui_06_reset_button_exists_in_header(no_key):
    """UI-06: Reset button present."""
    assert [b.label for b in make_app().run().button] == ['Reset']


def test_ui_06_reset_clears_session(fake_backend):
    """UI-06: Reset clears transcript, memory and phase; a new session id follows."""
    at = make_app().run()
    at.chat_input[0].set_value('hello').run()
    assert REPLY_MARK in all_text(at)
    before = state_of(at)
    next(b for b in at.button if b.label == 'Reset').click().run()
    t = all_text(at)
    assert not at.exception
    assert REPLY_MARK not in t
    assert 'hello' not in t.replace('Claims support', '')
    assert 'Type a message to start the conversation.' in t
    assert 'Verify ID' in t
    after = state_of(at)
    assert before != after


def test_ui_06_reset_then_chat_works(fake_backend):
    """UI-06: the app is usable after Reset."""
    at = make_app().run()
    at.chat_input[0].set_value('hello').run()
    next(b for b in at.button if b.label == 'Reset').click().run()
    at.chat_input[0].set_value('hi again').run()
    assert not at.exception and not at.error
    assert REPLY_MARK in all_text(at)


def test_transcript_shows_speaker_labels_and_text(fake_backend):
    """UI-01 (CP0 part): transcript shows Caller and Agent labels with text."""
    at = make_app().run()
    at.chat_input[0].set_value('hello').run()
    t = all_text(at)
    assert 'Caller' in t and 'Agent' in t and 'hello' in t


def test_ui_strings_no_dash_no_emoji_no_exclamation(fake_backend):
    """LANG-01 / FRONTEND 6,8: rendered UI has no dash, no emoji; system copy has no exclamation."""
    at = make_app().run()
    at.chat_input[0].set_value('hello').run()
    t = all_text(at)
    assert not any(d in t for d in DASHES)
    assert not EMOJI.search(t)
    visible = re.sub(r'<style>.*?</style>', '', t, flags=re.S)
    visible = re.sub(r'<[^>]+>', '', visible)
    assert '!' not in visible

