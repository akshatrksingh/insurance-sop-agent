"""CP1 round 4: extractor prompt anchors, new extractor fields, full name used once, 'verified' only on the verification turn."""
import re

import pytest

from conftest import ROOT
from cp1helpers import FakeLLM, Rec, ident, leaks, play
from insurance_claims.orchestrator import handle_turn, new_session

FULL = ident(full_name='Margaret Chen', dob='1985-03-15', id_last4='4472')
EXTRACTOR = (ROOT / 'insurance_claims' / 'prompts' / 'extractor.txt').read_text(encoding='utf-8')


def test_emo_01_extractor_prompt_has_the_four_intensity_anchors_and_example():
    """EMO-01: the extractor prompt defines intensity 0 to 3 anchors and gives 'Why was my claim denied?' as 0."""
    t = EXTRACTOR.lower()
    for anchor in ('neutral', 'plain question', 'mild impatience', 'explicit emotional words', 'complaints', 'strong anger', 'distress'):
        assert anchor in t, anchor
    assert re.search(r'why was my claim denied\?', t)
    example = t[t.index('why was my claim denied?') - 120: t.index('why was my claim denied?') + 120]
    assert '0' in example


def test_extractor_fields_exist_on_fake_extraction():
    """4.2: asked_about_factor and requests_protected are Extraction fields and carry their scripted values."""
    llm = FakeLLM(extractions={'t': {'asked_about_factor': 'dob', 'requests_protected': True}})
    ex = llm.extract('t', new_session().view())
    assert ex.asked_about_factor == 'dob' and ex.requests_protected is True
    assert llm.extract('unscripted', new_session().view()).requests_protected is False


def test_safe_03_unlisted_asked_about_factor_is_an_empty_extraction():
    """SAFE-03: an asked_about_factor outside the five factor names invalidates the extraction: no gate moves and a template reply follows."""
    s = new_session()
    llm = FakeLLM(extractions={'u': {'asked_about_factor': 'shoe size', **FULL}})
    r = handle_turn(s, 'u', llm)
    assert r.reply.strip() and s.view().phase == 'VERIFY_ID'


def test_extractor_schema_describes_the_two_new_fields():
    """4.2: the Extraction model schema has asked_about_factor (five names or null) and requests_protected (boolean)."""
    schema = type(FakeLLM().extract('x', new_session().view())).model_json_schema()
    props = schema['properties']
    assert props['requests_protected']['type'] == 'boolean'
    text = repr(props['asked_about_factor'])
    for name in ('full_name', 'dob', 'phone', 'email', 'id_last4', 'null'):
        assert name in text, name


def test_full_name_appears_once_at_verification_and_never_later():
    """Name rule: the bundle carries the full stored name only on the verification turn; the reply uses it once; first_name is gone."""
    class Echo(Rec):
        def reply(self, prompt_name, bundle, *a, **k):
            super().reply(prompt_name, bundle, *a, **k)
            if bundle.get('verified_this_turn'):
                return 'Thanks ' + bundle['full_name'] + ', you are verified. What do you need?'
            return 'What do you need next?'

    turns = [('a', {}), ('b', FULL), ('c', {}), ('d', {})]
    llm = Echo(extractions=dict(turns))
    s = new_session()
    replies = [handle_turn(s, t, llm).reply for t, _ in turns]
    bundles = [b for _, b in llm.bundles]
    assert len(bundles) == 3 and 'full_name' in bundles[0] and bundles[0]['verified_this_turn'] is True
    assert bundles[0]['full_name'] == 'Margaret Chen'
    assert all('full_name' not in b and b['verified_this_turn'] is False for b in bundles[1:])
    assert all('first_name' not in b for b in bundles)
    assert sum('Margaret Chen' in r for r in replies) == 1 and replies[1].count('Margaret Chen') == 1
    assert not any('Margaret' in r for r in replies[2:])


def test_no_you_are_verified_on_later_turns_when_more_identity_details_arrive():
    """Output check: 'verified' is flagged on any turn other than the verification turn, even when more identity details arrive."""
    class Liar(Rec):
        def reply(self, prompt_name, bundle, *a, **k):
            super().reply(prompt_name, bundle, *a, **k)
            return 'Thanks, you are verified. What do you need?'

    turns = [('a', FULL), ('b', ident(phone='6505212836')), ('c', ident(email='margaret@email.com'))]
    llm = Liar(extractions=dict(turns))
    s = new_session()
    replies = [handle_turn(s, t, llm).reply for t, _ in turns]
    assert re.search(r'\bverified\b', replies[0])
    assert not any(re.search(r'\bverified\b', r, re.I) for r in replies[1:]), replies
    assert leaks(' '.join(replies[1:])) == []


@pytest.mark.parametrize('text,ex', [('x', {}), ('y', ident(full_name='Margaret Chen'))])
def test_no_stored_value_or_name_in_pre_verification_replies(text, ex):
    """VER-06: no pre-verification reply holds a stored value or the party name."""
    _, _, results = play([(text, ex)])
    assert leaks(results[0].reply) == [] and 'Margaret' not in results[0].reply
