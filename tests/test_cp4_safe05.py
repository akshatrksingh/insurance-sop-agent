"""CP4 SAFE-05: before verification a reply holding a stored value or claim field is replaced. Uses a FakeLLM that tries to leak."""
import json

import pytest

from cp1helpers import FakeLLM, ident, leaks
from cp4helpers import OFF
from insurance_claims.orchestrator import handle_turn, new_session

LEAKS = ['Margaret Chen, your claim CL-2048 is denied.', 'We have margaret@email.com on file.', 'The deadline to appeal was 2026-03-18.',
         'Your date of birth 1985-03-15 is on file.', 'Policy POL-9921 has a pathology report missing.', 'Call you on +16505212836?',
         'Last four 4472 matched.', 'Your claim has an allowed maximum of 1450.00.', 'Ava Lopez has claim CL-3001.',
         'It was denied because the review file did not include the pathology report.']
TURNS = [('hello', {}), (OFF, {'in_scope': False}), ('I am Margaret Chen', ident(full_name='Margaret Chen')), ('what is my claim status?', {}),
         ('thanks', {}), ('my number is 000', ident(phone='000')), ('', {})]


class Leaky(FakeLLM):
    """FakeLLM whose every model-written reply is a leak."""

    def __init__(self, text, **kw):
        super().__init__(**kw)
        self.text = text

    def reply(self, prompt_name, bundle, *a, **k):
        return self.text


@pytest.mark.parametrize('leak', LEAKS)
def test_safe_05_leaking_reply_never_reaches_the_caller_before_verification(leak):
    """SAFE-05: with a model reply holding stored values or claim fields, no unverified turn shows any of them, in the reply or in events."""
    llm = Leaky(leak, extractions={t: e for t, e in TURNS})
    s = new_session()
    for t, _ in TURNS:
        r = handle_turn(s, t, llm)
        assert s.view().phase == 'VERIFY_ID'
        blob = json.dumps([r.reply, [e.text for e in r.events]])
        assert r.reply != leak and not leaks(blob), (t, r.reply)


def test_safe_05_replacement_is_a_safe_pre_verification_reply():
    """SAFE-05: the replacement is a template that states the confirmed count and lists the options, not an empty or error reply."""
    llm = Leaky(LEAKS[0], extractions={'hello': {}})
    r = handle_turn(new_session(), 'hello', llm)
    assert r.reply.strip() and '0 of 3 confirmed' in r.reply and 'full name' in r.reply


def test_safe_05_scan_does_not_replace_clean_replies_after_verification():
    """SAFE-05: the scan is for unverified sessions only; the verified Margaret answer keeps the claim fields."""
    from cp2helpers import S1_EX, S1_TEXT
    r = handle_turn(new_session(), S1_TEXT, FakeLLM(extractions={S1_TEXT: S1_EX}))
    assert 'CL-2048' in r.reply and 'pathology report' in r.reply
