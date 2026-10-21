"""CP2 INT-02, MEM-01, UI-05: a case_id hint that matches no claim of the verified party is dropped."""
import pytest

from cp2helpers import ID3, VERIFIED_ONLY, bundles_for, rows, run
from insurance_claims.cases import CASE_QUESTION

BAD = ['CL-9999', 'CL-3001']
DROPPED = 'Dropped: case_id (no such claim)'
REFUSAL = "I can only discuss your own claim, so I cannot share anyone else's."


def expected(bad):
    """Fixed reply on the dropping turn: another party's id gets the B38 refusal line first."""
    return f'{REFUSAL} {CASE_QUESTION}' if bad == 'CL-3001' else CASE_QUESTION


def calls(llm):
    """Number of responder calls made."""
    return len(llm.bundles)


@pytest.mark.parametrize('bad', BAD)
def test_int_02_dropped_hint_leaves_memory_and_row(bad):
    """INT-02 / MEM-01: the unmatched case_id is gone from Session.view() rows after the turn."""
    s, _, _ = run([('go', VERIFIED_ONLY), ('x', {'hints': {'case_id': bad}})])
    assert 'Case id' not in rows(s) and bad not in str(s.view().model_dump()['memory_rows'])


@pytest.mark.parametrize('bad', BAD)
def test_int_02_question_asked_once_then_normal_flow(bad):
    """INT-02: the fixed question appears on the dropping turn only. The next turn does not repeat it."""
    s, _, rs = run([('go', VERIFIED_ONLY), ('x', {'hints': {'case_id': bad}}), ('y', {})])
    assert rs[1].reply == expected(bad) and rs[2].reply != CASE_QUESTION and REFUSAL not in rs[2].reply


@pytest.mark.parametrize('bad', BAD)
def test_int_02_no_model_call_on_the_dropping_turn(bad):
    """INT-02 / NFR-01: the dropping turn makes no responder call."""
    _, llm, rs = run([('go', VERIFIED_ONLY), ('x', {'hints': {'case_id': bad}})])
    assert calls(llm) == 1 and rs[1].reply == expected(bad)


@pytest.mark.parametrize('bad', BAD)
def test_int_02_later_valid_case_id_resolves(bad):
    """INT-02: after a dropped hint, a new valid case_id resolves the case."""
    s, _, rs = run([('go', VERIFIED_ONLY), ('x', {'hints': {'case_id': bad}}), ('y', {'hints': {'case_id': 'CL-2011'}})])
    assert rows(s)['Resolved case'] == 'CL-2011' and 'case_found' in [e.kind for e in rs[2].events]


@pytest.mark.parametrize('bad', BAD)
def test_ui_05_dropped_event_is_a_detail_event(bad):
    """UI-05: the dropping turn emits the detail event 'Dropped: case_id (no such claim)'."""
    _, _, rs = run([('go', VERIFIED_ONLY), ('x', {'hints': {'case_id': bad}})])
    ev = [e for e in rs[1].events if e.text == DROPPED]
    assert len(ev) == 1 and ev[0].level == 'detail'


def test_int_02_other_stored_hints_survive_a_dropped_case_id():
    """MEM-01: only the case_id hint is dropped. Other hints stay in the status rows."""
    s, _, _ = run([('go', VERIFIED_ONLY), ('x', {'hints': {'case_id': 'CL-9999', 'case_type': 'healthcare'}})])
    assert rows(s)['Claim type'] == 'healthcare'


def test_int_02_verification_turn_actual_behavior_no_intent():
    """INT-02 actual behavior: a bad case_id on the verification turn is dropped with the event, the reply comes from the model (ask_need), not CASE_QUESTION."""
    s, llm, rs = run([('go', {'identity': ID3, 'hints': {'case_id': 'CL-9999'}})])
    assert DROPPED in [e.text for e in rs[0].events]
    assert rs[0].reply != CASE_QUESTION and bundles_for(llm, 'resolve_intent')[0]['case_state'] == 'ask_need'
    assert 'Resolved case' not in rows(s)


def test_int_02_verification_turn_actual_behavior_with_intent():
    """INT-02 actual behavior: with a stored intent the verification-turn bundle state is 'several' (all claims fit), reply comes from the model path."""
    s, llm, rs = run([('go', {'identity': ID3, 'hints': {'case_id': 'CL-9999', 'intent': 'status_inquiry'}})])
    assert DROPPED in [e.text for e in rs[0].events]
    b = bundles_for(llm, 'resolve_intent')[0]
    assert b['case_state'] == 'several' and b['hints'] == {} and rs[0].reply != CASE_QUESTION


def test_int_02_hint_stored_before_verification_is_dropped_on_verification_turn():
    """INT-02: a bad case_id stated before verification is dropped when verification completes and the normal verified reply is given."""
    s, _, rs = run([('a', {'hints': {'case_id': 'CL-9999'}}), ('go', VERIFIED_ONLY)])
    assert DROPPED in [e.text for e in rs[1].events] and 'verified' in rs[1].reply.lower() and rs[1].reply != CASE_QUESTION
