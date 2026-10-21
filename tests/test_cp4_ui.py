"""CP4 UI-07, POST-04, SCOPE-02 in the UI: consent buttons, preview card, strike counter, handoff event. Same path as typed consent."""
import html

import pytest

import insurance_claims.tools as tools
from apphelpers import make_app
from conftest import SENTINEL
from cp2helpers import S1_TEXT
from cp4helpers import DONE, EXTRACTIONS, OFF, at_offer, kinds, say
from insurance_claims.orchestrator import handle_choice


@pytest.fixture
def scripted(monkeypatch):
    """Route the app to a FakeLLM scripted with the CP4 extractions."""
    import insurance_claims.llm as llm

    class Scripted(llm.FakeLLM):
        def __init__(self, *a, **k):
            super().__init__(extractions=EXTRACTIONS, replies={})

    monkeypatch.setenv('LLM_API_KEY', SENTINEL)
    monkeypatch.setattr(llm, 'OpenAICompatLLM', Scripted)


def labels(at):
    """Button labels on the page."""
    return [b.label for b in at.button]


def press(at, label):
    """Click the button with this label and rerun."""
    [b for b in at.button if b.label == label][0].click().run()


def page(at):
    """Main column markdown joined."""
    return '\n'.join(m.value for m in at.main.markdown)


def offer_page():
    """AppTest at the open email offer."""
    at = make_app().run()
    at.chat_input[0].set_value(S1_TEXT).run()
    at.chat_input[0].set_value(DONE).run()
    return at


def test_ui_07_buttons_appear_only_while_the_offer_is_open(scripted):
    """UI-07: Send summary and Skip show with the open offer, not before it and not after the choice."""
    at = make_app().run()
    at.chat_input[0].set_value(S1_TEXT).run()
    assert 'Send summary' not in labels(at) and 'Skip' not in labels(at)
    at.chat_input[0].set_value(DONE).run()
    assert 'Send summary' in labels(at) and 'Skip' in labels(at) and not at.exception
    press(at, 'Skip')
    assert 'Send summary' not in labels(at) and 'Skip' not in labels(at)


def test_ui_07_send_summary_button_shows_the_exact_preview_card(scripted):
    """UI-07 / POST-04: Send summary sends once and the card shows the recipient, subject and body of the returned preview, labelled as mock."""
    at = offer_page()
    press(at, 'Send summary')
    view = at.session_state['session'].view()
    p = view.email_preview
    text = page(at)
    assert view.phase == 'COMPLETE' and 'Mock email to margaret@email.com' in text and 'Nothing was delivered' in text
    assert html.escape(p.subject) in text and html.escape(p.body).replace('\n', '<br>') in text
    assert not at.exception


def test_ui_07_skip_button_sends_nothing_and_shows_no_card(scripted, monkeypatch):
    """UI-07 / S7: Skip completes the call with no send and no preview card."""
    calls = []
    monkeypatch.setattr(tools, 'send_email', lambda *a: calls.append(a))
    at = offer_page()
    press(at, 'Skip')
    assert not calls and at.session_state['session'].view().email_preview is None
    assert 'Mock email to' not in page(at)
    assert at.session_state['session'].view().phase == 'COMPLETE'


@pytest.mark.parametrize('typed,label', [('yes', 'Send summary'), ('skip', 'Skip')])
def test_ui_07_button_and_typed_consent_end_in_the_same_state(scripted, typed, label):
    """UI-07: a button press and the typed answer leave the same phase, event kinds, preview and last agent reply."""
    a, b = offer_page(), offer_page()
    a.chat_input[0].set_value(typed).run()
    press(b, label)
    va, vb = (x.session_state['session'].view() for x in (a, b))
    assert va.phase == vb.phase == 'COMPLETE' and va.email_preview == vb.email_preview
    assert [e.kind for e in va.events] == [e.kind for e in vb.events]
    assert va.turns[-1] == vb.turns[-1]


@pytest.mark.parametrize('choice,typed', [('yes', 'yes'), ('no', 'no')])
def test_ui_07_handle_choice_matches_typed_consent(choice, typed):
    """UI-07: handle_choice returns the same reply, event kinds and preview as the typed word, and leaves the same view."""
    (sa, la, _), (sb, lb, _) = at_offer(), at_offer()
    ra, rb = handle_choice(sa, choice), say(sb, lb, typed)[0]
    assert (ra.reply, kinds(ra), ra.email_preview) == (rb.reply, kinds(rb), rb.email_preview)
    assert sa.view().phase == sb.view().phase and sa.view().email_preview == sb.view().email_preview


def test_ui_07_handle_choice_with_no_open_offer_sends_nothing(monkeypatch):
    """UI-07 / POST-02: handle_choice('yes') with no offer open (verification, or mid case) sends nothing and changes no phase."""
    calls = []
    monkeypatch.setattr(tools, 'send_email', lambda *a: calls.append(a))
    from cp4helpers import start, verified_case
    for s, phase in (start()[0], 'VERIFY_ID'), (verified_case()[0], 'PROCESS_CASE'):
        r = handle_choice(s, 'yes')
        assert r.email_preview is None and s.view().phase == phase
    assert not calls


def test_ui_strike_counter_and_handoff_event_are_rendered(scripted):
    """SCOPE-02 UI: the sidebar shows the strike count and the third off-topic message shows the human offer event inline."""
    at = make_app().run()
    at.chat_input[0].set_value(OFF).run()
    assert 'Off-topic strikes' in '\n'.join(m.value for m in at.sidebar.markdown)
    for _ in range(2):
        at.chat_input[0].set_value(OFF).run()
    assert 'Human representative offered' in page(at) and not at.exception
    at.chat_input[0].set_value('human').run()
    assert 'Handed off to a human representative' in page(at)
