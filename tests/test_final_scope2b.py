"""Final fix batch 2: SCOPE-01, SCOPE-02 allowlist tightening. Off-topic text with numbers or dates still earns strikes; real identity stays in scope."""
import pytest

from cp4helpers import handle_turn, strikes
from templatecheck import HUMAN_OFFER
from test_final_scope2 import session

OFF = {'in_scope': False}
OFF_TEXTS = ['What happened in March 2020?', 'Write a poem about december 2024', 'Give me a recipe using apricot 3 cups',
             'Explain marketing 101', 'Explain the years 1990 - 2000', 'What is 123 456 789 0', 'What is the status of my pizza order?',
             'Who is the best secret agent in my opinion?', 'I paid for my flight to Paris, what is the capital?', 'what is the status of the war']
WRONG_ID = [('Tell me what happened on 1 Jan 2024', {'dob': '2024-01-01'}), ('what is 1990 divided by 1', {'dob': '1990-01-01'}),
            ('Who is Tom Cruise?', {'full_name': 'Tom Cruise'}), ('tell me a joke', {'full_name': 'a'}), ('tell me a joke', {'policy_number': 'a'})]
IN_SCOPE = [('My name is Margaret Chen', {'full_name': 'Margaret Chen'}), ('Margaret Chen', {'full_name': 'Margaret Chen'}),
            ('my DOB is 1985-03-15', {'dob': '1985-03-15'}), ('March 15 1985', {'dob': '1985-03-15'}), ('15 March 1985', {'dob': '1985-03-15'}),
            ('4472', {'id_last4': '4472'}), ('last four 4472', {'id_last4': '4472'}), ('650 521 2836', {'phone': '+16505212836'}),
            ('margaret@email.com', {'email': 'margaret@email.com'}), ('my policy is POL-9921', {'policy_number': 'POL-9921'}),
            ('Hi, my name is Margaret Chen and my date of birth is March 15 1985', {'full_name': 'Margaret Chen', 'dob': '1985-03-15'})]
BENIGN = ['wats the status of my clam', 'status of my application', 'my payment', 'my benefits', 'what is my claim status']


def three_strikes(verified, text, ex):
    """Send text three times with the extractor out of scope and return (strike counts, replies, session, llm)."""
    s, llm = session(verified, [text], {text: {**OFF, **ex}})
    seen, replies = [], []
    for _ in range(3):
        replies.append(handle_turn(s, text, llm).reply)
        seen.append(strikes(s))
    return seen, replies, s, llm


@pytest.mark.parametrize('verified', [False, True])
@pytest.mark.parametrize('text', OFF_TEXTS)
def test_scope_02_numbers_and_dates_in_off_topic_text_still_earn_three_strikes(text, verified):
    """SCOPE-01, SCOPE-02: strikes 1, 2, 3, the human offer on the third reply only."""
    seen, replies, s, llm = three_strikes(verified, text, {})
    assert seen == [1, 2, 3], (seen, replies)
    assert 'human representative' in replies[2].lower() and 'human representative' not in replies[0].lower()
    assert (verified or replies[2] == HUMAN_OFFER)


@pytest.mark.parametrize('verified', [False, True])
@pytest.mark.parametrize('text,ident', WRONG_ID)
def test_scope_02_wrong_extractor_identity_value_does_not_hide_off_topic_text(text, ident, verified):
    """SCOPE-02: an identity value not present in the message never keeps off-topic text in scope."""
    seen, replies, s, llm = three_strikes(verified, text, {'identity': ident})
    assert seen == [1, 2, 3], (seen, replies)
    assert 'human representative' in replies[2].lower()
    handle_turn(s, 'yes', llm)
    assert s.view().phase == 'ESCALATED'


@pytest.mark.parametrize('verified', [False, True])
@pytest.mark.parametrize('text,ident', IN_SCOPE)
def test_scope_01_identity_statements_stay_in_scope_and_get_no_decline(text, ident, verified):
    """SCOPE-01: real identity text earns no strike and its reply is not the off-topic decline, before and after verification."""
    s, llm = session(verified, [text], {text: {**OFF, 'identity': ident}, 'what is RL?': OFF})
    r = handle_turn(s, text, llm).reply
    assert strikes(s) == 0
    ref, rllm = session(verified, [], {'what is RL?': OFF})
    decline = handle_turn(ref, 'what is RL?', rllm).reply
    assert r != decline and r != HUMAN_OFFER


@pytest.mark.parametrize('verified', [False, True])
@pytest.mark.parametrize('text', BENIGN)
def test_scope_01_benign_claim_controls_stay_in_scope_and_get_no_decline(text, verified):
    """SCOPE-01: benign claim phrasings earn no strike and no decline even when the extractor says off topic."""
    s, llm = session(verified, [text], {text: OFF, 'what is RL?': OFF})
    r = handle_turn(s, text, llm).reply
    ref, rllm = session(verified, [], {'what is RL?': OFF})
    assert strikes(s) == 0 and r != handle_turn(ref, 'what is RL?', rllm).reply
