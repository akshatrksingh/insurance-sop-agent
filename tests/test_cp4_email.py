"""CP4 POST-01, POST-02, S6, S7: the email offer, explicit consent, skip, ambiguity, nothing sent without a yes."""
import pytest

import insurance_claims.tools as tools
from cp4helpers import DONE, OFF, all_kinds, at_offer, kinds, say, start, verified_case


@pytest.fixture
def sent(monkeypatch):
    """Record every call to the mock send tool and delegate to it."""
    calls, real = [], tools.send_email
    monkeypatch.setattr(tools, 'send_email', lambda to, subject, body: (calls.append((to, subject, body)), real(to, subject, body))[1])
    return calls


def test_post_01_offer_comes_after_case_answered_and_caller_done(sent):
    """POST-01: the case answer alone does not offer an email; the offer follows when the caller is done, once, with an email_offer event."""
    s, llm = verified_case()
    assert s.view().phase == 'PROCESS_CASE' and not s.view().email_offer_open and 'email_offer' not in all_kinds(s)
    r = say(s, llm, 'deadline?')[0]
    assert 'email_offer' not in kinds(r) and not s.view().email_offer_open
    r = say(s, llm, DONE)[0]
    assert 'email_offer' in kinds(r) and s.view().phase == 'POST_PROCESS' and s.view().email_offer_open
    assert 'summary' in r.reply and 'email on file' in r.reply and not sent


def test_post_01_offer_is_not_made_before_verification(sent):
    """POST-01: a caller who is done before verifying gets no email offer and nothing is sent."""
    s, llm = start()
    say(s, llm, DONE, 'yes')
    assert 'email_offer' not in all_kinds(s) and not s.view().email_offer_open and not sent


def test_post_02_s6_yes_sends_once_to_the_email_on_file(sent):
    """POST-02 / S6: an explicit yes after the offer sends exactly one mock email to the address on file and completes the call."""
    s, llm, _ = at_offer()
    r = say(s, llm, 'yes')[0]
    assert [c[0] for c in sent] == ['margaret@email.com'] and r.email_preview is not None
    assert 'email_sent' in kinds(r) and s.view().phase == 'COMPLETE' and not s.view().email_offer_open


@pytest.mark.parametrize('word', ['no', 'skip'])
def test_post_02_s7_no_or_skip_sends_nothing_and_ends_cleanly(word, sent):
    """POST-02 / S7: no or skip sends nothing, records email_skipped, completes the call, and later turns do not send."""
    s, llm, _ = at_offer()
    r = say(s, llm, word)[0]
    assert not sent and r.email_preview is None and 'email_skipped' in kinds(r) and 'email_sent' not in all_kinds(s)
    assert s.view().phase == 'COMPLETE' and 'Nothing was sent' in r.reply
    later = say(s, llm, 'yes', 'send it')
    assert not sent and all(x.email_preview is None for x in later) and s.view().phase == 'COMPLETE'


@pytest.mark.parametrize('text', ['maybe', 'hmm'])
def test_post_02_ambiguous_answer_reasks_and_sends_nothing(text, sent):
    """POST-02: an unclear answer re-asks send or skip, keeps the offer open, and sends nothing."""
    s, llm, _ = at_offer()
    r = say(s, llm, text)[0]
    assert 'send' in r.reply and 'skip' in r.reply and s.view().email_offer_open and not sent and r.email_preview is None
    assert say(s, llm, 'yes')[0].email_preview is not None and len(sent) == 1


def test_post_02_off_topic_while_offer_open_reasks_and_sends_nothing(sent):
    """POST-02: an off-topic message while the offer is open does not count as consent."""
    s, llm, _ = at_offer()
    r = say(s, llm, OFF)[0]
    assert not sent and s.view().email_offer_open and 'skip' in r.reply


def test_post_02_yes_before_any_offer_sends_nothing(sent):
    """POST-02: a yes while no offer is open (verification, case, after the case answer) sends nothing."""
    s, llm = start()
    say(s, llm, 'yes')
    assert not sent and s.view().phase == 'VERIFY_ID'
    s, llm = verified_case()
    r = say(s, llm, 'yes', 'send it')[1]
    assert not sent and r.email_preview is None and 'email_sent' not in all_kinds(s)


def test_post_02_consent_in_the_same_turn_as_done_does_not_send(sent):
    """POST-02: a consent value on the same turn as the offer is not a yes to the offer; the offer is only made."""
    s, llm = verified_case({DONE: {'wants_to_end': True, 'consent': 'yes'}})
    r = say(s, llm, DONE)[0]
    assert not sent and r.email_preview is None and s.view().email_offer_open


def test_post_02_no_second_send_after_yes(sent):
    """POST-02: after a send, further yes turns and button choices send nothing more."""
    from insurance_claims.orchestrator import handle_choice
    s, llm, _ = at_offer()
    say(s, llm, 'yes', 'yes', 'send it')
    handle_choice(s, 'yes')
    assert len(sent) == 1


def test_post_02_hints_in_text_cannot_redirect_the_email(sent):
    """POST-02 / POST-03: an email address stated by the caller after the offer never changes the recipient."""
    s, llm, _ = at_offer({'send to evil@x.com': {'identity': {'email': 'evil@x.com'}, 'consent': 'yes'}})
    r = say(s, llm, 'send to evil@x.com')[0]
    assert all(c[0] == 'margaret@email.com' for c in sent) and 'evil@x.com' not in str(r.email_preview)
