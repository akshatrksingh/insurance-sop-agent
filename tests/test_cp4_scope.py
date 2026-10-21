"""CP4 SCOPE-01, SCOPE-02, S5: polite decline and redirect, allowlist never strikes, human offer at the limit."""
import subprocess
import sys

import pytest

from conftest import ROOT
from cp1helpers import leaks
from cp4helpers import OFF, at_offer, kinds, say, start, strikes, verified_case
from scopephrases import IN_SCOPE, OFF_TOPIC
from templatecheck import HUMAN_OFFER

NO_IDENTITY = [t for t in IN_SCOPE if t not in ('hello, my name is Margaret Chen', 'hi, my birthday is 1985-03-15')]


def test_scope_01_s5_pre_verification_declines_redirect_without_claim_data():
    """SCOPE-01 / S5: the first two off-topic turns before verification get a polite decline and a redirect to claims, one strike each."""
    s, llm = start()
    for n in (1, 2):
        r = say(s, llm, OFF)[0]
        assert 'insurance claim' in r.reply and 'confirmed' in r.reply and 'human' not in r.reply, r.reply
        assert strikes(s) == n and kinds(r) == ['strike'] and not leaks(r.reply), r.reply
    assert s.view().phase == 'VERIFY_ID'


def test_scope_01_post_verification_declines_and_redirects_to_the_claim():
    """SCOPE-01: after verification an off-topic turn gets a decline that redirects to the claim, no phase change, no claim restatement."""
    s, llm = verified_case()
    r = say(s, llm, OFF)[0]
    assert 'insurance claim' in r.reply and 'your claim' in r.reply and 'CL-2048' not in r.reply
    assert strikes(s) == 1 and s.view().phase == 'PROCESS_CASE'


@pytest.mark.parametrize('text', OFF_TOPIC)
def test_scope_01_each_off_topic_phrase_gets_decline_and_one_strike_after_verification(text):
    """SCOPE-01: 'hello, what is RL?' and the other clearly off-topic phrases are declined with one strike after verification."""
    s, llm = verified_case({t: {'in_scope': False} for t in OFF_TOPIC})
    r = say(s, llm, text)[0]
    assert strikes(s) == 1 and 'insurance claim' in r.reply, (text, r.reply)


@pytest.mark.parametrize('in_scope', [False, True])
@pytest.mark.parametrize('text', NO_IDENTITY)
def test_scope_01_allowlist_never_strikes_after_verification(text, in_scope):
    """SCOPE-01: greetings, yes/no, consent words, hesitation, process questions and claims vocabulary never strike, whatever the extractor says."""
    s, llm = verified_case({text: {'in_scope': in_scope}})
    say(s, llm, text)
    assert strikes(s) == 0, (text, in_scope)


@pytest.mark.parametrize('text', ['1985-03-15', '4472', 'margaret@email.com', '650-521-2836'])
def test_scope_01_identity_values_never_strike_even_if_extractor_says_out_of_scope(text):
    """SCOPE-01: bare identity values before verification never earn a strike."""
    s, llm = start({text: {'in_scope': False}})
    say(s, llm, text)
    assert strikes(s) == 0


def test_scope_01_extractor_in_scope_overrides_off_topic_looking_text():
    """SCOPE-01: a strike needs the extractor to say out of scope."""
    s, llm = start({OFF: {'in_scope': True}})
    say(s, llm, OFF, OFF)
    assert strikes(s) == 0


def test_scope_02_s5_third_strike_offers_human_before_verification():
    """SCOPE-02 / S5: the third 'What is RL?' gets the fixed human offer, a key handoff_offer event, and no escalation yet."""
    s, llm = start()
    r = say(s, llm, OFF, OFF, OFF)[2]
    assert r.reply == HUMAN_OFFER and kinds(r) == ['strike', 'handoff_offer']
    assert s.view().phase == 'VERIFY_ID' and strikes(s) == 3
    assert [e.level for e in r.events if e.kind == 'handoff_offer'] == ['key']


def test_scope_02_offer_after_verification_and_strikes_are_total_not_consecutive():
    """SCOPE-02: strikes are a running total, so an in-scope turn between strikes does not reset them."""
    s, llm = verified_case()
    rs = say(s, llm, OFF, 'maybe', OFF, OFF)
    assert 'human' not in rs[0].reply and 'human' not in rs[2].reply
    assert rs[3].reply == HUMAN_OFFER and strikes(s) == 3


def test_scope_02_offer_repeats_on_each_later_strike_and_yes_hands_off():
    """SCOPE-02: later strikes repeat the offer, and the caller's yes or a request for a human ends in a handoff event and ESCALATED."""
    s, llm = start()
    rs = say(s, llm, OFF, OFF, OFF, OFF)
    assert rs[3].reply == HUMAN_OFFER
    r = say(s, llm, 'yes')[0]
    assert 'handoff' in kinds(r) and s.view().phase == 'ESCALATED'


def test_scope_02_wants_human_after_offer_hands_off():
    """SCOPE-02: once the human is offered, a caller who asks for a human is handed off with a handoff event."""
    s, llm = start()
    r = say(s, llm, OFF, OFF, OFF, 'human')[3]
    assert 'handoff' in kinds(r) and s.view().phase == 'ESCALATED'


def test_scope_02_off_topic_during_email_offer_counts_and_offer_stays_open():
    """SCOPE-02: off-topic turns while the email offer is open strike, and the third offers a human."""
    s, llm, _ = at_offer()
    rs = say(s, llm, OFF, OFF, OFF)
    assert [strikes(s)] == [3] and rs[2].reply == HUMAN_OFFER


PROBE = """
import sys
sys.path[:0] = [{root!r}, {tests!r}]
from cp4helpers import *
s, llm = verified_case()
print([('human' in r.reply) for r in say(s, llm, *([OFF] * 6))])
"""


@pytest.mark.parametrize('limit,expected', [('1', 1), ('2', 2), ('5', 5)])
def test_scope_02_max_off_topic_maps_to_the_strike_that_offers_a_human(limit, expected):
    """SCOPE-02: MAX_OFF_TOPIC=N makes the Nth off-topic turn the first to offer a human (run in a fresh process for each value)."""
    import os
    env = {**os.environ, 'MAX_OFF_TOPIC': limit}
    env.pop('LLM_API_KEY', None)
    out = subprocess.run([sys.executable, '-I', '-c', PROBE.format(root=str(ROOT), tests=str(ROOT / 'tests'))], env=env,
                         capture_output=True, text=True, timeout=60, cwd=str(ROOT))
    flags = eval(out.stdout.strip().splitlines()[-1])
    assert flags.index(True) + 1 == expected and all(flags[expected - 1:]), (flags, out.stderr[-300:])
