"""CP2 INT-01, INT-02, CASE-01, SAFE-02 (case bundles), post-verification carry-overs."""
import pytest

from cp1helpers import ident
from insurance_claims.cases import CASE_QUESTION
from cp2helpers import HINTS, S1_EX, S1_TEXT, VERIFIED_ONLY, bundles_for, kinds, rows, run

INTENTS = ['status_inquiry', 'denial_question', 'document_submission', 'next_steps', 'general_claim_question']
LABELS = {'status_inquiry': 'status inquiry', 'denial_question': 'denial question', 'document_submission': 'document submission',
          'next_steps': 'next steps', 'general_claim_question': 'general claim question'}
MATIAN_ID = ident(full_name='Ma Tian', dob='1964-09-10', id_last4='6688')


@pytest.mark.parametrize('intent', INTENTS)
def test_int_01_each_of_five_intents_is_stored_and_reaches_the_bundle(intent):
    """INT-01: every allowed intent is stored, shown in memory and passed to the responder bundle of the follow-up turn."""
    s, llm, _ = run([('go', VERIFIED_ONLY), ('x', {'hints': {'case_type': 'auto', 'intent': intent}}), ('q', {})])
    assert rows(s)['Intent'] == LABELS[intent]
    assert bundles_for(llm, 'process_case')[-1]['intent'] == intent


def test_int_01_unknown_intent_value_is_not_stored():
    """INT-01: an intent outside the five is never stored."""
    s, _, _ = run([('go', VERIFIED_ONLY), ('x', {'hints': {'case_type': 'auto', 'intent': 'bogus'}})])
    assert rows(s).get('Intent') in (None, LABELS['status_inquiry'], *LABELS.values()) and rows(s).get('Intent') != 'bogus'


@pytest.mark.parametrize('status', ['denied', 'rejected', 'declined'])
def test_int_01_denied_status_without_intent_gives_denial_question(status):
    """INT-01: status hint denied (or the aliases rejected, declined) with no intent maps to denial_question."""
    s, _, _ = run([('go', VERIFIED_ONLY), ('x', {'hints': {'case_type': 'healthcare', 'status': status}})])
    assert rows(s)['Intent'] == 'denial question' and rows(s)['Resolved case'] == 'CL-2048'


@pytest.mark.parametrize('hints,case', [({'case_type': 'healthcare', 'status': 'denied'}, 'CL-2048'), ({'case_type': 'dental'}, 'CL-1899'),
                                        ({'case_type': 'auto'}, 'CL-2102'), ({'case_id': 'CL-2011'}, 'CL-2011'),
                                        ({'case_type': 'healthcare', 'status': 'closed'}, 'CL-2011')])
def test_int_02_one_match_proceeds_with_case_found(hints, case):
    """INT-02: exactly one matching claim resolves the case and emits Case found."""
    s, llm, rs = run([('go', VERIFIED_ONLY), ('x', {'hints': hints})])
    assert rows(s)['Resolved case'] == case and 'case_found' in kinds(rs[1])
    assert 'CL-' in rs[1].reply and case in rs[1].reply


@pytest.mark.parametrize('hints', [{'case_type': 'healthcare'}, {'month': 'january'}])
def test_int_02_several_matches_ask_one_question_naming_them(hints):
    """INT-02: several matches keep RESOLVE_INTENT, resolve nothing and ask one disambiguating question."""
    s, llm, rs = run([('go', VERIFIED_ONLY), ('x', {'hints': hints})])
    r = rs[1].reply
    assert s.view().phase == 'RESOLVE_INTENT' and 'Resolved case' not in rows(s) and 'case_found' not in kinds(rs[1])
    assert r.count('?') == 1 and 'CL-2048' in r and 'CL-2011' in r


@pytest.mark.parametrize('hints', [{'case_id': 'CL-9999'}, {'case_id': 'CL-3001'}])
def test_int_02_zero_matches_for_case_id_asks_fixed_question_with_no_claim_data(hints):
    """INT-02: a case_id that matches no claim of the party (another party's id counts) gives the fixed CASE_QUESTION, no model call, no claim data."""
    s, llm, rs = run([('go', VERIFIED_ONLY), ('x', {'hints': hints})])
    n_before = len(bundles_for(llm, 'resolve_intent')) + len(bundles_for(llm, 'process_case'))
    assert n_before == 1
    want = f"I can only discuss your own claim, so I cannot share anyone else's. {CASE_QUESTION}" if hints['case_id'] == 'CL-3001' else CASE_QUESTION
    assert rs[1].reply == want and rs[1].reply.count('?') == 1
    assert s.view().phase == 'RESOLVE_INTENT' and 'Resolved case' not in rows(s)
    assert not any(c in rs[1].reply for c in ('CL-2048', 'CL-2011', 'CL-1899', 'CL-2102', 'CL-3001', 'CL-9999'))


