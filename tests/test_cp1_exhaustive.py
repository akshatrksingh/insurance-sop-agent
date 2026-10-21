"""CP1 check 1 (VER-02, VER-04, VER-05, VER-06, SAFE-02): exhaustive deterministic factor scenarios."""
import itertools
import random
import re

import pytest

from cp1helpers import AVA, LABELS, MARGARET, YAWEN, Rec, failure_names_factor, ident, leaks, matched
from templatecheck import VERIFY_OFFER, WORDS, check_reply
from insurance_claims.orchestrator import handle_turn, new_session

FACTORS = list(LABELS)
WRONG2 = {'full_name': 'Someone Else', 'dob': '1971-02-02', 'phone': '6501111111', 'email': 'other@nowhere.org', 'id_last4': '1111'}
WRONG = {'full_name': 'Nobody Atall', 'dob': '1970-01-01', 'phone': '6500000000', 'email': 'nobody@nowhere.org', 'id_last4': '0000'}
VARIANTS = ['right', 'repeat', 'wrong', 'mixed', 'other', 'mixed_other']


def right_value(holder, factor, k):
    """A correct value for the holder, alternating alias forms when the record has them."""
    if factor == 'full_name':
        return ([holder['name']] + holder.get('name_aliases', []))[k % (1 + len(holder.get('name_aliases', [])))]
    if factor == 'email':
        return ([holder['email']] + holder.get('email_aliases', []))[k % (1 + len(holder.get('email_aliases', [])))]
    key = {'dob': 'dob', 'phone': 'phone', 'id_last4': 'id_last4'}[factor]
    return holder[key]


def value_for(kind, holder, other, factor, k):
    """Value of a given kind (right, wrong, other) for one factor."""
    return {'right': right_value(holder, factor, k), 'wrong': WRONG[factor], 'wrong2': WRONG2[factor], 'other': right_value(other, factor, k)}[kind]


def kinds_for(variant, n):
    """Kind of each supplied factor by position."""
    base = {'right': 'right', 'repeat': 'right', 'wrong': 'wrong', 'other': 'other'}
    if variant in base:
        return [base[variant]] * n
    return ['right' if i % 2 == 0 else ('wrong' if variant == 'mixed' else 'other') for i in range(n)]


def orders(subset):
    """Forward, reverse and two fixed-seed shuffles of a factor subset."""
    out = [list(subset), list(reversed(subset))]
    for seed in (1, 2):
        x = list(subset)
        random.Random(seed).shuffle(x)
        out.append(x)
    return out


def scenario(holder, other, variant, order, mode, alt_wrong=False):
    """Build turns as (text, extraction, items) where items are (factor, kind). alt_wrong swaps wrong values for different wrong values."""
    items = [(f, k) for f, k in zip(order, kinds_for(variant, len(order)))]
    groups = [items] if mode == 'one' else [[it] for it in items]
    if variant == 'repeat':
        groups += [items] if mode == 'one' else [[it] for it in items]
    turns = []
    for n, g in enumerate(groups):
        ident_ = {f: value_for('wrong2' if alt_wrong and k == 'wrong' else k, holder, other, f, n) for f, k in g}
        turns.append((f'turn {n}', ident(**ident_), g))
    return turns


def run(turns):
    """Play the turns with non-greeting scripted replies. Returns session, llm, results."""
    llm = Rec(extractions={t: e for t, e, _ in turns}, replies={t: 'Understood.' for t, _, _ in turns})
    s = new_session()
    return s, llm, [handle_turn(s, t, llm) for t, _, _ in turns]


def check(turns):
    """Assert one scenario against the oracle. Returns the per-turn replies."""
    llm = Rec(extractions={t: e for t, e, _ in turns}, replies={t: 'Understood.' for t, _, _ in turns})
    s, results, sets, replies, checked = new_session(), [], {'h': set(), 'o': set()}, [], 0
    for t, _, items in turns:
        results.append(handle_turn(s, t, llm))
        for f, k in items:
            if k == 'right':
                sets['h'].add(f)
            elif k == 'other':
                sets['o'].add(f)
        verified = max(len(sets['h']), len(sets['o'])) >= 3
        assert (s.view().phase != 'VERIFY_ID') is verified, (t, sets)
        rows = matched(s)
        reply = results[-1].reply
        if not verified:
            assert len(rows) == max(len(sets['h']), len(sets['o'])), (t, rows, sets)
            assert check_reply(reply, rows) == [], reply
            if reply == VERIFY_OFFER:  # VER-07: third failed round gets the fixed human offer instead of the partial template
                assert len(replies) >= 2 and not rows, (t, replies)
                replies.append(reply)
                continue
            assert items and check_reply(reply, rows, groups_=['partial']) == [], reply
            assert f'{len(rows)} of 3 confirmed' in reply, reply
            assert re.findall(r'(\d+) of (\d+)', reply) == [(str(len(rows)), '3')], reply
            for label, word in WORDS.items():
                assert (word.lower() in reply.lower()) is (label not in rows), (label, reply)
            assert not re.search(r'any three|two of those|\b[2-5] of [45]\b', reply, re.I)
            checked += 1
        replies.append(reply)
    blob = ' '.join(replies) + ' '.join(e.text for r in results for e in r.events)
    assert leaks(blob) == [] and failure_names_factor(results) == []
    return replies, s.view().phase != 'VERIFY_ID', checked


@pytest.mark.parametrize('variant', VARIANTS)
@pytest.mark.parametrize('holder,other', [(MARGARET, AVA), (YAWEN, MARGARET)], ids=['margaret', 'yawen'])
def test_exhaustive_factor_subsets_orders_and_modes(holder, other, variant, record_property):
    """VER-02 / VER-04 / VER-05 / VER-06 / SAFE-02: 31 subsets x 4 orders x 2 modes. Verified iff 3 factors match one record, count text, listed options, no leak, indistinguishable failures."""
    cases, verified_cases, member_checked = 0, 0, 0
    for size in range(1, 6):
        for subset in itertools.combinations(FACTORS, size):
            for order in orders(subset):
                for mode in ('turns', 'one'):
                    turns = scenario(holder, other, variant, order, mode)
                    replies, verified, n_checked = check(turns)
                    cases += 1
                    verified_cases += verified
                    member_checked += n_checked
                    if variant in ('wrong', 'mixed'):
                        dropped = scenario(holder, other, variant, order, mode, alt_wrong=True)
                        _, _, results = run(dropped)
                        assert [r.reply for r in results] == replies, (subset, order, mode)
    record_property('cases', cases)
    record_property('membership_checked', member_checked)
    assert cases == 31 * 4 * 2
    expected = {'wrong': lambda v: v == 0, 'right': lambda v: 0 < v < cases}
    assert expected.get(variant, lambda v: True)(verified_cases), verified_cases
    record_property('verified_cases', verified_cases)
