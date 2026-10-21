"""Check 2 (LANG-01, LANG-02, VER-04, EMO-01): scan every reply produced anywhere in this suite. Runs last by file name."""
import re

import replyrecorder
from templatecheck import check_reply
from insurance_claims.llm import FakeLLM
from insurance_claims.orchestrator import handle_turn, new_session

DASH = re.compile('[\u2013\u2014]')
OPENER = re.compile(r'^\W*(hello|hi|hey|greetings|welcome|good)\b', re.I)
TIME_OF_DAY = re.compile(r'good\s+(morning|afternoon|evening)', re.I)
COUNT_PHRASE = re.compile(r'any three|two of (those|these)|one of (those|these) three|three of (those|these)', re.I)
EMOTION = re.compile(r'frustrat|upset|angry|anger|anxious|anxiety|worried|stressed|annoy|irritat|confus|distress', re.I)


def hits_for(rec):
    """Names of the checks one recorded reply fails."""
    r, hits = rec['reply'], []
    if re.search(r'\bplease\b', r, re.I):
        hits.append('please')
    if TIME_OF_DAY.search(r):
        hits.append('time of day greeting')
    if rec['prior_agent'] >= 1 and OPENER.search(r):
        hits.append('repeat greeting')
    if rec.get('was_verified') and re.search(r'\bverified\b', r, re.I):
        hits.append('verified word on a later turn')
    if DASH.search(r):
        hits.append('dash')
    if COUNT_PHRASE.search(r):
        hits.append('count phrasing')
    for n, m in re.findall(r'(\d+) of (\d+)', r):
        if m != '3' or int(n) != min(rec['confirmed'], 3):
            hits.append(f'wrong count {n} of {m}')
    if rec['intensity'] < 2 and EMOTION.search(r):
        hits.append('emotion word below intensity 2')
    return hits


def membership_problems(records):
    """(problems, reply) for every pre-verification reply: the turn ended unverified and was not rejected."""
    checked = [r for r in records if not r['verified'] and not r['rejected']]
    bad = [(check_reply(r['reply'], set(r['matched_labels']), r['label'], r['intensity'], strikes=r.get('strikes')), r['reply'][:100]) for r in checked]
    return len(checked), [b for b in bad if b[0]]


def test_scan_every_reply_in_the_suite(record_property):
    """Scan all replies recorded in this run. Reports the raw number scanned and each hit with its reply text."""
    s = new_session()
    handle_turn(s, 'hello', FakeLLM())
    records = list(replyrecorder.RECORDS)
    assert len(records) > 0
    bad = [(hits_for(r), r['reply'][:120]) for r in records if hits_for(r)]
    checked, member_bad = membership_problems(records)
    record_property('membership_checked', checked)
    record_property('membership_failures', len(member_bad))
    record_property('replies_scanned', len(records))
    record_property('hits', len(bad))
    assert not member_bad, member_bad[:5]
    assert not bad, bad[:10]


def test_scanner_detects_planted_defects():
    """Positive control: hits_for flags each planted defect and passes a clean reply."""
    base = {'prior_agent': 1, 'intensity': 0, 'confirmed': 1, 'verified': False}
    clean = '1 of 3 confirmed. Any of these still work, and one is enough to start: phone number, or email.'
    assert hits_for({**base, 'reply': clean}) == []
    planted = ['Please share it.', 'Good evening. ' + clean, 'Hello. ' + clean, 'Sure \u2014 ' + clean,
               '2 of 3 confirmed.', '1 of 5 confirmed.', 'Any three of these five work.', 'You sound upset. ' + clean]
    for text in planted:
        assert hits_for({**base, 'reply': text}), text
    assert hits_for({**base, 'prior_agent': 0, 'reply': 'Hello. ' + clean}) == []
    assert hits_for({**base, 'intensity': 2, 'reply': 'You sound upset. ' + clean}) == []


def test_scope_02_human_offer_accepted_only_exact_and_after_limit_strikes():
    """SCOPE-02: the fixed pre-verification human offer passes only as the exact text with strikes at the limit or more."""
    from templatecheck import HUMAN_OFFER
    assert check_reply(HUMAN_OFFER, set(), strikes=3) == [] and check_reply(HUMAN_OFFER, set(), strikes=5) == []
    assert check_reply(HUMAN_OFFER, set(), strikes=2) and check_reply(HUMAN_OFFER, set())
    assert check_reply(HUMAN_OFFER + ' Now.', set(), strikes=3) and check_reply(HUMAN_OFFER.replace('cannot', 'can not'), set(), strikes=3)


def test_membership_check_detects_planted_defects():
    """Positive control: the template check passes a real template and flags edited, wrong-count and uninvited-empathy replies."""
    good = 'Hello, I can help with your claim once I confirm who I am speaking with. 0 of 3 confirmed. Any of these still work, and one is enough to start: full name, date of birth, phone number, email, or last four of SSN.'
    assert check_reply(good, set()) == []
    assert check_reply(good.replace('0 of 3', '1 of 3'), set())
    assert check_reply(good.replace('Hello', 'Hi'), set())
    assert check_reply('It makes sense to want answers quickly, and I want to get you there. ' + good, set())
    assert check_reply('It makes sense to want answers quickly, and I want to get you there. ' + good, set(), 'anger', 2) == []
