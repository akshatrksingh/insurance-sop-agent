"""CP4 POST-02 regression: a yes after the human offer made during the email offer is a handoff, never a send."""
import pytest

import insurance_claims.tools as tools
from cp2helpers import S1_TEXT
from cp4helpers import DONE, OFF, kinds, say, start

HANDOFF = 'I am connecting you with a human representative now. They will take it from here.'


@pytest.fixture
def sent(monkeypatch):
    """Record every call to the mock send tool and delegate to it."""
    calls, real = [], tools.send_email
    monkeypatch.setattr(tools, 'send_email', lambda to, subject, body: (calls.append((to, subject, body)), real(to, subject, body))[1])
    return calls


def row(s, label):
    """Value of one memory row."""
    return next(r['value'] for r in s.view().model_dump()['memory_rows'] if r['label'] == label)


def gate(s, label):
    """Done flag of one gate."""
    return next(g['done'] for p in s.view().model_dump()['phases'] for g in p['gates'] if g['label'] == label)


def offered_then_strikes():
    """Steps 1 to 4: case answered, email offer open, three out-of-scope turns (human offered on the third)."""
    s, llm = start()
    rs = say(s, llm, S1_TEXT, DONE, OFF, OFF, OFF)
    assert rs[1].events and s.view().email_offer_open and row(s, 'Off-topic strikes') == '3'
    assert 'human representative' in rs[4].reply
    return s, llm


def test_post_02_yes_after_human_offer_hands_off_and_sends_nothing(sent):
    """POST-02: yes after the human offer gives the handoff text, ESCALATED, no preview, consent not true, choice not made, nothing sent."""
    s, llm = offered_then_strikes()
    r = say(s, llm, 'yes')[0]
    assert r.reply == HANDOFF and s.view().phase == 'ESCALATED' and r.email_preview is None and s.view().email_preview is None
    assert row(s, 'Email consent') != 'yes' and gate(s, 'Email choice made') is False and 'handoff' in kinds(r)
    assert 'email_sent' not in kinds(r) and not sent and not s.view().email_offer_open
    assert say(s, llm, 'yes')[0].email_preview is None and not sent


def test_post_02_no_after_human_offer_reasks_then_yes_sends(sent):
    """POST-02: no after the human offer re-asks the email question, choice stays unmade, and a later yes sends once with the preview."""
    s, llm = offered_then_strikes()
    r = say(s, llm, 'no')[0]
    assert 'send the summary' in r.reply and 'skip' in r.reply and r.email_preview is None
    assert gate(s, 'Email choice made') is False and s.view().phase == 'POST_PROCESS' and s.view().email_offer_open and not sent
    r = say(s, llm, 'yes')[0]
    p = r.email_preview
    assert p is not None and p.to == 'margaret@email.com' and sent == [(p.to, p.subject, p.body)]
    assert s.view().phase == 'COMPLETE' and 'email_sent' in kinds(r)


def test_post_02_yes_while_offer_open_without_human_offer_sends_and_does_not_escalate(sent):
    """POST-02: with the offer open and no human offer, yes sends the email and the call completes, not escalated."""
    s, llm = start()
    r = say(s, llm, S1_TEXT, DONE, 'yes')[2]
    assert r.email_preview is not None and len(sent) == 1 and s.view().phase == 'COMPLETE'
    assert 'handoff' not in kinds(r) and gate(s, 'Email choice made') is True


def test_post_02_yes_after_one_or_two_strikes_in_offer_still_sends(sent):
    """POST-02: below the strike limit a yes while the offer is open is consent."""
    s, llm = start()
    say(s, llm, S1_TEXT, DONE, OFF, OFF)
    r = say(s, llm, 'yes')[0]
    assert r.email_preview is not None and len(sent) == 1 and s.view().phase == 'COMPLETE'
