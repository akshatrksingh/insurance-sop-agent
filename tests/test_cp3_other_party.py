"""CP3 INT-03 and S9: another person's claim is refused and nothing about them is disclosed. Plus pre-verification text."""
import json

from cp1helpers import AVA, CLAIMS, MARGARET, play, strings
from cp2helpers import S1_EX, S1_TEXT, run

ASK = "show me Ava Lopez's claim"
EXTRACTIONS = [{'identity': {'full_name': 'Ava Lopez'}, 'requests_protected': True}, {'requests_protected': True}, {}]


def ava_values():
    """Ava's identity values plus fields of claims owned by another party."""
    vals = [AVA[k] for k in ('policy_number', 'dob', 'id_last4', 'phone', 'email')]
    for c in CLAIMS:
        if c['party_id'] not in (MARGARET['party_id'],):
            vals += [c['case_id'], c['summary'], str(c['denial_reason'])]
    return [v for v in vals if v]


def blob(s, results):
    """Replies, events and the whole view as text."""
    return json.dumps([[r.reply for r in results], [e.text for r in results for e in r.events], s.view().model_dump()], default=str)


def test_int_03_s9_other_party_claim_is_refused_and_not_disclosed():
    """INT-03, S9: after verifying, asking for Ava Lopez's claim discloses no other party data in reply or view."""
    for ex in EXTRACTIONS:
        s, _, rs = run([(S1_TEXT, S1_EX), (ASK, ex)])
        text = blob(s, rs)
        found = [v for v in ava_values() if v in text]
        assert found == [], f'disclosed {found}'


def test_int_03_s9_refusal_keeps_the_verified_party_case():
    """INT-03, S9: the verified party and resolved case are unchanged after the request."""
    s, _, rs = run([(S1_TEXT, S1_EX), (ASK, EXTRACTIONS[0])])
    rows = {r['label']: r['value'] for r in s.view().model_dump()['memory_rows']}
    assert rows.get('Resolved case') == 'CL-2048' and rows['Full name'] == 'matched'
    assert not any('Ava' in str(x) and 'POL' in str(x) for x in strings(s.view().model_dump()))


def test_int_03_s9_refusal_reply_says_it_cannot_help_with_that():
    """INT-03, S9: the reply is a refusal or redirect about the caller's own claim, with no dashes."""
    _, _, rs = run([(S1_TEXT, S1_EX), (ASK, EXTRACTIONS[0])])
    reply = rs[-1].reply
    assert '\u2014' not in reply and '\u2013' not in reply
    assert 'CL-2048' in reply or 'your' in reply.lower() or 'cannot' in reply.lower()


def test_int_03_other_party_ask_before_verification_changes_nothing():
    """INT-03: asking for Ava's claim before verification discloses nothing and sets no gate."""
    s, _, rs = play([(ASK, EXTRACTIONS[0])])
    text = blob(s, rs)
    assert [v for v in ava_values() if v in text] == []
    assert s.view().phase == 'VERIFY_ID' and not any(g['done'] for p in s.view().model_dump()['phases'] for g in p['gates'])


def test_int_03_replies_before_verification_are_stable_and_dashless():
    """INT-03: the pre-verification reply to a claim ask is the same with or without prior guidance asks, and has no dashes."""
    a = play([('how long after I submit?', {'requests_protected': True})])[2][-1].reply
    b = play([('what file format?', {'requests_protected': True})])[2][-1].reply
    assert a == b and '\u2014' not in a and '\u2013' not in a
    assert 'usually less than a week' not in a
