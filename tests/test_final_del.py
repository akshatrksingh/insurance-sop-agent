"""Final pass: DEL-02 and DEL-03 through app.py."""
import pytest

from apphelpers import all_text, make_app
from conftest import SENTINEL
from cp2helpers import S1_TEXT
from cp4helpers import DONE, EXTRACTIONS


@pytest.fixture
def scripted(monkeypatch):
    """Route the app to a FakeLLM scripted with the CP4 extractions."""
    import insurance_claims.llm as llm

    class Scripted(llm.FakeLLM):
        def __init__(self, *a, **k):
            super().__init__(extractions=EXTRACTIONS, replies={})

    monkeypatch.setenv('LLM_API_KEY', SENTINEL)
    monkeypatch.setattr(llm, 'OpenAICompatLLM', Scripted)


def page(at):
    """Main column markdown joined."""
    return '\n'.join(m.value for m in at.main.markdown)


def test_del_02_text_chat_ui_accepts_natural_language_and_shows_a_reply(scripted):
    """DEL-02: a chat input exists, a typed sentence yields an Agent row, no exception."""
    at = make_app().run()
    assert len(at.chat_input) == 1
    at.chat_input[0].set_value('hello').run()
    assert 'cs-who">Agent<' in page(at) and 'cs-who">Caller<' in page(at) and not at.exception


def test_del_03_demo_shows_the_full_workflow_in_the_app(scripted):
    """DEL-03: through app.py one conversation passes verification, intent, case processing and the email follow-up."""
    at = make_app().run()
    at.chat_input[0].set_value(S1_TEXT).run()
    assert at.session_state['session'].view().phase == 'PROCESS_CASE'
    at.chat_input[0].set_value('deadline?').run()
    at.chat_input[0].set_value(DONE).run()
    assert 'Send summary' in [b.label for b in at.button]
    [b for b in at.button if b.label == 'Send summary'][0].click().run()
    view = at.session_state['session'].view()
    shown = page(at)
    assert view.phase == 'COMPLETE' and view.email_preview is not None
    for text in ('Verification complete', 'Case found: CL-2048', 'Email sent'):
        assert text in shown, text
    assert SENTINEL not in all_text(at) and not at.exception
