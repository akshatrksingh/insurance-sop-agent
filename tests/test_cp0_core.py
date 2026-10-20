"""CP0 core: FakeLLM round trip, SOP view, input validation, NFR-01, NFR-02."""
import statistics
import time

from insurance_claims.llm import FakeLLM
from insurance_claims.orchestrator import handle_turn, new_session


def test_fakellm_round_trip_through_handle_turn():
    """CP0 exit: FakeLLM round trip."""
    s = new_session()
    r = handle_turn(s, 'hello', FakeLLM())
    assert isinstance(r.reply, str) and r.reply.strip()
    assert r.email_preview is None
    assert isinstance(r.events, list)
    v = s.view()
    assert ('Caller', 'hello') in v.turns
    assert ('Agent', r.reply) in v.turns


def test_new_session_has_distinct_ids_and_starts_in_verify_id():
    """VER-01 / SOP-01 (CP0 part): start phase is VERIFY_ID, nothing done."""
    a, b = new_session(), new_session()
    assert a.session_id != b.session_id
    v = a.view()
    assert v.phase == 'VERIFY_ID'
    assert [p.name for p in v.phases] == ['VERIFY_ID', 'RESOLVE_INTENT', 'PROCESS_CASE', 'POST_PROCESS']
    assert not any(g.done for p in v.phases for g in p.gates)


def test_sop_02_status_pending_current_done_values():
    """SOP-02 (CP0 part): one current phase, others pending."""
    st = [p.status for p in new_session().view().phases]
    assert st == ['current', 'pending', 'pending', 'pending']


def test_sop_01_gates_per_design_4_1():
    """SOP-01: gate counts per phase match SYSTEM_DESIGN 4.1 derivation table."""
    counts = [len(p.gates) for p in new_session().view().phases]
    assert counts == [1, 2, 2, 2]


def test_empty_message_rejected_without_state_change():
    """Input validation: empty message does not count as a turn."""
    s = new_session()
    r = handle_turn(s, '   ', FakeLLM())
    assert r.reply
    assert not any(role == 'Caller' for role, _ in s.view().turns)


def test_oversized_message_rejected():
    """Input validation: over 2000 chars rejected before logic."""
    s = new_session()
    r = handle_turn(s, 'x' * 2001, FakeLLM())
    assert '2000' in r.reply
    assert not any(role == 'Caller' for role, _ in s.view().turns)


def test_2000_chars_accepted():
    """Input validation boundary: exactly 2000 chars accepted."""
    s = new_session()
    handle_turn(s, 'x' * 2000, FakeLLM())
    assert len(s.view().turns) == 2


def test_sessions_are_isolated():
    """MEM-04 (CP0 part): turns live in the session only."""
    a, b = new_session(), new_session()
    handle_turn(a, 'hello', FakeLLM())
    assert b.view().turns == []


def test_nfr_01_llm_calls_per_turn_at_most_2():
    """NFR-01: at most 2 LLM calls per turn."""
    calls = []

    class Counting(FakeLLM):
        def extract(self, *a, **k):
            calls.append('extract')
            return super().extract(*a, **k)

        def reply(self, *a, **k):
            calls.append('reply')
            return super().reply(*a, **k)

    s = new_session()
    llm = Counting()
    for i in range(5):
        calls.clear()
        handle_turn(s, f'hello {i}', llm)
        assert len(calls) <= 2, calls


def test_nfr_02_overhead_p95_under_50ms(record_property):
    """NFR-02: harness overhead per turn with FakeLLM, p95 < 50 ms."""
    llm = FakeLLM()
    times = []
    for _ in range(200):
        s = new_session()
        t = time.perf_counter()
        handle_turn(s, 'hello', llm)
        times.append((time.perf_counter() - t) * 1000)
    times.sort()
    p95 = times[int(len(times) * 0.95) - 1]
    record_property('nfr_02_ms', f'p50={statistics.median(times):.3f} p95={p95:.3f} max={times[-1]:.3f}')
    assert p95 < 50
