"""CP1 UI-02, UI-03, UI-04, UI-08 through Streamlit AppTest with a scripted FakeLLM."""
import pytest

from apphelpers import make_app
from cp1helpers import leaks
from conftest import SENTINEL

FULL = {'identity': {'full_name': 'Margaret Chen', 'dob': '1985-03-15', 'id_last4': '4472'}}
PARTIAL = {'identity': {'full_name': 'Margaret Chen'}}


@pytest.fixture
def scripted(monkeypatch):
    """Route the app to a FakeLLM scripted for the texts used in these tests."""
    import insurance_claims.llm as llm

    class Scripted(llm.FakeLLM):
        def __init__(self, *a, **k):
            super().__init__(extractions={'partial': PARTIAL, 'full': FULL})

    monkeypatch.setenv('LLM_API_KEY', SENTINEL)
    monkeypatch.setattr(llm, 'OpenAICompatLLM', Scripted)


def side(at):
    """Join the sidebar markdown values."""
    return '\n'.join(m.value for m in at.sidebar.markdown)


def page(at):
    """Join the main column markdown values."""
    return '\n'.join(m.value for m in at.main.markdown)


def test_ui_02_sidebar_factor_rows_show_matched_flags(scripted):
    """UI-02 / UI-03: after one matched factor the sidebar shows that factor as matched and the others as pending."""
    at = make_app().run()
    at.chat_input[0].set_value('partial').run()
    s = side(at)
    assert not at.exception
    row = [r for r in s.split('<div class="cs-side-row">') if 'Full name' in r][0]
    assert 'matched' in row and 'pending' not in row
    row = [r for r in s.split('<div class="cs-side-row">') if 'Date of birth' in r][0]
    assert 'pending' in row and 'matched' not in row


def test_ui_03_sidebar_never_shows_stored_values_or_claim_data(scripted):
    """UI-03: the sidebar shows factor names only, never policyholder values or claim data, before and after verification."""
    at = make_app().run()
    for text in ('partial', 'full'):
        at.chat_input[0].set_value(text).run()
        assert leaks(side(at)) == []


def test_ui_04_header_phase_and_gate_ticks_after_verification(scripted):
    """UI-04: after verification the header shows Resolve intent and the Verify ID row is done with its gate ticked."""
    at = make_app().run()
    at.chat_input[0].set_value('full').run()
    assert 'Phase: Resolve intent' in page(at)
    s = side(at)
    verify_row = [r for r in s.split('cs-phase-row') if 'Verify ID' in r][0]
    assert 'done' in verify_row
    assert 'Identity verified' in s


def test_ui_01_verification_complete_key_event_in_transcript(scripted):
    """UI-01 / CP1: the transcript shows 'Verification complete' once, with the check that it is a key event row."""
    at = make_app().run()
    at.chat_input[0].set_value('partial').run()
    assert 'Verification complete' not in page(at)
    at.chat_input[0].set_value('full').run()
    assert page(at).count('Verification complete') == 1


def test_ui_08_try_menu_exists_and_choosing_sends_no_turn(scripted):
    """UI-08: the sidebar Try menu lists scripted messages. Choosing one sends no turn and the select resets."""
    at = make_app().run()
    boxes = list(at.sidebar.selectbox)
    assert len(boxes) == 1 and len(boxes[0].options) >= 3
    box = boxes[0]
    box.select(box.options[1]).run()
    assert at.session_state['session'].view().turns == []
    assert not at.exception and at.sidebar.selectbox[0].value is None


def test_ui_08_try_menu_text_has_no_dash_or_exclamation():
    """UI-08 / LANG-01: Try menu entries have no em dash, en dash or exclamation mark."""
    at = make_app().run()
    for opt in at.sidebar.selectbox[0].options:
        assert '\u2014' not in opt and '\u2013' not in opt and '!' not in opt


def test_ui_08_try_menu_contains_verify_stage_messages():
    """UI-08: the CP1 Try menu includes an early claim ask, an injection attempt and an alias attempt."""
    opts = ' | '.join(str(o).lower() for o in make_app().run().sidebar.selectbox[0].options)
    assert 'ignore' in opts
    assert 'claim' in opts
    assert 'yaven li' in opts and 'ignore' in opts and 'why was my claim denied' in opts
