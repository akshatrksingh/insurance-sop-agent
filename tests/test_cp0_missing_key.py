"""CP0 DEL-01 missing key notice timing and visibility."""


from apphelpers import REPLY_MARK
from failhelpers import app, visible, T

def test_del_01_missing_key_notice_at_page_load(no_key):
    """DEL-01: with no key, a plain notice is visible at page load, before any message."""
    at = app().run()
    assert not at.exception
    notices = [e.value for e in at.error] + [e.value for e in at.warning] + [e.value for e in at.info]
    assert any('LLM_API_KEY' in n for n in notices)


def test_del_01_missing_key_notice_after_first_message(no_key):
    """DEL-01: with no key, the notice is visible after the first message."""
    at = app().run()
    at.chat_input[0].set_value('hello').run()
    notices = [e.value for e in at.error] + [e.value for e in at.warning] + [e.value for e in at.info]
    assert any('LLM_API_KEY' in n for n in notices)


def test_del_01_missing_key_notice_clears_when_token_pasted(no_key, monkeypatch):
    """DEL-01: after the sidebar token is pasted and a message sent, the missing-key notice is gone."""
    import insurance_claims.llm as llm

    class F(llm.FakeLLM):
        def __init__(self, *a, **k):
            super().__init__()

    monkeypatch.setattr(llm, 'OpenAICompatLLM', F)
    at = app().run()
    at.chat_input[0].set_value('hello').run()
    assert at.error
    at.sidebar.text_input[0].set_value(T).run()
    at.chat_input[0].set_value('hello again').run()
    assert not at.error
    assert REPLY_MARK in visible(at)


def test_del_01_missing_key_caller_message_visible(no_key):
    """UI-01 (failed turn): with no key, the caller's message stays visible after sending."""
    at = app().run()
    at.chat_input[0].set_value('my unique message zq').run()
    assert 'my unique message zq' in visible(at)


def test_del_01_missing_key_notice_has_no_dash_or_exclamation(no_key):
    """LANG-01 / FRONTEND 6: the missing-key notice has no dash and no exclamation mark."""
    at = app().run()
    at.chat_input[0].set_value('hello').run()
    for e in list(at.error) + list(at.warning) + list(at.info):
        assert '\u2014' not in e.value and '\u2013' not in e.value and '!' not in e.value



def test_isolation_no_secrets_and_no_env_key_visible():
    """Suite isolation: the app sees no key from secrets files or the environment (values never printed)."""
    import os
    from streamlit.runtime.secrets import secrets_singleton
    assert not os.environ.get('LLM_API_KEY')
    assert secrets_singleton.load_if_toml_exists() is False
