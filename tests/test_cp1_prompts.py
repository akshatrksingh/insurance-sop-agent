"""CP1 fix rounds 2 to 4: template replies, post-verification bundle, emotion rule, greeting rule, banned words."""
import re

import pytest

from apphelpers import make_app
from cp1helpers import FakeLLM, Rec, failure_names_factor, ident, leaks, matched, play, public_blob
from conftest import ROOT
from insurance_claims.orchestrator import handle_turn, new_session
from templatecheck import TEMPLATES, WORDS, check_reply
from test_lang02 import ui_string_constants

PROMPT_DIR = ROOT / 'insurance_claims' / 'prompts'
PROMPTS = sorted(PROMPT_DIR.glob('*.txt')) + [PROMPT_DIR / 'verify_templates.json']
FULL = ident(full_name='Margaret Chen', dob='1985-03-15', id_last4='4472')
EMO = {'emotion': {'label': 'anger', 'intensity': 2}}


def after_bundles(llm):
    """Reply bundles built after verification."""
    return [b for _, b in llm.bundles if b.get('phase') != 'VERIFY_ID']


@pytest.mark.parametrize('turns', [
    [('a', {})],
    [('a', ident(full_name='Margaret Chen'))],
    [('a', ident(full_name='Margaret Chen', dob='1999-01-01'))],
    [('a', ident(full_name='Margaret Chen')), ('b', ident(phone='6500000000'))],
    [('a', {'refused_verification': True}), ('b', ident(id_last4='0000'))],
])
def test_ver_04_pre_verification_reply_states_count_and_lists_only_unconfirmed(turns):
    """VER-04 / SAFE-02: the reply is an allowed template with 'N of 3 confirmed', N equal to confirmed factors, listing exactly the unconfirmed options."""
    s, llm, results = play(turns)
    assert llm.bundles == []
    reply = results[-1].reply
    assert check_reply(reply, matched(s)) == []
    assert f'{min(len(matched(s)), 3)} of 3 confirmed' in reply
    for label, word in WORDS.items():
        assert (word in reply) is (label not in matched(s)), (label, reply)


@pytest.mark.parametrize('turns', [
    [('a', ident(full_name='Margaret Chen', dob='1999-01-01'))],
    [('a', ident(full_name='Margaret Chen')), ('b', ident(phone='6500000000', email='x@nowhere.org'))],
    [('a', {'refused_verification': True}), ('b', {'wants_human': True})],
])
def test_ver_06_replies_have_no_stored_value_or_failed_item_name(turns):
    """VER-06 / SAFE-02: across partial, wrong-factor and refused turns no reply holds a stored value, claim data or failure text naming a factor."""
    s, llm, results = play(turns)
    assert leaks(public_blob(s, results)) == [] and failure_names_factor(results, llm) == []


def test_templates_file_shape_and_slots():
    """VER-04: verify_templates.json has the eight groups, five clarify keys, only {count} and {options} slots, and states the count in every reply template."""
    assert set(TEMPLATES) == {'greeting', 'partial', 'clarify', 'refusal', 'claim_request', 'general', 'off_topic', 'empathy'}
    assert set(TEMPLATES['clarify']) == {'full_name', 'dob', 'phone', 'email', 'id_last4'}
    flat = [t for k, v in TEMPLATES.items() if k not in ('empathy', 'clarify') for t in v]
    flat += [t for v in TEMPLATES['clarify'].values() for t in v]
    for t in flat:
        assert '{count} confirmed' in t and '{options}' in t, t
        assert set(re.findall(r'\{(\w+)\}', t)) == {'count', 'options'}
    assert not any('{' in t for t in TEMPLATES['empathy'])


def test_no_verify_prompt_file_remains_since_replies_are_templates():
    """VER-04: pre-verification replies come from templates, so no verify responder prompt file exists."""
    assert not (PROMPT_DIR / 'responder_verify_id.txt').exists()


def test_emotion_key_absent_at_intensity_0_and_1_present_from_2():
    """EMO-01 (bundle): the post-verification bundle has no emotion key at intensity 0 and 1 and has it at 2 and 3."""
    for level, present in ((0, False), (1, False), (2, True), (3, True)):
        _, llm, _ = play([('a', {**FULL, 'emotion': {'label': 'frustration', 'intensity': level}})])
        assert ('emotion' in after_bundles(llm)[0]) is present, level


