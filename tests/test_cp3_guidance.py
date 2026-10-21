"""CP3 CASE-02 and CASE-03: follow-up guidance, fallback and human recommendation."""
import re

from cp2helpers import S1_EX, S1_TEXT, run
from insurance_claims.orchestrator import handle_turn

PATH = "I can't get the pathology report"
OFFER = 'Would you like me to connect you with a human representative?'
HANDOFF_EVENT = 'Handed off to a human representative'


def ask(q, extraction=None, prior=()):
    """Verified Margaret session, then the prior turns, then q. Returns (session, llm, results)."""
    return run([(S1_TEXT, S1_EX), *prior, (q, extraction or {})])


def facts(reply):
    """Numbers and dates quoted in a reply."""
    return set(re.findall(r'\d[\d\-]*', reply))


def test_case_02_timing_followup_uses_guideline_text():
    """CASE-02: 'how long after I submit?' gets the processing time template with the fixture value."""
    s, _, rs = ask('how long after I submit?')
    reply = rs[-1].reply
    assert 'usually less than a week' in reply and 'CL-2048' in reply
    assert 'pathology report' in reply and 'office note' in reply
    assert [e.kind for e in rs[-1].events] == ['guidance']


def test_case_02_timing_followup_invents_no_numbers():
    """CASE-02: the timing reply holds only the claim id and no invented days, dollars or dates."""
    _, _, rs = ask('how long after I submit?')
    assert facts(rs[-1].reply) <= {'2048', '-'}


def test_case_02_file_format_followup_uses_document_guidance():
    """CASE-02: 'what file format?' gets the file format template plus per-document guidance."""
    s, _, rs = ask('what file format?')
    reply = rs[-1].reply
    assert 'clear, complete, and easy to review' in reply and 'Upload all pages together in one PDF' in reply
    assert 'patient name, specimen details' in reply
    assert facts(reply) <= {'2048', '-'}


def test_case_02_match_is_shown_in_details():
    """CASE-02: the matched guidance topic is a detail event and in the view event list."""
    s, _, rs = ask('what file format?')
    ev = [e for e in rs[-1].events if e.kind == 'guidance']
    assert ev and ev[0].level == 'detail' and 'Guidance matched' in ev[0].text
    assert any('Guidance matched' in e['text'] for e in s.view().model_dump()['events'])


def test_case_02_nonsense_followup_uses_fallback_not_guidance():
    """CASE-02: a message with no document or timing intent gets no guidance event and no invented guidance."""
    _, _, rs = ask('blah zzz qwerty')
    assert rs[-1].reply.startswith('Claim CL-2048') and not rs[-1].events
    assert 'usually less than a week' not in rs[-1].reply


def test_case_02_followups_do_not_change_claim_data():
    """CASE-02: guidance turns keep the resolved case and phase."""
    s, _, _ = ask('what file format?', prior=[('how long after I submit?', {})])
    rows = {r['label']: r['value'] for r in s.view().model_dump()['memory_rows']}
    assert rows['Resolved case'] == 'CL-2048' and s.view().phase == 'PROCESS_CASE'


def test_case_02_no_dashes_in_guidance_replies():
    """CASE-02 / LANG-01: no em or en dashes in any follow-up reply."""
    for q in ('how long after I submit?', 'what file format?', 'blah zzz', PATH):
        _, _, rs = ask(q)
        assert '\u2014' not in rs[-1].reply and '\u2013' not in rs[-1].reply


def test_case_03_cannot_obtain_recommends_human_representative():
    """CASE-03: the cannot-obtain message gives the alternatives text and offers a human claims representative."""
    s, _, rs = ask(PATH)
    reply = rs[-1].reply
    assert 'replacement copy' in reply and 'human representative' in reply and reply.endswith(OFFER)
    assert [e.kind for e in rs[-1].events] == ['guidance'] and 'document_alternatives' in rs[-1].events[0].text
    assert s.view().phase == 'PROCESS_CASE'


def test_case_03_bare_yes_hands_off():
    """CASE-03: a bare yes after the offer hands off to a human."""
    s, _, rs = ask('yes', {'consent': 'yes'}, prior=[(PATH, {})])
    assert s.view().phase == 'ESCALATED' and [e.kind for e in rs[-1].events] == ['handoff']
    assert HANDOFF_EVENT in [e['text'] for e in s.view().model_dump()['events']]


def test_case_03_no_expires_the_offer():
    """CASE-03: a no stays in the case and a later yes does not hand off."""
    s, llm, rs = ask('no', {'consent': 'no'}, prior=[(PATH, {})])
    assert s.view().phase == 'PROCESS_CASE' and 'handoff' not in [e.kind for e in rs[-1].events]
    llm.extractions['yes'] = {'consent': 'yes'}
    handle_turn(s, 'yes', llm)
    assert s.view().phase != 'ESCALATED'


def test_case_03_unrelated_message_expires_the_offer():
    """CASE-03: any non-yes turn, here an unrelated one, expires the offer so a later yes does not hand off."""
    s, llm, rs = ask('what file format?', prior=[(PATH, {})])
    assert 'handoff' not in [e.kind for e in rs[-1].events]
    llm.extractions['yes'] = {'consent': 'yes'}
    handle_turn(s, 'yes', llm)
    assert s.view().phase != 'ESCALATED'


def test_case_03_offer_is_one_turn_only_after_fallback():
    """CASE-03: a non-yes fallback turn then yes never hands off."""
    s, llm, _ = ask('blah zzz', prior=[(PATH, {})])
    llm.extractions['yes'] = {'consent': 'yes'}
    handle_turn(s, 'yes', llm)
    assert s.view().phase != 'ESCALATED'
