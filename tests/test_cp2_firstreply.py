"""CP2 round 3: code-built first reply (CASE-01, MEM-03), amount normalization, outcome and action claims in follow-ups."""
import pytest

from cp1helpers import CLAIMS
from cp2helpers import S1_EX, S1_TEXT, VERIFIED_ONLY, bundles_for, rows, run
from insurance_claims.grounding import ungrounded
from insurance_claims.responder import banned_reason
from test_cp2_grounding import BUNDLE

HOLDER_CASES = {'CL-2048': {'case_type': 'healthcare', 'status': 'denied'}, 'CL-1899': {'case_type': 'dental'},
                'CL-2102': {'case_type': 'auto'}, 'CL-2011': {'case_id': 'CL-2011'}}
INTENT = {'intent': 'status_inquiry'}
BAD_FIELDS = ('please', 'how can i help', 'what do you need', 'what would you like')


def first(case):
    """Run verification then the hints for one case. Returns (session, llm, result of the resolving turn)."""
    s, llm, rs = run([('go', VERIFIED_ONLY), ('x', {'hints': {**HOLDER_CASES[case], **INTENT}})])
    return s, llm, rs[1]


def claim(case):
    """Fixture claim by id."""
    return next(c for c in CLAIMS if c['case_id'] == case)


def test_case_01_denied_first_reply_states_all_claim_facts():
    """CASE-01: the first reply for CL-2048 has id, status, reason, both documents, 2026-03-18, that it passed, and a human offer."""
    _, llm, (r) = first('CL-2048')
    t = r.reply
    assert 'CL-2048' in t and 'denied' in t and 'did not include the pathology report and the treating provider office note' in t
    assert 'pathology report' in t and 'office note' in t and '2026-03-18' in t and 'passed' in t and 'human representative' in t
    assert bundles_for(llm, 'process_case') == []


def test_case_01_closed_first_reply_states_status_and_summary_fields_only():
    """CASE-01: the first reply for closed CL-1899 names the id, type and status and no deadline, denial reason or human offer."""
    _, llm, r = first('CL-1899')
    t = r.reply
    assert 'CL-1899' in t and 'dental' in t and 'closed' in t and '425.00' in t
    assert 'deadline' not in t and 'denied' not in t and 'human representative' not in t and bundles_for(llm, 'process_case') == []


def test_case_01_open_first_reply_states_status_and_summary():
    """CASE-01: the first reply for open CL-2102 names the id, type, status and summary and nothing about a deadline or denial."""
    _, llm, r = first('CL-2102')
    assert 'CL-2102' in r.reply and 'auto' in r.reply and 'open' in r.reply and 'Auto claim in progress' in r.reply
    assert 'deadline' not in r.reply and 'denied' not in r.reply and bundles_for(llm, 'process_case') == []


@pytest.mark.parametrize('case', sorted(HOLDER_CASES))
def test_case_01_first_reply_has_no_please_question_or_invented_amount(case):
    """CASE-01 / LANG-02: the first reply has no 'please', no how-can-I-help question and no amount absent from the claim."""
    _, _, r = first(case)
    low = r.reply.lower()
    assert not any(b in low for b in BAD_FIELDS) and '?' not in r.reply
    import re
    allowed = {f'{float(claim(case)[k]):,.2f}' for k in ('expected_reimbursement_amount', 'allowed_max_amount', 'net_pay', 'net_fee')}
    assert set(re.findall(r'\d[\d,]*\.\d{2}', r.reply)) <= allowed


@pytest.mark.parametrize('case', sorted(HOLDER_CASES))
def test_case_01_first_reply_is_deterministic_per_claim(case):
    """CASE-01: the same claim gives the same first reply text in two independent sessions."""
    a = first(case)[2].reply
    b = first(case)[2].reply
    assert a == b


def test_case_01_phrasings_vary_across_claim_ids():
    """CASE-01: across four claims the opening sentences use more than one phrasing pattern."""
    openers = {first(c)[2].reply.split(c)[0].split('.')[-1].strip() + '|' + first(c)[2].reply.split(c)[1][:12] for c in HOLDER_CASES}
    assert len(openers) >= 2


def test_case_01_verified_name_appears_once_on_verification_turn_only():
    """CASE-01 / VER-02: with hints in the same message the name is stated once on the verification turn and never in the follow-up."""
    _, _, rs = run([(S1_TEXT, S1_EX), ('and the deadline?', {})])
    assert rs[0].reply.count('Margaret Chen') == 1 and 'Margaret' not in rs[1].reply
    assert 'verified' in rs[0].reply and 'verified' not in rs[1].reply


