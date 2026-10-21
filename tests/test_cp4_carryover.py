"""CP4 carryover (CASE-01): negative outcome and action phrases are ungrounded; field matching uses whole words."""
import pytest

from insurance_claims.fields import asked_field
from insurance_claims.grounding import ungrounded
from test_cp2_grounding import BUNDLE

FLAGGED = ['will not be approved', 'cannot be reopened', "won't be paid", 'is likely to be approved', 'cannot file', 'will not be paid',
           "can't be reopened", 'wont be approved', 'is unlikely to be approved', 'is not going to be approved', 'Claims cannot be filed late',
           'will be approved', 'can be reopened']
HONEST = ['It has not passed.', 'It was denied because x', 'I cannot file appeals.', "We can't reopen it"]


@pytest.mark.parametrize('phrase', FLAGGED)
def test_case_01_outcome_and_action_phrase_is_flagged_bare(phrase):
    """CASE-01: positive and negative outcome or action phrases are ungrounded."""
    assert ungrounded(phrase, BUNDLE) is True


@pytest.mark.parametrize('phrase', FLAGGED)
def test_case_01_outcome_and_action_phrase_is_flagged_in_sentence(phrase):
    """CASE-01: the same phrases are ungrounded inside a short sentence."""
    assert ungrounded(f'Your claim {phrase} today.', BUNDLE) is True


@pytest.mark.parametrize('text', HONEST)
def test_case_01_honest_statements_are_not_flagged(text):
    """CASE-01: honest or grounded statements are not flagged."""
    assert ungrounded(text, BUNDLE) is False


EXPECTED = [('Am I allowed to appeal?', None), ('Can you file it before the deadline?', None), ('Please submit my appeal', None),
            ('What is the deadline?', 'deadline'), ('Is it before the deadline?', 'deadline'), ('What is my net pay?', 'net_pay'),
            ('Could you tell me the net pay?', 'net_pay'), ('What is the allowed maximum?', 'allowed'), ('How much is the maximum?', 'allowed'),
            ('Why was it denied?', 'reason'), ('what documents do I need', 'documents'), ('What is the status?', 'status'),
            ('What is the deadline and the status?', None), ('What is the status? What is the deadline?', None),
            ('What is the statuses?', None), ('What is the reasoning?', None), ('What are the documentation rules?', None),
            ('Unallowed things?', None), ('What is the netpay?', None)]


@pytest.mark.parametrize('question,field', EXPECTED)
def test_case_01_asked_field_matches_whole_words_only(question, field):
    """CASE-01: asked_field resolves whole words and phrases, and returns None for substrings, multi-field and two-question messages."""
    assert asked_field(question) == field
