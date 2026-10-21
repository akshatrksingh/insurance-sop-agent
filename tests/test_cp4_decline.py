"""CP4 POST-02: a whole-message plain decline at the open email offer is a no even when the extractor returns consent null."""
import pytest

import insurance_claims.tools as tools
from cp4helpers import DONE, OFF, all_kinds, kinds, say, start, verified_case
from test_cp4_post02_regress import offered_then_strikes

DECLINES = ['no', 'no thanks', 'no thank you', 'skip', 'skip it', 'don' + chr(39) + 't send it', 'do not send it', 'not now', 'I' + chr(39) + 'm good', 'I am good',
            'no need', 'nope', 'no thanks I am good', 'no thank you I am good']
VARIANTS = ['No', 'NO THANKS.', 'Skip it!', 'Don' + chr(39) + 't send it.', 'dont send it', 'I' + chr(0x2019) + 'm good', 'No, thank you.']
NOT_DECLINES = ['no thanks, but what about my deadline', 'no thanks I want to know my deadline', 'skip the deadline and tell me the status']


@pytest.fixture
def sent(monkeypatch):
    """Record every call to the mock send tool and delegate to it."""
    calls, real = [], tools.send_email
    monkeypatch.setattr(tools, 'send_email', lambda to, subject, body: (calls.append(to), real(to, subject, body))[1])
    return calls


def open_offer(text):
    """Session with the email offer open and the extractor returning no consent for text."""
    s, llm = verified_case({text: {}})
    say(s, llm, DONE)
    return s, llm


@pytest.mark.parametrize('text', DECLINES + VARIANTS)
def test_post_02_plain_decline_with_null_consent_skips_and_sends_nothing(text, sent):
    """POST-02: a whole-message plain decline with consent null skips: nothing sent, email_skipped, COMPLETE, no preview."""
    s, llm = open_offer(text)
    r = say(s, llm, text)[0]
    assert not sent and r.email_preview is None and 'email_skipped' in kinds(r) and 'email_sent' not in all_kinds(s)
    assert s.view().phase == 'COMPLETE' and not s.view().email_offer_open and 'Nothing was sent' in r.reply


@pytest.mark.parametrize('text', NOT_DECLINES)
def test_post_02_longer_message_is_not_a_decline_and_reasks(text, sent):
    """POST-02: a longer message that only starts with a decline gets the re-ask, keeps the offer open, sends nothing."""
    s, llm = open_offer(text)
    r = say(s, llm, text)[0]
    assert not sent and r.email_preview is None and s.view().email_offer_open and s.view().phase == 'POST_PROCESS'
    assert 'send' in r.reply and 'skip' in r.reply and 'email_skipped' not in all_kinds(s)


@pytest.mark.parametrize('text', ['maybe', 'yes please', 'yes', 'sure', 'go ahead', 'ok'])
def test_post_02_null_consent_never_sends_and_keeps_the_choice_open(text, sent):
    """POST-02: with consent null no text is a yes. Nothing is sent and the choice stays open (a decline phrase can never produce a yes)."""
    s, llm = open_offer(text)
    r = say(s, llm, text)[0]
    assert not sent and r.email_preview is None and s.view().email_offer_open and 'email_sent' not in all_kinds(s)


def test_post_02_decline_phrase_does_not_skip_while_human_offer_is_pending(sent):
    """POST-02: with the human offer pending, a null-consent 'no thanks' is not a skip; nothing is skipped or sent and the human question stands."""
    s, llm = offered_then_strikes()
    llm.extractions['no thanks'] = {}
    r = say(s, llm, 'no thanks')[0]
    assert not sent and r.email_preview is None and 'email_skipped' not in all_kinds(s)
    assert s.view().phase == 'POST_PROCESS' and s.view().email_offer_open and 'human representative' in r.reply


@pytest.mark.parametrize('text', ['no thanks', 'skip', 'nope'])
def test_post_02_decline_phrase_without_open_offer_changes_nothing(text, sent):
    """POST-02: with no offer open (verification, or mid case) a decline phrase skips nothing and sends nothing."""
    for s, llm in (start({text: {}}), verified_case({text: {}})):
        r = say(s, llm, text)[0]
        assert not sent and r.email_preview is None and 'email_skipped' not in all_kinds(s) and s.view().phase != 'COMPLETE'
    s, llm = start({text: {'in_scope': False}})
    say(s, llm, OFF)
    assert 'email_skipped' not in all_kinds(s)
