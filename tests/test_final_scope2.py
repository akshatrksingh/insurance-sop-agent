"""Final fix batch: SCOPE-01, SCOPE-02 with a scripted extractor that says out of scope (and sometimes wrongly returns identity values)."""
import pytest

from cp1helpers import Rec
from cp2helpers import S1_EX, S1_TEXT
from cp4helpers import handle_turn, new_session, strikes
from templatecheck import HUMAN_OFFER

OFF = {'in_scope': False}
NULL = {'consent': None, 'wants_human': False}
WRONG_IDS = [{}, {'identity': {'id_last4': '2018'}}, {'identity': {'dob': '2018-06-15', 'phone': '2018', 'full_name': 'Nobody Known'}},
             {'identity': {'email': 'who@example.com', 'policy_number': 'POL-2018', 'id_last4': '1234'}}]
OFF_TEXTS = ['Who won the 2018 world cup?', 'What is the status of the Mars mission?', 'who is the paid agent of the year',
             'best benefits of exercise', 'what is a payment plan for a car', 'who is the best real estate agent in Texas',
             'how much is the paid version of that video game', 'what are the benefits of drinking coffee']
IN_SCOPE = [('my DOB is 1985-03-15', {'dob': '1985-03-15'}), ('4472', {'id_last4': '4472'}), ('last four 4472', {'id_last4': '4472'}),
            ("it's 4472", {'id_last4': '4472'}), ('650 521 2836', {'phone': '650 521 2836'}), ('margaret@email.com', {'email': 'margaret@email.com'}),
            ('my policy is POL-9921', {'policy_number': 'POL-9921'}), ('Margaret Chen', {'full_name': 'Margaret Chen'})]
BENIGN = ['wats the status of my clam', 'status of my application', 'my payment', 'my benefits', 'what is my claim status']


def session(verified, texts, ex_by_text):
    """New session, optionally verified first, with the extractor scripted by text."""
    llm = Rec(extractions={S1_TEXT: S1_EX, 'yes': NULL, **ex_by_text})
    s = new_session()
    if verified:
        handle_turn(s, S1_TEXT, llm)
    return s, llm


@pytest.mark.parametrize('verified', [False, True])
@pytest.mark.parametrize('extra', WRONG_IDS)
@pytest.mark.parametrize('text', OFF_TEXTS[:2])
def test_scope_02_three_strikes_offer_a_human_then_plain_yes_hands_off(text, extra, verified):
    """SCOPE-01, SCOPE-02: strikes 1, 2, 3, the human offer on the third, then a plain yes escalates, with or without wrong extractor identity."""
    s, llm = session(verified, [text], {text: {**OFF, **extra}})
    seen, replies = [], []
    for _ in range(3):
        replies.append(handle_turn(s, text, llm).reply)
        seen.append(strikes(s))
    assert seen == [1, 2, 3], (seen, replies)
    assert 'human representative' in replies[2].lower() and (verified or replies[2] == HUMAN_OFFER)
    assert 'human representative' not in replies[0].lower()
    handle_turn(s, 'yes', llm)
    assert s.view().phase == 'ESCALATED'
    if not verified:
        assert not any(g['done'] for p in s.view().model_dump()['phases'] for g in p['gates'])


@pytest.mark.parametrize('text', OFF_TEXTS)
def test_scope_01_ambiguous_word_off_topic_messages_earn_a_strike(text):
    """SCOPE-01: clearly off-topic phrasings with agent, paid, payment, benefits or status each earn one strike and a decline."""
    s, llm = session(False, [text], {text: OFF})
    r = handle_turn(s, text, llm)
    assert strikes(s) == 1 and 'human representative' not in r.reply.lower()


@pytest.mark.parametrize('text,ident', IN_SCOPE)
def test_scope_01_identity_answers_stay_in_scope_even_if_extractor_says_off_topic(text, ident):
    """SCOPE-01: identity answers never earn a strike, whatever the extractor says about scope."""
    s, llm = session(False, [text], {text: {**OFF, 'identity': ident}})
    handle_turn(s, text, llm)
    assert strikes(s) == 0


@pytest.mark.parametrize('text', BENIGN)
def test_scope_01_benign_claim_controls_stay_in_scope(text):
    """SCOPE-01: benign claim phrasings with the extractor wrongly saying off topic earn no strike, before and after verification."""
    for verified in (False, True):
        s, llm = session(verified, [text], {text: OFF})
        handle_turn(s, text, llm)
        assert strikes(s) == 0, (text, verified)
