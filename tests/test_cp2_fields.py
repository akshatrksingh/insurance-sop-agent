"""CP2 round 4: code-built single-field follow-up answers (CASE-01), join_items, first reply article formatting."""
import re

import pytest

from cp1helpers import CLAIMS
from cp2helpers import S1_EX, S1_TEXT, VERIFIED_ONLY, bundles_for, run
from insurance_claims.grounded import field_reply, join_items

CASES = {'CL-2048': {'case_type': 'healthcare', 'status': 'denied'}, 'CL-1899': {'case_type': 'dental'}, 'CL-2102': {'case_type': 'auto'},
         'CL-2011': {'case_id': 'CL-2011'}}
MODEL_TEXT = 'It will be approved on appeal.'


def ask(case, question, replies=None):
    """Resolve a case with an intent, then ask one follow-up. Returns (llm, follow-up result)."""
    hints = {**CASES[case], 'intent': 'status_inquiry'}
    _, llm, rs = run([('go', VERIFIED_ONLY), ('x', {'hints': hints}), (question, {})], replies or {question: MODEL_TEXT})
    return llm, rs[2]


def claim(case):
    """Fixture claim by id."""
    return next(c for c in CLAIMS if c['case_id'] == case)


def test_case_01_join_items_one_two_and_three():
    """CASE-01: join_items gives 'the a', 'the a and the b', 'the a, the b, and the c', and four items keep the serial form."""
    assert join_items(['a']) == 'the a' and join_items(['a', 'b']) == 'the a and the b'
    assert join_items(['a', 'b', 'c']) == 'the a, the b, and the c'
    assert join_items(['a', 'b', 'c', 'd']) == 'the a, the b, the c, and the d'


def test_case_01_first_reply_documents_read_with_articles():
    """CASE-01: the first reply says 'The documents needed are the pathology report and the office note.' or an equivalent with articles."""
    _, _, (r,) = run([(S1_TEXT, S1_EX)])
    assert 'the pathology report and the office note' in r.reply and 'are pathology report' not in r.reply


FIELDS = [('What documents do I need?', 'the pathology report and the office note'), ('What paperwork is missing?', 'the pathology report and the office note'),
          ('What is the status?', 'is denied'), ('Why was it denied?', 'did not include the pathology report and the treating provider office note'),
          ('What is the reason?', 'did not include the pathology report'), ('When is the deadline?', '2026-03-18'),
          ('Is the deadline passed?', 'passed'), ('What is the net pay?', '$0.00'), ('What is the expected reimbursement?', '$0.00'),
          ('What is the allowed maximum?', '$1,450.00')]


@pytest.mark.parametrize('question,expect', FIELDS)
def test_case_01_single_field_question_is_answered_by_code_for_denied_claim(question, expect):
    """CASE-01: a single-field follow-up is answered from the claim with no responder call, no please and no question."""
    llm, r = ask('CL-2048', question)
    assert expect in r.reply and MODEL_TEXT not in r.reply
    assert bundles_for(llm, 'process_case') == [] and 'please' not in r.reply.lower() and '?' not in r.reply


def test_case_01_passed_deadline_answer_states_date_passed_and_human_offer():
    """CASE-01: the deadline answer for CL-2048 gives the date, says it passed and offers a human representative."""
    _, r = ask('CL-2048', 'When is the deadline?')
    assert '2026-03-18' in r.reply and 'passed' in r.reply and 'human representative' in r.reply


@pytest.mark.parametrize('case', sorted(CASES))
@pytest.mark.parametrize('question', ['What is the status?', 'What is the net pay?', 'What is the allowed maximum?'])
def test_case_01_field_answers_are_deterministic_and_use_claim_values(case, question):
    """CASE-01: the same claim and question give the same text, and any amount stated is the claim's own value."""
    a, b = ask(case, question)[1].reply, ask(case, question)[1].reply
    assert a == b
    allowed = {f'${float(claim(case)[k]):,.2f}' for k in ('net_pay', 'allowed_max_amount', 'expected_reimbursement_amount', 'net_fee')}
    assert set(re.findall(r'\$[\d,]+\.\d{2}', a)) <= allowed


@pytest.mark.parametrize('case', ['CL-1899', 'CL-2102', 'CL-2011'])
@pytest.mark.parametrize('question', ['What documents do I need?', 'Why was it denied?', 'When is the deadline?'])
def test_case_01_fields_absent_from_claim_are_not_answered_by_code(case, question):
    """CASE-01: when the claim has no documents, denial reason or deadline, code does not answer: the model path with grounding is used."""
    llm, r = ask(case, question, {question: 'I do not have that information. I can connect you with a human representative.'})
    assert len(bundles_for(llm, 'process_case')) == 1 and r.reply.startswith('I do not have that information')


def test_case_01_net_pay_only_for_claims_that_record_it():
    """CASE-01: net pay for the open auto claim and the closed claim is answered from the recorded value."""
    assert '$0.00' in ask('CL-2102', 'What is the net pay?')[1].reply
    assert '$780.00' in ask('CL-2011', 'What is the net pay?')[1].reply


@pytest.mark.parametrize('question', ['What documents do I need and what is the status?', 'Tell me more', 'How much will I get?',
                                      'Why was it denied? When is the deadline?', 'What is the status? What is the deadline?'])
def test_case_01_multi_field_or_open_questions_use_model_with_grounding(question):
    """CASE-01: two-field and open-ended messages go to the model, and an invented model answer falls back to code text after 2 calls."""
    llm, r = ask('CL-2048', question)
    assert len(bundles_for(llm, 'process_case')) == 2 and MODEL_TEXT not in r.reply and 'CL-2048' in r.reply


def test_case_01_model_path_keeps_an_honest_reply_for_multi_field_question():
    """CASE-01: a grounded model reply for a two-field question is delivered unchanged with one call."""
    q = 'What documents do I need and what is the status?'
    ok = 'The status is denied and the documents needed are the pathology report and the office note.'
    llm, r = ask('CL-2048', q, {q: ok})
    assert r.reply == ok and len(bundles_for(llm, 'process_case')) == 1


def test_case_01_field_reply_is_a_pure_function_of_the_bundle():
    """CASE-01: field_reply returns None without a claim or message, and the same text for the same bundle."""
    bundle = {'claim': claim('CL-2048'), 'caller_message': 'What documents do I need?', 'deadline_passed': True}
    assert field_reply({'caller_message': 'status?'}) is None and field_reply({'claim': claim('CL-2048')}) is None
    assert field_reply(bundle) == field_reply(dict(bundle)) and 'pathology report' in field_reply(bundle)


def test_case_01_first_answer_turn_is_never_a_field_reply():
    """CASE-01: a message with a single field word on the first answer still gets the full first reply, not a single-field answer."""
    _, _, rs = run([('go', VERIFIED_ONLY), ('x', {'hints': {'case_type': 'healthcare', 'status': 'denied', 'intent': 'denial_question'}})])
    assert 'CL-2048' in rs[1].reply and 'documents needed' in rs[1].reply.lower() and 'deadline' in rs[1].reply.lower()
