"""Helpers for CP1 tests. Public names, fixtures and the SessionView only."""
import json
import re

from conftest import ROOT
from insurance_claims.llm import FakeLLM
from insurance_claims.orchestrator import handle_turn, new_session

FX = ROOT / 'insurance_claims' / 'fixtures'
HOLDERS = json.loads((FX / 'policyholders.json').read_text())
CLAIMS = json.loads((FX / 'claims.json').read_text())
MARGARET, AVA, MATIAN, YAWEN = HOLDERS
LABELS = {'full_name': 'Full name', 'dob': 'Date of birth', 'phone': 'Phone', 'email': 'Email', 'id_last4': 'ID last 4'}
WORDS = {'Full name': 'full name', 'Date of birth': 'date of birth', 'Phone': 'phone number', 'Email': 'email',
         'ID last 4': 'last four of ssn'}
MISMATCH_WORDS = ('mismatch', 'incorrect', 'wrong', 'invalid')


def ident(**identity):
    """Build an extraction dict holding only identity fields."""
    return {'identity': identity}


class Rec(FakeLLM):
    """FakeLLM that records every extract view and every reply bundle for inspection."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.bundles, self.extract_views = [], []

    def extract(self, text, view, *a, **k):
        self.extract_views.append(view)
        return super().extract(text, view, *a, **k)

    def reply(self, prompt_name, bundle, *a, **k):
        self.bundles.append((prompt_name, bundle))
        return super().reply(prompt_name, bundle, *a, **k)


def play(turns, llm_cls=Rec):
    """Run turns given as (text, extraction dict). Returns (session, llm, results)."""
    llm = llm_cls(extractions={t: e for t, e in turns})
    s = new_session()
    results = [handle_turn(s, t, llm) for t, _ in turns]
    return s, llm, results


def matched(session):
    """Labels of factors the view shows as matched."""
    return {r['label'] for r in session.view().model_dump()['memory_rows'] if r['value'] == 'matched'}


def gates(session):
    """Gate states in view order."""
    return [g['done'] for p in session.view().model_dump()['phases'] for g in p['gates']]


def strings(obj):
    """Every string inside nested dicts and lists."""
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from strings(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from strings(v)


def stored_values():
    """Policyholder values and claim fields that must never leak before verification."""
    out = set()
    for h in HOLDERS:
        for k, v in h.items():
            if k in ('party_id', 'id_type'):
                continue
            out |= {str(x) for x in (v if isinstance(v, list) else [v])}
        out |= {w for w in h['name'].split() if len(w) > 2}
    for c in CLAIMS:
        for k in ('case_id', 'summary', 'denial_reason', 'appeal_deadline', 'allowed_max_amount'):
            if c.get(k) not in (None, ''):
                out.add(str(c[k]))
    return out


def leaks(text_blob):
    """Stored values found in a blob, matched as whole tokens."""
    return [v for v in stored_values() if re.search(r'(?<![\w.])' + re.escape(v) + r'(?![\w])', text_blob)]


def public_blob(session, results):
    """Replies, events, factor rows and phases. Caller turns are excluded since the caller may say anything."""
    v = session.view().model_dump()
    v.pop('turns')
    return json.dumps([v, [r.reply for r in results], [e.text for r in results for e in r.events]])


def bundle_blob(llm, phase='VERIFY_ID'):
    """Reply bundles built for a phase, without the caller_message key."""
    out = []
    for _, b in llm.bundles:
        if b.get('phase') == phase:
            out.append({k: v for k, v in b.items() if k != 'caller_message'})
    return json.dumps(out)


def failure_names_factor(results, llm=None):
    """True if any event, reply or bundle text pairs a factor label with a failure word."""
    texts = [e.text for r in results for e in r.events] + [r.reply for r in results]
    texts += [t for _, b in (llm.bundles if llm else []) for t in strings({k: v for k, v in b.items() if k not in ('caller_message', 'still_needed')})]
    fail = ('not match', 'did not', 'failed', 'wrong', 'mismatch', 'incorrect')
    return [t for t in texts if any(f in t.lower() for f in fail) and any(l.lower() in t.lower() for l in LABELS.values())]
