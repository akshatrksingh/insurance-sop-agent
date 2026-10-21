"""CP1 VER-03, VER-06, SAFE-02 (verify bundle), MEM-02, S1b (state part), S4 (without human offer)."""
import json

import pytest

from cp1helpers import (AVA, MISMATCH_WORDS, bundle_blob, failure_names_factor, gates, ident, leaks, matched, play,
                        public_blob)

WRONG = [
    ident(full_name='Margaret Chen', dob='1999-01-01'),
    ident(full_name='Margaret Chen', phone='6500000000'),
    ident(full_name='Margaret Chen', email='nobody@nowhere.org'),
    ident(full_name='Margaret Chen', id_last4='0000'),
    ident(full_name='Nobody Atall', dob=AVA['dob'], id_last4=AVA['id_last4']),
]
ASKS = ['why was my claim denied?', 'what is the status of my claim', 'do I have any claims?']


@pytest.mark.parametrize('ex', WRONG)
def test_ver_06_no_stored_value_or_mismatch_hint_after_wrong_factor(ex):
    """VER-06: after a supplied wrong factor, no reply, event, row or bundle holds a stored value or a mismatch word."""
    s, llm, results = play([('t', ex)])
    blob = public_blob(s, results) + bundle_blob(llm)
    assert leaks(blob) == []
    assert not any(w in blob.lower() for w in MISMATCH_WORDS)
    assert failure_names_factor(results, llm) == []


def test_ver_06_wrong_factor_row_stays_pending_not_marked_wrong():
    """VER-06: a wrong DOB does not change the DOB row to a distinct state."""
    s, _, _ = play([('t', ident(full_name='Margaret Chen', dob='1999-01-01'))])
    rows = {r['label']: r['value'] for r in s.view().model_dump()['memory_rows']}
    assert rows['Date of birth'] == 'pending' and rows['Full name'] == 'matched'


def test_s4_three_wrong_rounds_leak_nothing_and_stay_unverified():
    """S4 / VER-06 (no human offer here): three rounds of wrong factors reveal nothing and never verify."""
    turns = [(f'try {i}', ex) for i, ex in enumerate(WRONG[:3])]
    s, llm, results = play(turns)
    assert not any(gates(s)) and s.view().phase == 'VERIFY_ID'
    blob = public_blob(s, results) + bundle_blob(llm)
    assert leaks(blob) == [] and not any(w in blob.lower() for w in MISMATCH_WORDS)
    rows = {r['label']: r['value'] for r in s.view().model_dump()['memory_rows']}
    assert rows['Failed verification rounds'] == '3'


def test_ver_03_failed_rounds_count_only_supplied_unmatched_factors():
    """4.1: a turn with no identity is not a failed round; a turn with a wrong factor is."""
    s, _, _ = play([('hi', {}), ('t', WRONG[0])])
    rows = {r['label']: r['value'] for r in s.view().model_dump()['memory_rows']}
    assert rows['Failed verification rounds'] == '1'


@pytest.mark.parametrize('ask', ASKS)
@pytest.mark.parametrize('ex', [{}, ident(full_name='Margaret Chen'), WRONG[1]])
def test_ver_03_no_claim_data_or_party_name_before_verification(ask, ex):
    """VER-03 / SAFE-02: asking for claim data before verification gives no claim data, party name or claim existence cue."""
    s, llm, results = play([(ask, ex)])
    blob = public_blob(s, results) + bundle_blob(llm)
    assert leaks(blob) == []
    assert s.view().phase == 'VERIFY_ID'
    lowered = blob.lower()
    for word in ('cl-2048', 'denied', 'pathology', 'appeal'):
        assert word not in lowered


def test_safe_02_no_reply_call_exists_before_verification():
    """SAFE-02: before verification no model reply is requested, so no bundle exists to hold excluded data (absent, not just forbidden)."""
    s, llm, results = play([('a', ident(full_name='Margaret Chen', policy_number='POL-9921')), ('b', ident(dob='1985-03-15'))])
    assert llm.bundles == [] and len(llm.extract_views) == 2
    assert leaks(public_blob(s, results)) == []
    assert all('Margaret' not in r.reply and 'Chen' not in r.reply and 'POL-' not in r.reply for r in results)


def test_safe_02_pre_verification_reply_tracks_matched_count_and_still_needed():
    """4.3: the pre-verification reply states the matched count and lists exactly the factor types still needed."""
    _, _, results = play([('a', ident(full_name='Margaret Chen', dob='1985-03-15'))])
    reply = results[0].reply
    assert '2 of 3 confirmed' in reply
    assert 'full name' not in reply and 'date of birth' not in reply
    assert all(x in reply for x in ('phone number', 'email', 'last four of SSN'))


def test_safe_02_bundle_for_phase_after_verification_carries_no_other_party():
    """SAFE-02: after verification the next bundle names only the caller's own first name, no other party."""
    _, llm, _ = play([('t', ident(full_name='Margaret Chen', dob='1985-03-15', id_last4='4472'))])
    blob = json.dumps([b for _, b in llm.bundles])
    for other in ('Ava', 'Lopez', 'Tian', 'Yaven', 'POL-1044', '9180', '6688', '5317'):
        assert other not in blob


def test_mem_02_hints_stored_without_phase_change_and_not_echoed_before_verification():
    """MEM-02 / S1b state part: name plus claim hint keeps VERIFY_ID, stores the hint, does not echo it in the reply or bundle."""
    hints = {'case_type': 'healthcare', 'status': 'denied', 'month': 'January'}
    s, llm, results = play([('t', {**ident(full_name='Margaret Chen'), 'hints': hints})])
    v = s.view().model_dump()
    assert v['phase'] == 'VERIFY_ID' and not any(gates(s))
    rows = {r['label']: r['value'] for r in v['memory_rows']}
    assert 'healthcare' in rows.values() or 'January' in rows.values()
    for text in [r.reply for r in results] + [bundle_blob(llm)]:
        assert 'healthcare' not in text.lower() and 'january' not in text.lower() and 'denied' not in text.lower()


def test_mem_02_hint_kept_after_verification():
    """MEM-02: the hint stored in VERIFY_ID is still in memory after verification, with no phase decided by it."""
    s, _, _ = play([('a', {**ident(full_name='Margaret Chen'), 'hints': {'month': 'January'}}),
                    ('b', ident(dob='1985-03-15', id_last4='4472'))])
    rows = {r['label']: r['value'] for r in s.view().model_dump()['memory_rows']}
    assert s.view().phase != 'VERIFY_ID' and 'January' in rows.values()


def test_ver_06_matched_set_never_exposes_values_in_view_json():
    """VER-06 / UI-03: the view exposes factor names and flags only, never matched values."""
    s, _, results = play([('t', ident(full_name='Margaret Chen', dob='1985-03-15', id_last4='4472'))])
    assert matched(s) == {'Full name', 'Date of birth', 'ID last 4'}
    v = s.view().model_dump()
    v.pop('turns')
    assert leaks(json.dumps(v)) == []
