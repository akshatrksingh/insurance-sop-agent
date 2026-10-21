"""CP5 regressions: human offer lifetime (EMO-03, VER-07), email offer pending state (POST-02), button consent (POST-02), refusal then verify (EMO-03)."""
import pytest

import insurance_claims.tools as tools
from cp1helpers import ident, play
from cp2helpers import S1_EX, S1_TEXT
from cp4helpers import DONE, OFF, all_kinds, say, start
from insurance_claims.orchestrator import handle_choice

M = 'Margaret Chen'
HUMAN_REPLY = 'I am connecting you with a human representative now. They will take it from here.'
REASK = 'I did not catch a clear answer. Should I send the summary to the email on file, or skip it?'
VERIFIED = ident(full_name=M, dob='1985-03-15', id_last4='4472')


@pytest.fixture
def sent(monkeypatch):
    """Record every call to the mock send tool and delegate to it."""
    calls, real = [], tools.send_email
    monkeypatch.setattr(tools, 'send_email', lambda to, subject, body: (calls.append(to), real(to, subject, body))[1])
    return calls


def failed(i):
    """Margaret's name with a wrong dob."""
    return (f'f{i}', ident(full_name=M, dob=f'1990-01-0{i}'))


def test_ver_07_emo_03_yes_right_after_offer_escalates():
    """VER-07 / EMO-03: the third failed round gets the human offer and a consent yes on the next turn escalates."""
    s, _, rs = play([failed(1), failed(2), failed(3), ('y', {'consent': 'yes'})])
    assert 'human representative' in rs[2].reply and s.view().phase == 'ESCALATED'


@pytest.mark.parametrize('later', ['yes', 'no'])
def test_ver_07_emo_03_human_offer_is_valid_for_one_turn_in_verify(later):
    """VER-07 / EMO-03: after one unrelated turn the offer has lapsed; a later yes does not escalate, a later no gives no human decline reply."""
    s, _, rs = play([failed(1), failed(2), failed(3), ('unrel', {}), ('later', {'consent': later})])
    assert 'human representative' in rs[2].reply
    assert s.view().phase == 'VERIFY_ID' and not s.escalated and not s.human_offered and s.pending_question is None
    assert HUMAN_REPLY not in rs[4].reply and 'Understood' not in rs[4].reply


@pytest.mark.parametrize('later', ['yes', 'no'])
def test_emo_03_human_offer_lapses_after_one_turn_with_case_answer_kept(later, sent):
    """EMO-03: offer from three off-topic turns after the case answer; an unrelated turn lapses it; a later consent does not escalate, drop the answer, or send."""
    s, llm = start({'unrel': {}, 'later': {'consent': later}})
    say(s, llm, S1_TEXT, OFF, OFF, OFF)
    assert s.human_offered
    rs = say(s, llm, 'unrel', 'later')
    assert not s.escalated and not s.human_offered and s.gates.case_answered and s.view().phase == 'PROCESS_CASE'
    assert HUMAN_REPLY not in rs[1].reply and not sent and 'email_sent' not in all_kinds(s)


def test_post_02_emo_03_email_offer_survives_off_topic_strikes(sent):
    """POST-02 / EMO-03: email offer, three off-topic turns (human offer on the third), then an in-scope null turn: pending is email, re-ask, human_offered false."""
    s, llm = start({'inscope': {}})
    rs = say(s, llm, S1_TEXT, DONE, OFF, OFF, OFF)
    assert 'human representative' in rs[4].reply and s.human_offered
    r = say(s, llm, 'inscope')[0]
    assert s.pending_question == 'email' and not s.human_offered and r.reply == REASK
    assert not sent and r.email_preview is None and s.view().email_offer_open


@pytest.mark.parametrize('choice,sends', [('yes', True), ('no', False)])
def test_post_02_button_answers_email_offer_and_clears_human_offer(choice, sends, sent):
    """POST-02: with the human offer open on the email offer, the button is the email answer; afterwards a typed yes does not escalate."""
    s, llm = start({'typed': {'consent': 'yes'}})
    say(s, llm, S1_TEXT, DONE, OFF, OFF, OFF)
    assert s.human_offered
    r = handle_choice(s, choice)
    assert bool(sent) is sends and (r.email_preview is not None) is sends
    assert s.gates.email_choice_made and not s.human_offered and s.pending_question is None and not s.escalated
    say(s, llm, 'typed')
    assert not s.escalated and s.view().phase == 'COMPLETE'


def test_emo_03_refusal_rounds_then_verifying_identity_is_not_a_handoff():
    """EMO-03: two refusals, then a third refusal turn that carries full verifying identity: verified, count 2, not escalated."""
    r = {'refused_verification': True}
    s, _, rs = play([('r1', r), ('r2', r), ('r3', {**r, **S1_EX})])
    assert s.view().phase == 'PROCESS_CASE' and s.resistance_count == 2 and not s.escalated


def test_emo_03_refusal_turn_with_wants_human_still_escalates():
    """EMO-03: wants_human on that third turn escalates despite the verifying identity."""
    r = {'refused_verification': True}
    s, _, rs = play([('r1', r), ('r2', r), ('r3', {**r, **S1_EX, 'wants_human': True})])
    assert s.escalated and s.view().phase == 'ESCALATED'
