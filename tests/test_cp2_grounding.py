"""CP2 CASE-01 deterministic grounding (F2, F3): ungrounded() and banned_reason() on time frames, formats, amounts, documents."""
import copy

import pytest

from cp2helpers import S1_EX, S1_TEXT, run
from insurance_claims.grounding import ungrounded
from insurance_claims.responder import banned_reason

CLAIM = {'case_id': 'CL-2048', 'case_type': 'healthcare', 'created_at': '2026-01-12', 'status': 'denied',
         'summary': 'Healthcare claim denied due to missing pathology report and office note',
         'denial_reason': 'the review file did not include the pathology report and the treating provider office note',
         'documents_needed': ['pathology report', 'office note'], 'appeal_deadline': '2026-03-18', 'allowed_max_amount': '1450.00'}
BUNDLE = {'phase': 'PROCESS_CASE', 'verified_this_turn': False, 'first_agent_turn': False, 'first_answer': False,
          'deadline_passed': True, 'intent': 'next_steps', 'caller_message': 'x', 'claim': CLAIM}
CLEAN = ('Your claim CL-2048 is denied because the review file did not include the pathology report and the treating '
         'provider office note. The appeal deadline 2026-03-18 has passed and I can connect you with a human representative.')
INVENTED = {
    'time digits': 'It will be reviewed in 5 business days.', 'time words': 'It will be reviewed within two weeks.',
    'time couple': 'Expect a decision in a couple of days.', 'time next week': 'You will hear back next week.',
    'iso date': 'Send it by 2026-04-30.', 'slash date': 'Send it by 03/25/2026.', 'month date': 'Send it by March 25.',
    'format pdf': 'Send it as a pdf.', 'format jpg': 'A jpg is fine.', 'format fax': 'You can use fax.',
    'format attachment': 'Use an email attachment.', 'amount words': 'You will get five hundred dollars.',
    'amount digits': 'You will get 500 dollars.', 'document letter': 'Bring your denial letter.',
    'document proof': 'Send proof of residence.', 'document estimate': 'Send a repair estimate.',
}


@pytest.mark.parametrize('name', sorted(INVENTED))
def test_case_01_invented_detail_is_ungrounded_and_banned(name):
    """CASE-01 / F2: a time frame, format, amount or named document absent from the bundle is rejected by ungrounded() and banned_reason()."""
    assert ungrounded(INVENTED[name], BUNDLE) is True
    assert banned_reason(INVENTED[name], BUNDLE) == 'ungrounded'


@pytest.mark.parametrize('name,detail,key', [
    ('time digits', 'It will be reviewed in 5 business days.', 'guidance'), ('time words', 'It will be reviewed within two weeks.', 'guidance'),
    ('format pdf', 'Send it as a pdf.', 'guidance'), ('format fax', 'You can use fax.', 'guidance'),
    ('document letter', 'Bring your denial letter.', 'guidance'), ('iso date', 'Send it by 2026-04-30.', 'guidance')])
def test_case_01_detail_present_in_matched_guidance_is_accepted(name, detail, key):
    """CASE-01 / F2: the same detail is accepted when the bundle's matched guidance text states it."""
    b = {**copy.deepcopy(BUNDLE), key: [detail + ' Also keep copies.']}
    assert ungrounded(detail, b) is False and banned_reason(detail, b) is None


def test_case_01_detail_present_in_claim_data_is_accepted():
    """CASE-01 / F2: details stated in the claim (documents, ISO date, case id) pass."""
    for t in ('The pathology report and office note are needed.', 'The appeal deadline is 2026-03-18.', 'Claim CL-2048 is denied.'):
        assert ungrounded(t, BUNDLE) is False and banned_reason(t, BUNDLE) is None, t


def test_case_01_month_name_date_matches_iso_date_in_bundle():
    """CASE-01 / F2: 'March 18, 2026' is accepted because the bundle holds 2026-03-18, and 'March 19' is not."""
    assert ungrounded('The deadline was March 18, 2026.', BUNDLE) is False
    assert ungrounded('The deadline was March 19.', BUNDLE) is True


def test_case_01_clean_grounded_reply_is_not_rejected():
    """CASE-01 / F2 false-positive guard: the clean CL-2048 reply (pathology report, office note, 2026-03-18) is accepted on first and later answers."""
    first = {**BUNDLE, 'first_answer': True}
    assert banned_reason(CLEAN, first) is None and banned_reason(CLEAN, BUNDLE) is None
    for t in ('The documents needed are the pathology report and the office note.', 'Your healthcare claim is denied.',
              'I do not have that information. I can connect you with a human representative.'):
        assert banned_reason(t, BUNDLE) is None, t


@pytest.mark.parametrize('name', ['time words', 'format pdf', 'amount words', 'document letter', 'month date'])
def test_case_01_invented_follow_up_falls_back_after_single_regeneration(name):
    """CASE-01 / NFR-01: an invented detail twice on a follow-up gives the code-built reply after exactly two reply calls."""
    _, llm, rs = run([(S1_TEXT, S1_EX), ('q', {})], {'q': INVENTED[name]})
    assert len(llm.bundles) == 2 and 'pathology report' in rs[1].reply and INVENTED[name] not in rs[1].reply
    assert '2026-03-18' in rs[1].reply


def test_case_01_first_reply_makes_no_responder_call_even_if_model_text_is_scripted():
    """CASE-01: the first claim reply is code-built, so scripted invented model text for that turn is never requested or shown."""
    _, llm, (r,) = run([(S1_TEXT, S1_EX)], {S1_TEXT: 'You are verified, Margaret Chen. ' + INVENTED['time words']})
    assert llm.bundles == [] and 'two weeks' not in r.reply and 'pathology report' in r.reply


def test_case_01_call_count_stays_at_most_three_in_a_turn_pair():
    """NFR-01: with invented replies every follow-up makes at most 2 reply calls (3 with the extract) and the first reply makes none."""
    bad = 'It takes two weeks as a pdf.'
    turns = [(S1_TEXT, S1_EX), ('q1', {}), ('q2', {})]
    _, llm, rs = run(turns, {t: bad for t, _ in turns})
    assert len(llm.bundles) == 4 and all('two weeks' not in r.reply and 'pdf' not in r.reply for r in rs)


@pytest.mark.parametrize('text', ['Your claim will be approved on appeal.', 'I have filed your appeal for you.',
                                  'You will be reimbursed in full.', 'A supervisor will call you back soon.'])
def test_case_01_standalone_non_numeric_invented_claim_is_rejected(text):
    """CASE-01 / F3: a reply that invents an outcome or action with no number, format or document word is rejected (reported as found)."""
    assert banned_reason(text, BUNDLE) is not None
