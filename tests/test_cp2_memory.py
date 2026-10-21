"""CP2 MEM-01, MEM-02, MEM-03, MEM-04, S1 (deterministic), S1b."""
import builtins

from cp1helpers import CLAIMS, ident, leaks
from cp2helpers import GROUNDED, HINTS, S1_EX, S1_TEXT, VERIFIED_ONLY, dump, kinds, rows, run
from insurance_claims.orchestrator import handle_turn, new_session

SPLIT = [('Hi I am Margaret Chen about my denied healthcare claim from January', {'identity': {'full_name': 'Margaret Chen'}, 'hints': HINTS}),
         ('my date of birth is 1985-03-15', ident(dob='1985-03-15')), ('last four 4472', ident(id_last4='4472'))]
ASKING = ('how can i help', 'what do you need', 'what would you like', 'what can i help')


def test_s1_margaret_one_message_verifies_resolves_and_grounds_reply():
    """S1 / VER-02 / MEM-03 / INT-02 / CASE-01: one utterance verifies, stores hints, resolves CL-2048 and the reply states its data."""
    s, llm, (r,) = run([(S1_TEXT, S1_EX)], {S1_TEXT: GROUNDED})
    assert s.view().phase == 'PROCESS_CASE'
    assert rows(s)['Resolved case'] == 'CL-2048'
    assert r.reply != GROUNDED and 'CL-2048' in r.reply and 'pathology report' in r.reply and '2026-03-18' in r.reply
    assert 'case_found' in kinds(r) and 'Case found: CL-2048' in [e.text for e in r.events]
    assert llm.bundles == []


def test_s1_margaret_fallback_reply_is_grounded_when_model_text_is_weak():
    """S1 / CASE-01: the code-built first reply names the missing pathology report and office note and does not ask a question."""
    s, _, (r,) = run([(S1_TEXT, S1_EX)])
    assert r.reply.count('Margaret Chen') == 1 and 'verified' in r.reply.split('.')[1] + r.reply.split('.')[0]
    assert 'pathology report' in r.reply and 'office note' in r.reply and '2026-03-18' in r.reply
    assert not any(a in r.reply.lower() for a in ASKING) and '?' not in r.reply


def test_s1b_split_stays_in_verify_id_then_resolves_without_asking():
    """S1b / MEM-03 / VER-03: turns 1 and 2 stay in VERIFY_ID, turn 3 verifies and answers from the stored hints without asking what the caller needs."""
    s, llm, rs = run(SPLIT)
    assert [r.reply for r in rs[:2]] and 'Thanks.' in rs[0].reply and 'of 3 confirmed' in rs[1].reply
    assert not leaks(rs[0].reply + rs[1].reply)
    assert 'case_found' not in kinds(rs[0]) + kinds(rs[1])
    assert s.view().phase == 'PROCESS_CASE' and rows(s)['Resolved case'] == 'CL-2048'
    assert not any(a in rs[2].reply.lower() for a in ASKING)
    assert 'CL-2048' in rs[2].reply and 'pathology report' in rs[2].reply
    assert llm.bundles == []


def test_s1b_after_turn_one_phase_is_verify_id_and_hints_are_in_memory():
    """S1b / MEM-02: after turn 1 the phase is VERIFY_ID, the hints sit in Session memory and no responder call was made."""
    s, llm, rs = run(SPLIT[:1])
    assert s.view().phase == 'VERIFY_ID' and llm.bundles == []
    assert (rows(s)['Claim type'], rows(s)['Status'], rows(s)['Month']) == ('healthcare', 'denied', 'january')


def test_mem_01_extractor_runs_every_turn_in_every_phase():
    """MEM-01: one extract call per turn before and after verification, in every phase reached."""
    turns = SPLIT + [('what is the deadline', {}), ('thanks', {})]
    s, llm, rs = run(turns)
    assert len(llm.extract_views) == len(turns)


def test_mem_01_hints_stored_whenever_stated_after_verification():
    """MEM-01: a hint stated after verification is stored and shown in memory rows."""
    s, _, _ = run([('go', VERIFIED_ONLY), ('dental please', {'hints': {'case_type': 'dental'}})])
    assert rows(s)['Claim type'] == 'dental' and rows(s)['Resolved case'] == 'CL-1899'


def test_mem_01_intent_stored_when_stated():
    """MEM-01 / INT-01: an extracted intent is stored and shown as Intent."""
    s, _, _ = run([('go', VERIFIED_ONLY), ('x', {'hints': {'intent': 'document_submission'}})])
    assert rows(s)['Intent'] == 'document submission'


def test_mem_02_hints_not_echoed_before_verification():
    """MEM-02: hints stated before verification do not change phase, trigger a reply call, or appear in the reply or event text."""
    s, llm, (r,) = run(SPLIT[:1])
    blob = (r.reply + ' ' + ' '.join(e.text for e in r.events)).lower()
    for v in ('healthcare', 'denied', 'january', 'cl-2048'):
        assert v not in blob
    assert s.view().phase == 'VERIFY_ID' and not llm.bundles


def test_mem_03_hints_resolve_case_on_the_verification_turn_without_reask():
    """MEM-03: hints stored earlier select the case on the verification turn, emitting Case found and no question."""
    s, llm, rs = run([('a', {'hints': {'case_type': 'auto'}}), ('b', VERIFIED_ONLY)])
    assert rows(s)['Resolved case'] == 'CL-2102'
    assert 'case_found' in kinds(rs[1]) and 'CL-2102' in rs[1].reply
    assert 'which' not in rs[1].reply.lower() and 'several' not in rs[1].reply.lower()


def test_mem_04_reset_clears_hints_intent_and_case():
    """MEM-04: a fresh session after a full conversation holds no hints, intent or case."""
    run([(S1_TEXT, S1_EX)])
    r = rows(new_session())
    assert not {'Claim type', 'Status', 'Month', 'Intent', 'Resolved case'} & set(r)


def test_mem_04_memory_not_shared_between_sessions():
    """MEM-04: two sessions keep separate hints and resolved cases."""
    a, b = new_session(), new_session()
    llm = run([(S1_TEXT, S1_EX)])[1]
    handle_turn(a, S1_TEXT, llm)
    assert rows(a)['Resolved case'] == 'CL-2048' and 'Resolved case' not in rows(b)


def test_mem_04_nothing_written_to_disk_during_a_full_conversation(monkeypatch, tmp_path):
    """MEM-04: no file is opened for writing while a session holds hints and a resolved case."""
    opened = []
    real = builtins.open

    def spy(file, mode='r', *a, **k):
        """Record any open that is not read only, then delegate."""
        if any(c in str(mode) for c in 'wax+'):
            opened.append((str(file), mode))
        return real(file, mode, *a, **k)

    monkeypatch.setattr(builtins, 'open', spy)
    monkeypatch.chdir(tmp_path)
    run(SPLIT + [('what is the deadline', {})])
    assert opened == [] and list(tmp_path.iterdir()) == []


def test_mem_04_sidebar_memory_rows_hold_hints_but_no_claim_data():
    """MEM-04 / UI-03: after S1 the view shows the hints and resolved case id but no claim summary, denial reason, amount or deadline."""
    s, _, _ = run([(S1_TEXT, S1_EX)])
    blob = dump(s.view().model_dump())
    turns_removed = dump({k: v for k, v in s.view().model_dump().items() if k not in ('turns',)})
    for c in CLAIMS:
        for k in ('summary', 'denial_reason', 'appeal_deadline', 'allowed_max_amount'):
            if c.get(k):
                assert str(c[k]) not in turns_removed
    assert 'CL-2048' in blob
