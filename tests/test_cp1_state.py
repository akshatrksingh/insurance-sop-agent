"""CP1 VER-01, SOP-01, SOP-02, key event, NFR-01, NFR-02 (with extract)."""
import statistics
import time

from cp1helpers import FakeLLM, Rec, gates, ident, play
from insurance_claims.orchestrator import handle_turn, new_session

FULL = ident(full_name='Margaret Chen', dob='1985-03-15', id_last4='4472')


def statuses(s):
    """Phase statuses in view order."""
    return [p['status'] for p in s.view().model_dump()['phases']]


def test_ver_01_phases_in_order_and_only_verify_advances_in_cp1():
    """VER-01: order is VERIFY_ID, RESOLVE_INTENT, PROCESS_CASE, POST_PROCESS and verification moves to RESOLVE_INTENT."""
    s = new_session()
    assert [p['name'] for p in s.view().model_dump()['phases']] == ['VERIFY_ID', 'RESOLVE_INTENT', 'PROCESS_CASE', 'POST_PROCESS']
    s, _, _ = play([('t', FULL)])
    assert s.view().phase == 'RESOLVE_INTENT'


def test_sop_01_phase_is_first_phase_not_done_derived_from_gates():
    """SOP-01: the view phase equals the first phase whose gates are not all done."""
    for turns in ([], [('a', {})], [('t', FULL)]):
        s, _, _ = play(turns) if turns else (new_session(), None, None)
        phases = s.view().model_dump()['phases']
        first = next(p['name'] for p in phases if not all(g['done'] for g in p['gates']))
        assert s.view().phase == first


def test_sop_02_status_values_before_and_after_verification():
    """SOP-02: pending, current, done derived from gates."""
    assert statuses(new_session()) == ['current', 'pending', 'pending', 'pending']
    s, _, _ = play([('t', FULL)])
    assert statuses(s) == ['done', 'current', 'pending', 'pending']


def test_sop_01_gates_never_go_true_to_false_except_on_reset():
    """4.1: after verification, later turns including wrong factors and refusal never un-set a gate."""
    s, llm, _ = play([('t', FULL)])
    before = gates(s)
    for text, ex in [('wrong', ident(full_name='Nobody', dob='2000-01-01')), ('no', {'refused_verification': True}), ('hi', {})]:
        llm.extractions[text] = ex
        handle_turn(s, text, llm)
        assert all(b <= a for b, a in zip(before, gates(s)))
        assert s.view().phase != 'VERIFY_ID'


def test_sop_01_gates_cleared_on_fresh_session():
    """4.1: a new session starts with every gate false."""
    play([('t', FULL)])
    assert not any(gates(new_session()))


def test_key_event_verification_complete_once():
    """UI-01 / FRONTEND key event: 'Verification complete' appears once at level key when the third factor matches."""
    s, llm, results = play([('a', ident(full_name='Margaret Chen')), ('b', ident(dob='1985-03-15')), ('c', ident(id_last4='4472'))])
    key = [[e for e in r.events if e.level == 'key'] for r in results]
    assert key[0] == [] and key[1] == []
    assert len(key[2]) == 1 and key[2][0].text.startswith('Verification complete')
    llm.extractions['d'] = {}
    again = handle_turn(s, 'd', llm)
    assert not [e for e in again.events if 'Verification complete' in e.text]
    events = [e for e in s.view().model_dump()['events'] if 'Verification complete' in e['text']]
    assert len(events) == 1 and events[0]['level'] == 'key'


def test_nfr_01_calls_per_turn_one_before_verification_two_after():
    """NFR-01: exactly one call (extract) per pre-verification turn and extract plus reply per post-verification turn."""
    turns = [(f'm{i}', ex) for i, ex in enumerate([{}, ident(full_name='Margaret Chen'), ident(dob='1985-03-15'), FULL, {}, {}])]
    llm = Rec(extractions=dict(turns), replies={t: 'Understood.' for t, _ in turns})
    s = new_session()
    expected = [(1, 0), (1, 0), (1, 0), (1, 1), (1, 1), (1, 1)]
    for (text, _), want in zip(turns, expected):
        e0, r0 = len(llm.extract_views), len(llm.bundles)
        handle_turn(s, text, llm)
        assert (len(llm.extract_views) - e0, len(llm.bundles) - r0) == want, text


def test_nfr_01_rejected_input_makes_no_llm_calls():
    """NFR-01 / input validation: an empty message makes no LLM call."""
    llm = Rec()
    handle_turn(new_session(), '   ', llm)
    assert llm.extract_views == [] and llm.bundles == []


def test_nfr_02_overhead_p95_under_50ms_with_extraction(record_property):
    """NFR-02: harness overhead per turn with FakeLLM including extraction and verification, p95 under 50 ms."""
    llm = FakeLLM(extractions={'t': FULL, 'u': ident(full_name='Margaret Chen')})
    times = []
    for i in range(200):
        s = new_session()
        for text in ('u', 't'):
            t0 = time.perf_counter()
            handle_turn(s, text, llm)
            times.append((time.perf_counter() - t0) * 1000)
    times.sort()
    p95 = times[int(len(times) * 0.95) - 1]
    record_property('nfr_02_cp1_ms', f'p50={statistics.median(times):.3f} p95={p95:.3f} max={times[-1]:.3f}')
    assert p95 < 50
