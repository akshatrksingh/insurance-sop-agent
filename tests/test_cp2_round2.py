"""CP2 fix round 2: F1 same-call stale case_id with a resolvable remainder, F9 notice turns and first_agent_turn."""
import pytest

from cp1helpers import Rec, gates
from cp2helpers import VERIFIED_ONLY, bundles_for, kinds, rows, run
from insurance_claims.cases import CASE_QUESTION
from insurance_claims.orchestrator import handle_turn, new_session

REPLIES = {'go': 'You are verified, Margaret Chen. What do you need help with on your claims?'}
DROPPED = 'Dropped: case_id (no such claim)'


@pytest.mark.parametrize('bad', ['CL-9999', 'CL-3001'])
def test_int_02_f1_stale_case_id_with_dental_hint_resolves_one_claim_same_turn(bad):
    """INT-02 / F1: a stale case_id plus a hint that fits one claim resolves it on the same turn, with Case found and no CASE_QUESTION."""
    s, llm, rs = run([('go', VERIFIED_ONLY), ('x', {'hints': {'case_id': bad, 'case_type': 'dental', 'intent': 'status_inquiry'}})])
    r = rs[1]
    assert r.reply != CASE_QUESTION and 'CL-1899' in r.reply and 'closed' in r.reply and bundles_for(llm, 'process_case') == []
    assert DROPPED in [e.text for e in r.events] and kinds(r).count('case_found') == 1
    assert rows(s)['Resolved case'] == 'CL-1899' and 'Case ID' not in rows(s)
    assert s.view().phase == 'PROCESS_CASE' and gates(s)[:6] == [True, True, True, True, False, False][:6] and gates(s)[3]


def test_int_02_f1_grounded_answer_for_denied_claim_after_stale_id():
    """INT-02 / CASE-01 / F1: stale case_id with healthcare plus denied resolves CL-2048 and the answer names the documents and the passed deadline."""
    s, llm, rs = run([('go', VERIFIED_ONLY), ('x', {'hints': {'case_id': 'CL-9999', 'case_type': 'healthcare', 'status': 'denied'}})])
    assert 'pathology report' in rs[1].reply and '2026-03-18' in rs[1].reply and rows(s)['Resolved case'] == 'CL-2048'
    assert bundles_for(llm, 'process_case') == []


def test_int_02_f1_without_intent_resolves_case_and_asks_what_to_know_not_case_question():
    """INT-02 / F1: remaining hints resolve one claim but no intent: phase stays RESOLVE_INTENT, the reply names the claim, not CASE_QUESTION."""
    s, _, rs = run([('go', VERIFIED_ONLY), ('x', {'hints': {'case_id': 'CL-9999', 'case_type': 'dental'}})])
    assert rows(s)['Resolved case'] == 'CL-1899' and 'CL-1899' in rs[1].reply and rs[1].reply != CASE_QUESTION
    assert s.view().phase == 'RESOLVE_INTENT' and 'Intent' not in rows(s)


def test_int_02_f1_remainder_not_unique_gives_fixed_question():
    """INT-02 / F1 actual behavior: stale case_id plus a hint matching two claims gives CASE_QUESTION with no model call and nothing resolved."""
    s, llm, rs = run([('go', VERIFIED_ONLY), ('x', {'hints': {'case_id': 'CL-9999', 'case_type': 'healthcare'}})])
    assert 'Resolved case' not in rows(s) and rs[1].reply == CASE_QUESTION and len(llm.bundles) == 1


def first_flags(llm):
    """first_agent_turn values of the bundles built so far."""
    return [b['first_agent_turn'] for _, b in llm.bundles]


@pytest.mark.parametrize('notice_text', ['   ', 'x' * 2001])
def test_f9_notice_does_not_consume_first_agent_turn(notice_text):
    """F9: after an empty or oversized-input notice the next real turn still has first_agent_turn true and the notice stays in the transcript."""
    llm, s = Rec(extractions={'go': VERIFIED_ONLY}, replies=REPLIES), new_session()
    n = handle_turn(s, notice_text, llm)
    r = handle_turn(s, 'go', llm)
    assert set(first_flags(llm)) == {True}
    assert ('Agent', n.reply) in s.view().turns and s.view().turns[0] == ('Agent', n.reply)
    assert r.reply and len(s.view().turns) == 3


def test_f9_two_notices_then_verification_turn_still_first():
    """F9: several notices in a row, then the verification turn: first_agent_turn is true in every bundle of that turn."""
    llm, s = Rec(extractions={'go': VERIFIED_ONLY}, replies=REPLIES), new_session()
    handle_turn(s, '', llm)
    handle_turn(s, 'y' * 2500, llm)
    handle_turn(s, 'go', llm)
    assert set(first_flags(llm)) == {True}


def test_f9_real_greeting_reply_ends_first_agent_turn():
    """F9: after a real pre-verification reply, a notice and then the verification turn give first_agent_turn false."""
    llm, s = Rec(extractions={'go': VERIFIED_ONLY}, replies=REPLIES), new_session()
    handle_turn(s, 'hello', llm)
    handle_turn(s, '', llm)
    handle_turn(s, 'go', llm)
    assert set(first_flags(llm)) == {False}