def test_emotion_key_rule_holds_in_post_verification_bundle():
    """EMO-01 (bundle): intensity 2 is carried with its label; no emotion data means no key."""
    _, llm, _ = play([('a', {**FULL, **EMO})])
    assert after_bundles(llm)[-1]['emotion']['intensity'] == 2
    _, llm, _ = play([('a', FULL)])
    assert 'emotion' not in after_bundles(llm)[-1]


TIME_GREETINGS = ('good morning', 'good afternoon', 'good evening')


def test_lang_02_no_time_of_day_greeting_in_prompts_templates_or_ui_strings():
    """LANG-02 / greeting: no 'good morning', 'good afternoon' or 'good evening' in any prompt file, template file or UI string."""
    bad = [f'{p.name}:{i}' for p in PROMPTS for i, l in enumerate(p.read_text(encoding='utf-8').splitlines(), 1)
           if any(g in l.lower() for g in TIME_GREETINGS)]
    bad += [f'{f}:{ln}' for f, ln, t in ui_string_constants() if any(g in t.lower() for g in TIME_GREETINGS)]
    assert not bad, bad


def test_lang_02_no_please_in_prompts_templates_ui_strings_and_fake_default_replies():
    """LANG-02: the word 'please' (any case) is absent from prompts, templates, UI strings and FakeLLM default replies."""
    rx = re.compile(r'\bplease\b', re.I)
    bad = [f'{p.name}:{i}' for p in PROMPTS for i, l in enumerate(p.read_text(encoding='utf-8').splitlines(), 1) if rx.search(l)]
    bad += [f'{f}:{ln}' for f, ln, t in ui_string_constants() if rx.search(t)]
    fake = FakeLLM()
    for name in ('resolve_intent', 'process_case', 'post_process', 'anything'):
        if rx.search(fake.reply(name, {'phase': 'RESOLVE_INTENT'})):
            bad.append(f'FakeLLM.reply({name})')
    assert not bad, bad


def test_greeting_first_agent_turn_true_only_when_no_agent_turn_exists():
    """Greeting: first_agent_turn is true when verification is the first agent turn and false after template replies."""
    _, llm, _ = play([('a', FULL)])
    assert [b['first_agent_turn'] for b in after_bundles(llm)] == [True]
    llm = Rec(extractions={'b': FULL}, replies={'b': 'Understood.'})
    s = new_session()
    for text in ('a', 'b'):
        handle_turn(s, text, llm)
    assert [b['first_agent_turn'] for b in after_bundles(llm)] == [False]


def test_greeting_first_agent_turn_stays_true_after_failed_turn_without_agent_reply():
    """Greeting: a failed turn that produced no agent reply leaves first_agent_turn true on the next turn."""
    seen = []

    class FlakyReply(Rec):
        def reply(self, prompt_name, bundle, *a, **k):
            seen.append(bundle['first_agent_turn'])
            if len(seen) == 1:
                raise RuntimeError('boom')
            return super().reply(prompt_name, bundle, *a, **k)

    s, llm = new_session(), FlakyReply(extractions={'first': FULL, 'third': {}}, replies={'first': 'Understood.', 'third': 'Understood.'})
    with pytest.raises(RuntimeError):
        handle_turn(s, 'first', llm)
    assert not any(role == 'Agent' for role, _ in s.view().turns)
    handle_turn(s, 'first', llm)
    handle_turn(s, 'third', llm)
    assert seen == [True, True, False]


def test_greeting_resolve_intent_prompt_ties_greeting_to_first_agent_turn():
    """Greeting: the responder prompt ties greeting to first_agent_turn and forbids greeting otherwise."""
    t = (PROMPT_DIR / 'responder_resolve_intent.txt').read_text(encoding='utf-8').lower()
    assert 'first_agent_turn' in t and re.search(r'(do not greet|never greet|no greeting)', t)


def test_ui_try_select_box_label_is_demo_identities():
    """UI-08: the Try select box label is 'Demo identities'."""
    boxes = list(make_app().run().sidebar.selectbox)
    assert len(boxes) == 1 and boxes[0].label == 'Demo identities'
