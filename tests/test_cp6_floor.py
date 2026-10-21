"""CP6 emotion floor: EMO-01, EMO-02 (Tier 1 safeguard), EMO-03 interplay. Behavior through handle_turn with a scripted FakeLLM."""
import pytest

from cp1helpers import Rec, ident, leaks, public_blob
from cp2helpers import HINTS, ID3
from insurance_claims.orchestrator import handle_turn, new_session
from templatecheck import EMPATHY, WORDS

S2 = 'I already told you who I am. This is ridiculous. Just tell me why my claim was denied.'
PHRASES = ['this is ridiculous', 'this is useless', 'this is unacceptable', 'I already told you', 'this is a joke', 'I am fed up',
           'I am sick of this', 'this is a waste of time', 'this is outrageous', 'this is unbelievable']
BENIGN = ['what is the status of my claim', 'I need to submit documents', 'thanks for your help', 'can you explain the denial',
          'I told you my name is Margaret', 'it is useful to know the deadline']
LOW = [None, ('neutral', 0), ('neutral', 1), ('frustration', 1), ('anxiety', 0)]


def emo(label, level):
    """Extraction dict with an emotion."""
    return {'emotion': {'label': label, 'intensity': level}}


def one(text, ex=None, s=None, llm=None):
    """Send one message with an optional scripted extraction. Returns (session, result)."""
    s = s or new_session()
    llm = llm or Rec(extractions={text: ex} if ex is not None else {})
    return s, handle_turn(s, text, llm)


def has_empathy(reply):
    """True when the reply starts with a fixed empathy line."""
    return any(reply.startswith(e) for e in EMPATHY)


def level(s):
    """Emotion intensity from the view."""
    return int(s.view().emotion.split(', ')[1])


@pytest.mark.parametrize('score', LOW, ids=str)
@pytest.mark.parametrize('phrase', PHRASES)
def test_emo_01_floor_phrase_raises_low_scores_to_at_least_2(phrase, score):
    """EMO-01: a floor phrase with a neutral, 0 or 1 extractor score gives an emotion event at intensity 2 or more and an empathy line."""
    s, r = one(phrase, emo(*score) if score else None)
    assert level(s) >= 2 and level(s) < 3
    assert any(e.kind == 'emotion' for e in r.events)
    assert has_empathy(r.reply), r.reply


def test_emo_02_s2_text_gets_empathy_protection_factors_no_data():
    """EMO-02 / S2: neutral 0 plus requests_protected gives empathy, protected-data wording, the allowed factors and no claim data."""
    s, r = one(S2, {**emo('neutral', 0), 'requests_protected': True})
    assert has_empathy(r.reply) and 'protected' in r.reply
    assert all(w in r.reply for w in WORDS.values())
    assert leaks(public_blob(s, [r])) == []
    assert s.view().phase == 'VERIFY_ID' and level(s) == 2


def test_emo_02_s2_text_without_protected_flag_still_gets_empathy_and_factors():
    """EMO-02 / S2: neutral 0 and requests_protected False still gives the empathy line, the factors, no claim data and no CL- text."""
    s, r = one(S2, {**emo('neutral', 0), 'requests_protected': False})
    assert has_empathy(r.reply)
    assert all(w in r.reply for w in WORDS.values())
    assert leaks(public_blob(s, [r])) == [] and 'CL-' not in r.reply
    assert s.view().phase == 'VERIFY_ID'


def test_emo_02_s2_text_with_empty_extraction():
    """EMO-02: the floor applies when the extractor returns the empty extraction."""
    s, r = one(S2)
    assert level(s) >= 2 and has_empathy(r.reply)


def test_emo_01_floor_applies_when_extractor_returns_an_empty_extraction():
    """EMO-01: an extractor that returns a freshly built empty Extraction still gets the floor."""
    class Empty(Rec):
        def extract(self, text, view, *a, **k):
            return type(super().extract('zz', view))()
    s, r = one(S2, llm=Empty())
    assert level(s) == 2 and has_empathy(r.reply)