def test_case_01_split_verification_turn_has_name_once():
    """CASE-01: when verification completes on a later turn the first reply states the name once."""
    _, _, rs = run([('a', {'identity': {'full_name': 'Margaret Chen'}, 'hints': {'case_type': 'dental'}}), ('b', {'identity': {'dob': '1985-03-15', 'id_last4': '4472'}})])
    assert rs[1].reply.count('Margaret Chen') == 1 and 'CL-1899' in rs[1].reply


def test_case_01_first_reply_contains_no_field_absent_from_the_claim():
    """CASE-01: the closed claim reply holds no denial reason, document list or appeal date, since the claim has none."""
    c = claim('CL-1899')
    assert not any(c.get(k) for k in ('denial_reason', 'documents_needed', 'appeal_deadline'))
    t = first('CL-1899')[2].reply.lower()
    assert 'because' not in t and 'documents' not in t and 'appeal' not in t


@pytest.mark.parametrize('text', ['The allowed maximum is 1,450 dollars.', 'The allowed maximum is $1,450.', 'The allowed maximum is 1450.00.',
                                  'The allowed maximum is 1450 dollars.'])
def test_case_01_amounts_match_by_value(text):
    """CASE-01: 1,450 dollars, $1,450 and 1450.00 all match the bundle amount 1450.00."""
    assert ungrounded(text, BUNDLE) is False and banned_reason(text, BUNDLE) is None


@pytest.mark.parametrize('text', ['The allowed maximum is 1,500 dollars.', 'The allowed maximum is $1,500.', 'The allowed maximum is 1500.00.'])
def test_case_01_wrong_amounts_are_rejected(text):
    """CASE-01: an amount that differs in value from every bundle amount is rejected."""
    assert ungrounded(text, BUNDLE) is True


@pytest.mark.parametrize('text', ['Your claim will be approved if you appeal.', 'Your claim will be approved on appeal.', 'I have filed your appeal.',
                                  'Someone will call you back.', 'I will submit it.'])
def test_case_01_outcome_and_action_promises_are_rejected(text):
    """CASE-01: outcome and action promises absent from the bundle are rejected in follow-ups."""
    assert banned_reason(text, BUNDLE) == 'ungrounded'


@pytest.mark.parametrize('text', ['I can connect you with a human representative.', 'I cannot file appeals.', 'Your claim status is denied.'])
def test_case_01_safe_phrases_pass(text):
    """CASE-01: a human offer, a refusal to file, and a status word present in the bundle are not rejected."""
    assert banned_reason(text, BUNDLE) is None


def test_case_01_promise_present_in_matched_guidance_is_accepted():
    """CASE-01: an action phrase that the matched guidance text states is accepted."""
    b = {**BUNDLE, 'guidance': ['Someone will call you back after the review.']}
    assert banned_reason('Someone will call you back.', b) is None


@pytest.mark.parametrize('promise', ['Your claim will be approved if you appeal.', 'I have filed your appeal for you.', 'Someone will call you back.'])
def test_case_01_follow_up_promise_falls_back_to_code_text(promise):
    """CASE-01 / NFR-01: a model promise on a follow-up question is replaced by code text after one regeneration, two reply calls total."""
    _, llm, rs = run([(S1_TEXT, S1_EX), ('Will my claim be approved if I appeal?', {})], {'Will my claim be approved if I appeal?': promise})
    assert len(bundles_for(llm, 'process_case')) == 2 and promise not in rs[1].reply and 'CL-2048' in rs[1].reply
    assert 'approved' not in rs[1].reply and 'filed' not in rs[1].reply and 'call you back' not in rs[1].reply


def test_case_01_follow_up_honest_model_reply_is_kept():
    """CASE-01: an honest follow-up reply that offers a human representative is delivered unchanged."""
    ok = 'I do not have that information. I can connect you with a human representative.'
    _, llm, rs = run([(S1_TEXT, S1_EX), ('q', {})], {'q': ok})
    assert rs[1].reply == ok and len(bundles_for(llm, 'process_case')) == 1


def test_mem_03_first_reply_uses_stored_hints_without_resolve_call():
    """MEM-03: with hints from earlier turns, the verification turn answers with the code-built reply and no responder call."""
    s, llm, rs = run([('a', {'hints': {'case_type': 'healthcare', 'status': 'denied'}}), ('b', {'identity': {'full_name': 'Margaret Chen', 'dob': '1985-03-15', 'id_last4': '4472'}})])
    assert 'CL-2048' in rs[1].reply and llm.bundles == [] and rows(s)['Resolved case'] == 'CL-2048'
