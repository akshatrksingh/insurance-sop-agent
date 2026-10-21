"""CP1 off-topic rule (SCOPE-01 part, VER-04): the code allowlist wins over the extractor, a strike needs both."""
import pytest

from cp1helpers import FakeLLM, ident
from insurance_claims.orchestrator import handle_turn, new_session
from scopephrases import IDENTITY_EXTRACTION, IN_SCOPE, OFF_TOPIC, PLEASANTRIES
from templatecheck import allowed, check_reply, filled, split_empathy

COUNT = {'checked': 0}
PRIORS = [[], [('p1', ident(full_name='Margaret Chen'))], [('p1', ident(full_name='Margaret Chen')), ('p2', ident(dob='1999-01-01'))]]


def play_one(text, in_scope, prior=()):
    """Play prior turns, then the text with a scripted in_scope value. Returns (session, last result)."""
    llm = FakeLLM(extractions={**dict(prior), text: {'in_scope': in_scope, 'identity': IDENTITY_EXTRACTION.get(text, {})}})
    s = new_session()
    for t, _ in prior:
        handle_turn(s, t, llm)
    return s, handle_turn(s, text, llm)


def strikes(s):
    """Off-topic strike count read from the view."""
    return int(next(r['value'] for r in s.view().model_dump()['memory_rows'] if r['label'] == 'Off-topic strikes'))


def matched_labels(s):
    """Factor labels shown as matched."""
    return {r['label'] for r in s.view().model_dump()['memory_rows'] if r['value'] == 'matched'}


def is_off_topic_template(s, reply):
    """True when the reply (without empathy) equals an off-topic template for the current state."""
    return split_empathy(reply)[1] in filled('off_topic', matched_labels(s))


def membership(s, reply, groups=None):
    """Template membership problems for the reply in the current state."""
    COUNT['checked'] += 1
    return check_reply(reply, matched_labels(s), groups_=groups)


@pytest.mark.parametrize('prior', PRIORS, ids=['t1', 't2', 't3'])
@pytest.mark.parametrize('in_scope', [False, True])
@pytest.mark.parametrize('text', IN_SCOPE)
def test_scope_01_allowlisted_text_never_gets_off_topic_template_or_strike(text, in_scope, prior):
    """SCOPE-01 / 0 strikes: greetings, goodbyes, thanks, yes/no, consent, hesitation, process questions, claim phrasing and identity values never get the off-topic template or a strike, whatever the extractor says."""
    s, r = play_one(text, in_scope, prior)
    assert strikes(s) == 0, (text, in_scope)
    assert not is_off_topic_template(s, r.reply), (text, r.reply)
    assert membership(s, r.reply) == [], r.reply


@pytest.mark.parametrize('prior', PRIORS, ids=['t1', 't2', 't3'])
@pytest.mark.parametrize('text', OFF_TOPIC)
def test_scope_01_clearly_off_topic_text_gets_template_and_exactly_one_strike(text, prior):
    """SCOPE-01: with the extractor saying out of scope, clearly off-topic text gets the off-topic template and exactly one strike; 'hello, what is RL?' counts too."""
    s, r = play_one(text, False, prior)
    assert strikes(s) == 1 and is_off_topic_template(s, r.reply), (text, r.reply)
    assert membership(s, r.reply, ['off_topic']) == []
    assert s.view().phase == 'VERIFY_ID'


@pytest.mark.parametrize('text', OFF_TOPIC)
def test_scope_01_extractor_in_scope_means_no_strike_even_for_off_topic_text(text):
    """SCOPE-01: a strike needs the extractor to say out of scope; when it says in scope there is no strike."""
    s, r = play_one(text, True)
    assert strikes(s) == 0 and not is_off_topic_template(s, r.reply)


def test_scope_01_strikes_accumulate_one_per_off_topic_turn_with_detail_event():
    """SCOPE-01: three off-topic turns give strikes 1, 2, 3 and a detail event 'Off-topic strike N' each."""
    llm = FakeLLM(extractions={t: {'in_scope': False} for t in OFF_TOPIC[:3]})
    s, seen = new_session(), []
    for n, t in enumerate(OFF_TOPIC[:3], 1):
        r = handle_turn(s, t, llm)
        seen.append((strikes(s), [e.text for e in r.events if 'strike' in e.text.lower()]))
    assert [x[0] for x in seen] == [1, 2, 3]
    assert [x[1] for x in seen] == [['Off-topic strike 1'], ['Off-topic strike 2'], ['Off-topic strike 3']]


@pytest.mark.parametrize('text', PLEASANTRIES)
@pytest.mark.parametrize('in_scope', [False, True])
def test_pleasantries_never_off_topic(text, in_scope):
    """Greeting, thanks, hesitation and process question never produce the off-topic template or a strike."""
    s, r = play_one(text, in_scope)
    assert strikes(s) == 0 and not is_off_topic_template(s, r.reply)


@pytest.mark.parametrize('in_scope', [False, True])
def test_pre_verification_hello_gets_greeting_template_and_asks_for_identity(in_scope):
    """A pre-verification 'hello' gets a greeting-group template that states 0 of 3 and lists all five options."""
    s, r = play_one('hello', in_scope)
    assert membership(s, r.reply, ['greeting']) == []
    for word in ('0 of 3 confirmed', 'full name', 'date of birth', 'phone number', 'email', 'last four of SSN'):
        assert word in r.reply


@pytest.mark.parametrize('text', ['thanks', 'goodbye', 'thank you very much', 'bye'])
def test_thanks_or_goodbye_pre_verification_gets_general_template(text):
    """Thanks or a goodbye before verification gets the general template and no strike."""
    s, r = play_one(text, False)
    assert membership(s, r.reply, ['general']) == [] and strikes(s) == 0


def test_greeting_template_only_on_first_turn():
    """The greeting template is used only on the first turn: a later 'hello' gets the general template."""
    s, r = play_one('hello', True, [('p1', ident(full_name='Margaret Chen'))])
    assert membership(s, r.reply, ['general']) == []
    assert r.reply not in allowed(matched_labels(s), ['greeting'])


def test_scope_case_count_recorded(record_property):
    """Records how many replies the scope tests checked by template membership."""
    record_property('scope_membership_checked', COUNT['checked'])
    assert COUNT['checked'] > 100
