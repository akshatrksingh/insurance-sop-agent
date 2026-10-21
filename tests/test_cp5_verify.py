"""CP5 scenarios S2, S4, S8 and requirements VER-07, VER-06, EMO-02 (deterministic, FakeLLM)."""
import pytest

from cp1helpers import MARGARET, failure_names_factor, gates, ident, leaks, play, public_blob
from templatecheck import EMPATHY, VERIFY_OFFER, WORDS as OPTION_WORDS

HUMAN = 'human representative'
S2_TEXT = 'I already told you who I am. This is ridiculous. Just tell me why my claim was denied.'
WRONG = [ident(phone='6500000000'), ident(email='nobody@nowhere.org'), ident(dob='1999-01-01')]
MISMATCH = ('mismatch', 'incorrect', 'wrong', 'invalid', 'did not match', 'not match')


def wrong_turns(n):
    """n turns each supplying one wrong factor."""
    return [(f'w{i}', WRONG[i % 3]) for i in range(n)]


def phase(s):
    """Current phase name from the view."""
    return s.view().phase


def test_s2_angry_unverified_gets_empathy_why_options_no_data():
    """S2 / EMO-01 / EMO-02 / EMO-04 / VER-03: empathy, protection reason, allowed factors, no claim data, no skip."""
    ex = {'emotion': {'label': 'anger', 'intensity': 2}, 'requests_protected': True}
    s, llm, results = play([(S2_TEXT, ex)])
    reply = results[0].reply
    assert any(reply.startswith(e) for e in EMPATHY)
    assert 'protected' in reply
    assert all(w in reply for w in OPTION_WORDS.values())
    assert leaks(public_blob(s, results)) == []
    assert phase(s) == 'VERIFY_ID' and not any(gates(s))
    assert not any(m in reply.lower() for m in MISMATCH)


def test_s2_repeat_pressure_never_skips_verification():
    """S2 / EMO-04: repeating the demand with anger 2 until handoff never verifies and never leaks."""
    ex = {'emotion': {'label': 'anger', 'intensity': 2}, 'requests_protected': True}
    s, _, results = play([(f'{S2_TEXT} {i}', ex) for i in range(5)])
    assert leaks(public_blob(s, results)) == []
    assert phase(s) in ('VERIFY_ID', 'ESCALATED') and not any(gates(s)[:1])


def test_s4_three_wrong_rounds_offer_human_and_leak_nothing():
    """S4 / VER-07 / VER-06: round 3 gets the fixed human offer, nothing about what failed."""
    s, llm, results = play(wrong_turns(3))
    assert results[2].reply == VERIFY_OFFER and HUMAN in results[2].reply
    assert any(e.kind == 'handoff_offer' for e in results[2].events)
    assert all(r.reply != VERIFY_OFFER for r in results[:2])
    assert phase(s) == 'VERIFY_ID'
    assert failure_names_factor(results, llm) == [] and leaks(public_blob(s, results)) == []
    assert not any(v in results[2].reply.lower() for v in ('phone', 'dob', 'nobody', '6500000000', '1999'))


@pytest.mark.parametrize('affirm', [{'consent': 'yes'}, {'wants_human': True}])
def test_ver_07_yes_after_offer_escalates(affirm):
    """VER-07: a yes after the offer hands off and the phase is ESCALATED."""
    s, _, results = play(wrong_turns(3) + [('yes', affirm)])
    assert phase(s) == 'ESCALATED'
    assert 'Handed off to a human representative' in [e['text'] for e in s.view().model_dump()['events']]
    assert HUMAN in results[3].reply


def test_ver_07_no_offer_before_third_failed_round():
    """VER-07: two failed rounds do not offer a human."""
    s, _, results = play(wrong_turns(2))
    assert all(HUMAN not in r.reply for r in results) and not any(e.kind == 'handoff_offer' for r in results for e in r.events)


def test_ver_07_offer_after_valid_progress_still_counts_failures_only():
    """VER-07: a correct factor between failures keeps the count of failed rounds, replies name nothing failed (VER-06)."""
    turns = [('w0', WRONG[0]), ('ok', ident(full_name=MARGARET['name'])), ('w1', WRONG[1]), ('w2', WRONG[2])]
    s, llm, results = play(turns)
    assert failure_names_factor(results, llm) == [] and leaks(public_blob(s, results)) == []
    assert phase(s) in ('VERIFY_ID', 'ESCALATED')


def test_ver_07_bare_yes_without_offer_does_not_escalate():
    """VER-07: yes after only two failed rounds is not a handoff."""
    s, _, _ = play(wrong_turns(2) + [('yes', {'consent': 'yes'})])
    assert phase(s) == 'VERIFY_ID'


def test_ver_06_post_offer_replies_name_nothing():
    """VER-06: further failures after the offer still name nothing and leak nothing."""
    s, llm, results = play(wrong_turns(5))
    assert failure_names_factor(results, llm) == [] and leaks(public_blob(s, results)) == []


def test_s8_refuses_all_id_explains_alternatives_then_hands_off():
    """S8 / VER-04 / EMO-02 / EMO-03: rounds 1 and 2 explain and offer alternatives, round 3 hands off, never leaves VERIFY_ID before that."""
    ex = {'refused_verification': True, 'emotion': {'label': 'refusal', 'intensity': 1}}
    turns = [(f'no {i}', ex) for i in range(3)]
    s, _, results = play(turns[:1])
    s, _, results = play(turns[:2])
    for r in results:
        assert 'confirm' in r.reply and sum(w in r.reply for w in OPTION_WORDS.values()) >= 4
    assert 'protects your information' in results[0].reply
    assert phase(s) == 'VERIFY_ID' and not any(gates(s))
    s, _, results = play(turns)
    assert phase(s) == 'ESCALATED' and HUMAN in results[2].reply
    assert leaks(public_blob(s, results)) == []
    assert not any(gates(s)[:1])


def test_s8_phase_never_leaves_verify_id_except_handoff():
    """S8 / VER-04: the phase after each refusal round is VERIFY_ID until the third, then ESCALATED."""
    ex = {'refused_verification': True}
    seen = []
    for n in (1, 2, 3):
        s, _, _ = play([(f'no {i}', ex) for i in range(n)])
        seen.append(phase(s))
    assert seen == ['VERIFY_ID', 'VERIFY_ID', 'ESCALATED']