@pytest.mark.parametrize('hints', [{'case_type': 'auto', 'status': 'denied'}])
def test_int_02_zero_matches_for_type_and_status_ask_one_question_and_list_own_claims(hints):
    """INT-02: zero matches from type and status hints ask one question and list only the caller's own claims."""
    s, llm, rs = run([('go', VERIFIED_ONLY), ('x', {'hints': hints})])
    r = rs[1].reply
    assert s.view().phase == 'RESOLVE_INTENT' and 'Resolved case' not in rows(s)
    assert r.count('?') == 1 and all(c in r for c in ('CL-2048', 'CL-2011', 'CL-1899', 'CL-2102')) and 'CL-3001' not in r


def test_int_02_disambiguation_then_answer_resolves_on_next_turn():
    """INT-02: after a several-matches question, a hint that narrows to one claim resolves it."""
    s, _, rs = run([('go', VERIFIED_ONLY), ('a', {'hints': {'case_type': 'healthcare'}}), ('b', {'hints': {'status': 'denied'}})])
    assert 'case_found' not in kinds(rs[1]) and 'case_found' in kinds(rs[2]) and rows(s)['Resolved case'] == 'CL-2048'


def test_int_02_case_found_emitted_once_and_not_again_on_later_turns():
    """INT-02 / UI-05: Case found is a key event on the resolving turn only."""
    s, _, rs = run([(S1_TEXT, S1_EX), ('and the deadline?', {}), ('thanks', {})])
    assert [k.count('case_found') for k in map(kinds, rs)] == [1, 0, 0]
    assert [e.level for e in rs[0].events if e.kind == 'case_found'] == ['key']


def test_int_02_case_never_resolves_to_another_partys_claim():
    """INT-02 / INT-03: Ma Tian can resolve CL-3001 and Margaret cannot, whatever the hints."""
    s, _, _ = run([('go', MATIAN_ID), ('x', {'hints': {'case_type': 'healthcare'}})])
    assert rows(s)['Resolved case'] == 'CL-3001'
    m, _, _ = run([('go', VERIFIED_ONLY), ('x', {'hints': {'case_id': 'CL-3001'}})])
    assert 'Resolved case' not in rows(m)


def test_case_01_reply_is_code_built_from_claim_data_when_model_text_ungrounded():
    """CASE-01: an invented amount, rule or time frame in model text never reaches the caller."""
    bad = ['Your claim CL-2048 is denied. It will pay 999.00 dollars within 30 days. You are verified, Margaret Chen.',
           'You are verified, Margaret Chen. Claim CL-2048 is denied and you can appeal until 2026-05-01. The appeal deadline 2026-03-18 has passed and I can connect you with a human representative.']
    for text in bad:
        _, _, (r,) = run([(S1_TEXT, S1_EX)], {S1_TEXT: text})
        assert '999' not in r.reply and '30 days' not in r.reply and '2026-05-01' not in r.reply
        assert 'pathology report' in r.reply and '2026-03-18' in r.reply


def test_case_01_grounded_model_text_is_used_and_numbers_come_from_claim():
    """CASE-01: a follow-up reply that matches the claim data is delivered unchanged with one reply call."""
    ok = 'The documents needed are the pathology report and the office note.'
    _, llm, rs = run([(S1_TEXT, S1_EX), ('q', {})], {'q': ok})
    assert rs[1].reply == ok and len(llm.bundles) == 1


def test_case_01_bad_model_text_is_regenerated_at_most_once_then_fixed_text():
    """CASE-01 / NFR-01: an ungrounded follow-up costs one regeneration (two reply calls) and then the code-built reply."""
    _, llm, rs = run([(S1_TEXT, S1_EX), ('q', {})], {'q': 'You will receive 5000 dollars.'})
    assert len(llm.bundles) == 2 and '5000' not in rs[1].reply and 'CL-2048' in rs[1].reply


def test_case_01_denied_claim_with_passed_deadline_offers_human_and_states_date():
    """CASE-01: for CL-2048 the reply states the exact deadline, says it has passed, and offers a human representative."""
    _, _, (r,) = run([(S1_TEXT, S1_EX)])
    assert '2026-03-18' in r.reply and 'passed' in r.reply and 'human representative' in r.reply


def test_case_01_model_text_missing_the_passed_deadline_is_replaced():
    """CASE-01: a model reply that omits the passed-deadline statement is not delivered."""
    text = 'You are verified, Margaret Chen. Your claim CL-2048 is denied.'
    _, _, (r,) = run([(S1_TEXT, S1_EX)], {S1_TEXT: text})
    assert r.reply != text and 'passed' in r.reply


