"""CP5 emotion-only messages never earn an off-topic strike (EMO-02, SCOPE-01). FakeLLM scripted extractions."""

import insurance_claims.tools as tools
from cp1helpers import matched, play
from cp2helpers import S1_TEXT
from cp4helpers import DONE, say, start
from templatecheck import EMPATHY, check_reply, split_empathy

ANGER = {'emotion': {'label': 'anger', 'intensity': 2}, 'in_scope': False}
MILD = {'emotion': {'label': 'frustration', 'intensity': 1}, 'in_scope': False}
ASK = 'What would you like to know about your claim?'
USELESS = 'you people are useless'
SHORT = 'That sounds stressful, and I will keep this short. ' + ASK
EXTRA = {USELESS: ANGER, 'mild': MILD, 'this is ridiculous, what is RL?': ANGER, 'What is RL?': {'in_scope': False}}


def state(s):
    """Phase, strikes, resistance rounds, escalated."""
    return s.view().phase, s.off_topic_strikes, s.resistance_count, s.escalated


def case_session():
    """Margaret verified with the case answered."""
    s, llm = start(EXTRA)
    say(s, llm, S1_TEXT)
    return s, llm


def test_emo_02_scope_01_emotion_only_after_case_is_redirected_without_strike():
    """EMO-02 / SCOPE-01: anger 2 out-of-scope with no question gets the fixed line and no strike or resistance."""
    s, llm = case_session()
    r = say(s, llm, USELESS)[0]
    assert r.reply == SHORT and state(s) == ('PROCESS_CASE', 0, 0, False)


def test_emo_02_scope_01_mild_emotion_gets_empathy_and_redirect_without_strike():
    """EMO-02 / SCOPE-01: frustration 1 gets an empathy line, the redirect, and no strike."""
    s, llm = case_session()
    r = say(s, llm, USELESS, 'mild')[1]
    line, rest = split_empathy(r.reply)
    assert line in EMPATHY and r.reply.endswith(ASK) and state(s)[1] == 0


def test_emo_02_scope_01_emotion_plus_question_still_earns_strike():
    """EMO-02 / SCOPE-01: empathy first, then the off-topic decline, and one strike when the message asks something."""
    s, llm = case_session()
    r = say(s, llm, 'this is ridiculous, what is RL?')[0]
    line, rest = split_empathy(r.reply)
    assert line in EMPATHY and 'cannot answer that' in rest and state(s)[1] == 1


def test_emo_02_scope_01_unverified_emotion_only_gets_general_template_and_resistance():
    """EMO-02 / SCOPE-01: before verification: empathy plus a general template, no strike, resistance 1, no claim data."""
    s, _, rs = play([(USELESS, ANGER)])
    assert check_reply(rs[0].reply, matched(s), 'anger', 2, ['general']) == []
    assert rs[0].reply.split('.')[0] in [e.split('.')[0] for e in EMPATHY]
    assert state(s) == ('VERIFY_ID', 0, 1, False) and 'CL-' not in rs[0].reply


def test_emo_02_scope_01_email_offer_open_gets_redirect_and_sends_nothing(monkeypatch):
    """EMO-02 / SCOPE-01: at the open email offer the message gets the email redirect; choice stays open, nothing sent."""
    calls = []
    monkeypatch.setattr(tools, 'send_email', lambda *a: calls.append(a))
    s, llm = start(EXTRA)
    say(s, llm, S1_TEXT, DONE)
    r = say(s, llm, USELESS)[0]
    assert r.reply.endswith('For now, should I send the summary to the email on file, or skip it?')
    assert s.view().email_offer_open and not s.gates.email_choice_made and not calls and r.email_preview is None
    assert state(s)[1] == 0


def test_emo_02_scope_01_neutral_out_of_scope_still_earns_strike():
    """SCOPE-01: a neutral out-of-scope message still earns a strike."""
    s, llm = case_session()
    say(s, llm, 'What is RL?')
    assert state(s)[1] == 1


def test_emo_02_scope_01_three_emotion_only_messages_hand_off_on_resistance():
    """EMO-02 / SCOPE-01: three anger 2 emotion-only messages before verification escalate on the third resistance round, with 0 strikes."""
    extra = {'u2': ANGER, 'u3': ANGER, USELESS: ANGER}
    s, llm = start(extra)
    say(s, llm, USELESS, 'u2')
    assert state(s) == ('VERIFY_ID', 0, 2, False)
    say(s, llm, 'u3')
    assert state(s) == ('ESCALATED', 0, 3, True)
