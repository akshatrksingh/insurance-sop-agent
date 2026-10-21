"""Per-turn checks for the live smoke script: fixtures, leak scan, template membership and rubric."""
import json
import re

from conftest import ROOT


def load_fixture(name):
    """Load one fixture file."""
    return json.loads((ROOT / 'insurance_claims' / 'fixtures' / name).read_text())




def stored_values():
    """Policyholder and claim values that must not appear before verification."""
    out = set()
    for h in load_fixture('policyholders.json'):
        for k, v in h.items():
            if k not in ('party_id', 'id_type'):
                out |= {str(x) for x in (v if isinstance(v, list) else [v])}
        out |= {w for w in h['name'].split() if len(w) > 2}
    for c in load_fixture('claims.json'):
        out |= {str(c[k]) for k in ('case_id', 'summary', 'denial_reason', 'appeal_deadline') if c.get(k)}
    return out




def leaked(reply, values):
    """Stored values found in a reply as whole tokens."""
    return [v for v in values if re.search(r'(?<![\w.])' + re.escape(v) + r'(?![\w])', reply)]




def judge(reply, labels, verified, was_verified, made, emotion, level, values, expect):
    """Per-turn checks: membership before verification, rubric after, call counts, expected verification state."""
    from templatecheck import check_reply
    problems = []
    if verified != expect:
        problems.append(f'verified={verified} expected={expect}')
    if not verified:
        problems += check_reply(reply, labels, emotion, level)
        problems += [f'stored value in reply: {v}' for v in leaked(reply, values)]
        if made != 1:
            problems.append(f'pre-verification turn made {made} LLM calls')
        return problems
    names = [h['name'] for h in load_fixture('policyholders.json')]
    count = sum(reply.count(n) for n in names)
    if (was_verified and count) or count > 1:
        problems.append(f'full name appears {count} times, verification turn: {not was_verified}')
    if was_verified and made != 2 and made != 3:
        problems.append(f'post-verification turn made {made} LLM calls')
    return problems


def is_off_topic(reply, labels):
    """True when the reply (without an empathy line) is an off-topic template for the confirmed labels."""
    from templatecheck import filled, split_empathy
    return split_empathy(reply)[1] in filled('off_topic', labels)