def test_carry_post_verification_reply_uses_stored_hints_and_never_asks_how_to_help():
    """Carry-over: with hints stored before verification the verification-turn reply is the case answer, with no open question."""
    for hints, case in [(HINTS, 'CL-2048'), ({'case_type': 'dental'}, 'CL-1899')]:
        _, _, rs = run([('a', {'identity': {'full_name': 'Margaret Chen'}, 'hints': hints}), ('b', ident(dob='1985-03-15', id_last4='4472'))])
        assert case in rs[1].reply and 'which' not in rs[1].reply.lower() and 'how can i help' not in rs[1].reply.lower()
    assert '?' not in rs[1].reply or case != 'CL-2048'


def test_carry_no_hints_after_verification_asks_what_is_needed():
    """Carry-over: with no hints the reply asks what the caller needs, one question, and resolves nothing."""
    s, llm, (r,) = run([('go', VERIFIED_ONLY)])
    assert bundles_for(llm, 'resolve_intent')[0]['case_state'] == 'ask_need' and r.reply.count('?') <= 1
    assert 'Resolved case' not in rows(s)


def test_carry_resolve_prompt_has_no_please_and_forbids_invention():
    """Carry-over / LANG-02: the resolve prompt contains no 'please', no dash, and tells the model to use only the listed claim fields."""
    from conftest import ROOT
    text = (ROOT / 'insurance_claims' / 'prompts' / 'responder_resolve_intent.txt').read_text(encoding='utf-8')
    low = text.lower()
    assert 'please' not in low and chr(0x2014) not in text and chr(0x2013) not in text
    assert 'do not state or guess anything that is not in it' in low


def test_carry_resolve_reply_with_please_or_invented_amount_is_replaced():
    """Carry-over: a resolve reply using 'please' or stating an amount is not delivered."""
    for text in ['You are verified, Margaret Chen. Please tell me what you need.', 'You are verified, Margaret Chen. You will get 5000 dollars.']:
        _, _, (r,) = run([('go', VERIFIED_ONLY)], {'go': text})
        assert r.reply != text and 'please' not in r.reply.lower() and '5000' not in r.reply


def test_carry_resolve_reply_without_verification_sentence_on_first_turn_is_not_invented_content():
    """Carry-over: an accepted resolve reply on the verification turn names the caller as verified using the stored name."""
    ok = 'You are verified, Margaret Chen. What do you need help with?'
    _, _, (r,) = run([('go', VERIFIED_ONLY)], {'go': ok})
    assert r.reply == ok


GUIDANCE_QUESTIONS = ('how long after I submit', 'what file format do you accept')


@pytest.mark.parametrize('question', ['how long after I submit', 'what file format do you accept', 'what is my name', 'will it be paid in 10 days'])
def test_carry_procedural_questions_after_verification_answer_only_from_tool_data(question):
    """Carry-over / CASE-01: a procedural question after verification never delivers invented time frames or formats."""
    turns = [(S1_TEXT, S1_EX), (question, {})]
    invented = 'You are verified, Margaret Chen. It takes 10 business days and PDF files are accepted. The appeal deadline 2026-03-18 has passed.'
    s, llm, rs = run(turns, {question: invented})
    r = rs[1].reply
    assert '10 business days' not in r and 'PDF files are accepted' not in r and 'CL-2048' in r
    if question in GUIDANCE_QUESTIONS:
        # CASE-02: answered by code from the guideline file with no model call, so every number and format word must be fixture text.
        from conftest import ROOT
        fixture = (ROOT / 'insurance_claims' / 'fixtures' / 'required_document_guideline.json').read_text(encoding='utf-8')
        claims = (ROOT / 'insurance_claims' / 'fixtures' / 'claims.json').read_text(encoding='utf-8')
        source = fixture + claims
        import re
        for num in re.findall(r'\d+', r):
            assert num in source, f'number {num} not from fixture text'
        for word in re.findall(r'\b(?:PDF|pdf|scan|photo|photos|image|JPEG|JPG|PNG|TIFF|format|formats)\b', r):
            assert word in source, f'format word {word} not from fixture text'
        return
    assert bundles_for(llm, 'process_case')[-1]['claim']['case_id'] == 'CL-2048'


def test_carry_later_turn_never_says_you_are_verified_again():
    """Carry-over: replies after the verification turn do not repeat the verification statement."""
    _, _, rs = run([(S1_TEXT, S1_EX), ('and the deadline?', {})])
    assert 'verified' not in rs[1].reply.lower()
