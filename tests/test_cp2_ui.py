"""CP2 UI-05 (Show details toggle), Case found key event, memory rows, injection routing regression."""
import pytest

from apphelpers import make_app
from conftest import SENTINEL
from cp1helpers import leaks
from cp2helpers import HINTS, S1_EX, S1_TEXT

SPLIT1 = 'hello I am Margaret Chen about my denied healthcare claim from January'
EXTRACTIONS = {S1_TEXT: S1_EX, SPLIT1: {'identity': {'full_name': 'Margaret Chen'}, 'hints': HINTS}, 'dob': {'identity': {'dob': '1985-03-15'}},
               'ssn': {'identity': {'id_last4': '4472'}}}


@pytest.fixture
def scripted(monkeypatch):
    """Route the app to a FakeLLM scripted for the Margaret messages."""
    import insurance_claims.llm as llm

    class Scripted(llm.FakeLLM):
        def __init__(self, *a, **k):
            super().__init__(extractions=EXTRACTIONS, replies={})

    monkeypatch.setenv('LLM_API_KEY', SENTINEL)
    monkeypatch.setattr(llm, 'OpenAICompatLLM', Scripted)


def page(at):
    """Join the main column markdown values."""
    return '\n'.join(m.value for m in at.main.markdown)


def side(at):
    """Join the sidebar markdown values."""
    return '\n'.join(m.value for m in at.sidebar.markdown)


def reply_of(at):
    """Text of the last agent reply in the session."""
    return at.session_state['session'].view().turns[-1][1]


def toggle(at):
    """The Show details toggle."""
    found = [t for t in at.sidebar.toggle if t.label == 'Show details']
    assert len(found) == 1
    return found[0]


def test_ui_05_toggle_exists_and_defaults_off(scripted):
    """UI-05: a Show details toggle is present and off by default."""
    at = make_app().run()
    assert toggle(at).value is False and not at.exception


def test_ui_05_off_hides_detail_events_and_extractor_fields(scripted):
    """UI-05: with the toggle off no detail event rows and no extractor field list are rendered, key events still are."""
    at = make_app().run()
    at.chat_input[0].set_value(S1_TEXT).run()
    p, s = page(at), side(at)
    assert 'cs-event detail' not in p and 'Tool called' not in p and 'Stored:' not in p
    assert 'Extractor fields' not in s and 'identity.full_name' not in s
    assert 'Verification complete' in p and 'Case found: CL-2048' in p


def test_ui_05_on_shows_tool_calls_memory_stored_and_extractor_field_names(scripted):
    """UI-05: with the toggle on, detail rows (memory stored, tool calls) appear inline and the sidebar lists extractor field names."""
    at = make_app().run()
    at.chat_input[0].set_value(S1_TEXT).run()
    toggle(at).set_value(True).run()
    p, s = page(at), side(at)
    for text in ('Stored: case_type, status, month', 'Tool called: get_claims', 'Tool called: get_claim CL-2048', 'Matched: Full name, Date of birth, ID last 4'):
        assert text in p, text
    assert p.count('cs-event detail') >= 4
    assert 'Extractor fields' in s
    for name in ('identity.full_name', 'identity.dob', 'identity.id_last4', 'hints.case_type', 'hints.status', 'hints.month'):
        assert name in s, name
    assert not at.exception


def test_ui_05_extractor_list_shows_field_names_never_values(scripted):
    """UI-05 / UI-03: the sidebar extractor list holds names only, so no stored value or claim datum appears with the toggle on."""
    at = make_app().run()
    at.chat_input[0].set_value(S1_TEXT).run()
    toggle(at).set_value(True).run()
    block = s = side(at).split('Extractor fields')[1].split('cs-side-title')[0]
    for v in ('Margaret', '1985-03-15', '4472', 'POL-9921', 'healthcare', 'denied', 'january'):
        assert v not in block, v
    assert leaks(s.split('<div class="cs-side-title">')[0]) == []


def test_ui_05_toggle_does_not_change_agent_reply_or_state(scripted):
    """UI-05: flipping the toggle leaves the transcript reply and the session phase unchanged."""
    at = make_app().run()
    at.chat_input[0].set_value(S1_TEXT).run()
    before = at.session_state['session'].view().model_dump()
    toggle(at).set_value(True).run()
    after = at.session_state['session'].view().model_dump()
    assert before['turns'] == after['turns'] and before['phase'] == after['phase'] == 'PROCESS_CASE'
    assert page(at).count(reply_of(at)) == 1


def test_ui_05_detail_events_come_before_the_agent_reply_in_order(scripted):
    """UI-05: inside the turn the detail rows appear inline between the caller message and the agent reply."""
    at = make_app().run()
    at.chat_input[0].set_value(S1_TEXT).run()
    toggle(at).set_value(True).run()
    p = page(at)
    assert p.index('Stored: case_type') < p.index('Verification complete') < p.index('Case found: CL-2048') < p.index(reply_of(at)[:30])


def test_s1_demo_through_the_ui_shows_case_found_and_resolved_case_in_memory(scripted):
    """S1 / UI-05: the one-message demo shows Phase: Process case, the Case found event, and memory rows for hints, intent and resolved case."""
    at = make_app().run()
    at.chat_input[0].set_value(S1_TEXT).run()
    p, s = page(at), side(at)
    assert 'Phase: Process case' in p and p.count('Case found: CL-2048') == 1 and reply_of(at) in p
    for label, value in (('Claim type', 'healthcare'), ('Status', 'denied'), ('Month', 'january'), ('Intent', 'denial question'), ('Resolved case', 'CL-2048')):
        row = [r for r in s.split('<div class="cs-side-row">') if f'<span>{label}</span>' in r][0]
        assert value in row, label


def test_s1b_demo_through_the_ui_split_across_turns(scripted):
    """S1b / MEM-02: turn 1 keeps Phase: Verify ID with hint rows shown and no Case found, turn 3 resolves."""
    at = make_app().run()
    at.chat_input[0].set_value(SPLIT1).run()
    p, s = page(at), side(at)
    assert 'Phase: Verify ID' in p and 'Case found' not in p and 'CL-2048' not in p
    assert '<span>Claim type</span><span class="cs-tone-">healthcare</span>' in s and 'Resolved case' not in s
    for t in ('dob', 'ssn'):
        at.chat_input[0].set_value(t).run()
    p = page(at)
    assert 'Phase: Process case' in p and p.count('Case found: CL-2048') == 1 and 'pathology report' in p
    assert not at.exception


def test_ui_05_reset_clears_events_and_memory_rows(scripted):
    """MEM-04 / UI-05: Reset empties the transcript, hint rows and extractor list."""
    at = make_app().run()
    at.chat_input[0].set_value(S1_TEXT).run()
    toggle(at).set_value(True).run()
    [b for b in at.button if b.label == 'Reset'][0].click().run()
    assert 'Case found' not in page(at) and 'Resolved case' not in side(at) and 'identity.full_name' not in side(at)
