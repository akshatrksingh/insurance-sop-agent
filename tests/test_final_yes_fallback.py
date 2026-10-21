"""Final pass: plain yes fallback for the human offer (SCOPE-02, S5, POST-02, SAFE-08, CASE-03). Extractor consent is null throughout."""
import pytest

from cp4helpers import OFF, at_offer, say, start, verified_case

YES_FORMS = ['yes', 'Yes', 'yeah', 'yep', 'yes please', 'sure', 'ok', 'okay', 'go ahead', 'please do', 'connect me',
             'yes, please connect me', 'yes please connect me', 'sure, please connect me', 'ok, please connect me',
             'sure please connect me', 'ok please connect me', 'Yes!', 'yes.', 'okay.']
NOT_YES = ['yes but what is my claim', 'yes what is the status', 'no', 'maybe']
NULL = {'consent': None, 'wants_human': False}
SELF_HARM = 'I want to end my life'
CANNOT = "I can't get the pathology report"


def handed_off(s, results):
    """True when the session is ESCALATED and a handoff event was emitted."""
    kinds = [e.kind for r in results for e in r.events] + [e['kind'] for e in s.view().model_dump()['events']]
    return s.view().phase == 'ESCALATED' and any('handoff' in k or 'human' in k for k in kinds)


def after_strikes(extra=None):
    """Fresh session with three off-topic strikes done and the human offered."""
    ex = {**{t: NULL for t in YES_FORMS + NOT_YES}, **(extra or {})}
    s, llm = start(ex)
    say(s, llm, OFF, OFF, OFF)
    return s, llm


@pytest.mark.parametrize('text', YES_FORMS)
def test_scope_02_s5_plain_yes_after_third_strike_hands_off(text):
    """SCOPE-02, S5: a plain yes form with consent null and wants_human false hands off after the human offer."""
    s, llm = after_strikes()
    assert s.view().phase == 'VERIFY_ID'
    results = say(s, llm, text)
    assert handed_off(s, results), (text, s.view().phase)


@pytest.mark.parametrize('text', NOT_YES)
def test_scope_02_non_plain_yes_does_not_hand_off(text):
    """SCOPE-02: a yes with extra content, a no, or maybe does not hand off."""
    s, llm = after_strikes()
    results = say(s, llm, text)
    assert s.view().phase != 'ESCALATED' and not handed_off(s, results), text


def test_scope_02_yes_with_no_pending_question_does_not_hand_off():
    """SCOPE-02: a yes in a fresh session and a yes in PROCESS_CASE with nothing pending hand off nothing."""
    s, llm = start({'yes': NULL})
    say(s, llm, 'yes')
    assert s.view().phase == 'VERIFY_ID'
    s, llm = verified_case({'yes': NULL})
    say(s, llm, 'yes')
    assert s.view().phase != 'ESCALATED'


def test_post_02_yes_while_the_email_question_is_open_sends_nothing_and_no_handoff():
    """POST-02, SCOPE-02: with the email offer open (nothing pending for a human), a null consent yes does not escalate or send."""
    s, llm, _ = at_offer({'yes': NULL, 'sure': NULL})
    for t in ('sure', 'yes'):
        r = say(s, llm, t)[0]
        assert s.view().phase != 'ESCALATED' and r.email_preview is None and s.view().email_preview is None


def test_safe_08_plain_yes_after_the_self_harm_offer_hands_off():
    """SAFE-08: the human offer in the supportive reply is accepted by a plain yes with consent null."""
    s, llm = start({SELF_HARM: {}, 'yes': NULL})
    first = say(s, llm, SELF_HARM)[0]
    assert 'human representative' in first.reply.lower()
    assert handed_off(s, say(s, llm, 'yes'))


def test_case_03_plain_yes_after_the_cannot_obtain_offer_hands_off():
    """CASE-03: the human recommendation for an item the caller cannot get is accepted by a plain yes with consent null."""
    s, llm = verified_case({CANNOT: {}, 'yes': NULL})
    say(s, llm, CANNOT)
    assert handed_off(s, say(s, llm, 'yes'))


def test_scope_02_offer_lapses_after_one_unrelated_turn():
    """SCOPE-02: after the offer, one unrelated turn closes it and a later plain yes no longer hands off."""
    s, llm = after_strikes({'hello again': {}})
    say(s, llm, 'hello again')
    results = say(s, llm, 'yes')
    assert s.view().phase != 'ESCALATED' and not handed_off(s, results)