@pytest.mark.parametrize('label, start', [('anger', 3), ('frustration', 3)])
def test_emo_01_floor_never_lowers_a_higher_score(label, start):
    """EMO-01: an existing intensity 3 stays 3 with a floor phrase and still hands off."""
    s, r = one('this is ridiculous', emo(label, start))
    assert level(s) == 3
    if label == 'anger':
        assert s.view().phase == 'ESCALATED'


def test_emo_01_floor_never_sets_3_and_2_alone_does_not_hand_off():
    """EMO-01 / EMO-03: from intensity 0 the floor gives 2, not 3, and one message does not hand off."""
    s, r = one('this is ridiculous', emo('anger', 0))
    assert level(s) == 2 and s.view().phase == 'VERIFY_ID' and not s.escalated


@pytest.mark.parametrize('text', BENIGN)
def test_emo_02_benign_controls_get_no_empathy_and_no_emotion_change(text):
    """EMO-02: ordinary messages get no empathy line and no emotion event, and the emotion stays neutral."""
    s, r = one(text)
    assert not has_empathy(r.reply)
    assert not any(e.kind == 'emotion' for e in r.events)
    assert s.view().emotion == 'neutral, 0'


def verified(extra):
    """Verified session and a recording FakeLLM scripted with extra extractions. Returns (session, llm)."""
    s = new_session()
    llm = Rec(extractions={'verify': ident(**ID3), **extra})
    handle_turn(s, 'verify', llm)
    assert s.view().phase != 'VERIFY_ID'
    return s, llm


@pytest.mark.parametrize('scored', [None, ('frustration', 2)], ids=['floor', 'extractor'])
def test_emo_02_floor_phrase_after_verification_records_emotion_and_bundle(scored):
    """EMO-02: after verification the floor records 'frustration, 2' and the responder bundle carries it, same as an extractor score of frustration 2. The empathy sentence on this model-built path relies on the prompt, not on code."""
    text = 'this is ridiculous'
    s, llm = verified({text: emo(*scored)} if scored else {})
    n = len(llm.bundles)
    r = handle_turn(s, text, llm)
    assert s.view().emotion == 'frustration, 2'
    assert any(e.kind == 'emotion' and 'frustration, 2' in e.text for e in r.events)
    assert llm.bundles[n:] and llm.bundles[-1][1]['emotion'] == {'label': 'frustration', 'intensity': 2}


@pytest.mark.parametrize('scored', [None, ('frustration', 2)], ids=['floor', 'extractor'])
def test_emo_02_code_built_reply_after_verification_has_one_fixed_empathy_line(scored):
    """EMO-02: a code-built reply after verification starts with a fixed empathy line exactly once, with the floor or an extractor score."""
    text = 'this is ridiculous, why was my claim denied'
    ex = {'hints': HINTS, 'intent': 'denial_reason'}
    s, llm = verified({text: {**ex, **(emo(*scored) if scored else {})}})
    r = handle_turn(s, text, llm)
    assert has_empathy(r.reply), r.reply
    assert sum(r.reply.count(e) for e in EMPATHY) == 1


def test_emo_03_three_floor_messages_before_identity_hand_off():
    """EMO-03: three floor phrase messages before identity reach the human handoff."""
    s = new_session()
    llm = Rec()
    for t in ('this is ridiculous', 'this is useless', 'I am fed up'):
        r = handle_turn(s, t, llm)
    assert s.view().phase == 'ESCALATED' and any(e.kind == 'handoff' for e in r.events)


def test_emo_03_identity_bearing_floor_turn_is_not_a_resistance_round():
    """EMO-03: a floor phrase message that carries an identity factor is not counted as a resistance round."""
    text = 'this is ridiculous, my name is Margaret Chen'
    s, r = one(text, ident(full_name='Margaret Chen'))
    assert s.resistance_count == 0
    assert not any(e.kind == 'resistance' for e in r.events)
