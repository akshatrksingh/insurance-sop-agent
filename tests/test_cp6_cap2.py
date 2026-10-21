"""CP6 NFR-08 bypass regression: clearing the visitor token re-applies the cap, MAX_TURNS fallback, Reset restores the cap."""
import pytest

from apphelpers import all_text, make_app
from failhelpers import EXC_FACTORIES

HOSTED = 'hosted_KEY_cp6_aaaa'
CAP = 2


def install(monkeypatch):
    """Route the app to a recording FakeLLM. Returns the list of (constructor args text, call name)."""
    import insurance_claims.llm as llm
    log = []

    class Rec(llm.FakeLLM):
        def __init__(self, *a, **k):
            super().__init__()
            self.who = repr(a) + repr(k)
            log.append((self.who, 'init'))

        def extract(self, *a, **k):
            log.append((self.who, 'extract'))
            if 'bad_visitor' in self.who:
                raise EXC_FACTORIES['openai.AuthenticationError']()
            return super().extract(*a, **k)

        def reply(self, *a, **k):
            log.append((self.who, 'reply'))
            return super().reply(*a, **k)

    monkeypatch.setenv('LLM_API_KEY', HOSTED)
    monkeypatch.setattr(llm, 'OpenAICompatLLM', Rec)
    return log


def calls(log, mark):
    """extract and reply calls recorded after mark. Client construction is not a call."""
    return [x for x in log[mark:] if x[1] != 'init']


def say(at, t):
    """Send one caller message."""
    at.chat_input[0].set_value(t).run()


def at_cap(monkeypatch, cap=CAP):
    """AppTest at the cap with the hosted key. Returns (at, log)."""
    monkeypatch.setenv('MAX_TURNS', str(cap))
    log = install(monkeypatch)
    at = make_app().run()
    for i in range(cap):
        say(at, f'hello {i}')
    return at, log


def turns(at):
    """Caller messages in the transcript."""
    return [t for w, t in at.session_state['session'].view().turns if w == 'Caller']


def test_nfr_08_clearing_visitor_token_reapplies_cap(monkeypatch):
    """NFR-08: after a visitor token lifts the cap, clearing the field caps the next message, with 0 calls and no hosted key use."""
    at, log = at_cap(monkeypatch)
    at.sidebar.text_input[0].set_value('anything_goes_123').run()
    say(at, 'passes')
    assert 'passes' in turns(at)
    at.sidebar.text_input[0].set_value('').run()
    mark = len(log)
    say(at, 'bypass attempt')
    assert 'bypass attempt' not in turns(at)
    assert 'Reset' in all_text(at) and not at.exception
    assert calls(log, mark) == []


def test_nfr_08_visitor_calls_never_use_the_hosted_key(monkeypatch):
    """NFR-08: calls made after the lift use the visitor token, not the hosted key."""
    at, log = at_cap(monkeypatch)
    mark = len(log)
    at.sidebar.text_input[0].set_value('anything_goes_123').run()
    say(at, 'passes')
    after = log[mark:]
    assert after and not any(HOSTED in who for who, _ in after)


def test_nfr_08_invalid_visitor_token_does_not_leave_cap_lifted(monkeypatch):
    """NFR-08: an invalid visitor token at the cap, then cleared, leaves the cap enforced."""
    at, log = at_cap(monkeypatch)
    at.sidebar.text_input[0].set_value('bad_visitor').run()
    say(at, 'try with bad token')
    assert not at.exception
    at.sidebar.text_input[0].set_value('').run()
    mark = len(log)
    say(at, 'after clearing')
    assert 'after clearing' not in turns(at)
    assert calls(log, mark) == []
    assert not at.session_state['session'].cap_lifted


@pytest.mark.parametrize('value', ['0', '-1', '-40'])
def test_nfr_08_nonpositive_max_turns_falls_back_to_40(monkeypatch, value):
    """NFR-08: MAX_TURNS of zero or below falls back to 40 and the cap is still enforced."""
    from insurance_claims.llm import FakeLLM
    from insurance_claims.orchestrator import handle_turn, new_session
    monkeypatch.setenv('MAX_TURNS', value)
    s = new_session()
    results = [handle_turn(s, f'hi {i}', FakeLLM()) for i in range(40)]
    assert not any(r.capped for r in results)
    assert handle_turn(s, 'hi', FakeLLM()).capped


def test_nfr_08_reset_after_lift_restores_the_cap(monkeypatch):
    """NFR-08: Reset after the lift restores the cap, even with the token field cleared first."""
    at, log = at_cap(monkeypatch)
    at.sidebar.text_input[0].set_value('anything_goes_123').run()
    say(at, 'passes')
    at.sidebar.text_input[0].set_value('').run()
    [b for b in at.button if b.label == 'Reset'][0].click().run()
    assert not at.session_state['session'].cap_lifted
    for i in range(CAP):
        say(at, f'new {i}')
    assert len(turns(at)) == CAP
    mark = len(log)
    say(at, 'over again')
    assert 'over again' not in turns(at) and calls(log, mark) == []
