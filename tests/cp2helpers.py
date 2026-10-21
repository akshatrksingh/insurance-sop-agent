"""Helpers for CP2 tests. Public names, fixtures and the SessionView only."""
import json

from cp1helpers import Rec, ident
from insurance_claims.orchestrator import handle_turn, new_session

ID3 = {'full_name': 'Margaret Chen', 'dob': '1985-03-15', 'id_last4': '4472'}
HINTS = {'case_type': 'healthcare', 'status': 'denied', 'month': 'january'}
S1_TEXT = 'I am Margaret Chen, POL-9921, my denied healthcare claim from January, dob 1985-03-15, ssn 4472'
S1_EX = {'identity': {**ID3, 'policy_number': 'POL-9921'}, 'hints': HINTS}
VERIFIED_ONLY = ident(**ID3)
GROUNDED = ('You are verified, Margaret Chen. Your claim CL-2048 is denied because the review file did not include the '
            'pathology report and the treating provider office note. The appeal deadline 2026-03-18 has passed and '
            'I can connect you with a human representative.')
MARGARET_FALLBACK = 'Your healthcare claim CL-2048 is denied. It was denied because the review file did not include'


def run(turns, replies=None, llm_cls=Rec):
    """Play (text, extraction) turns. Returns (session, llm, results). Replies are keyed by caller text."""
    llm = llm_cls(extractions=dict(turns), replies=replies or {})
    s = new_session()
    return s, llm, [handle_turn(s, t, llm) for t, _ in turns]


def rows(s):
    """Memory rows as a label to value dict."""
    return {r['label']: r['value'] for r in s.view().model_dump()['memory_rows']}


def kinds(result):
    """Event kinds of one result in order."""
    return [e.kind for e in result.events]


def bundles_for(llm, name):
    """Reply bundles built for one prompt name."""
    return [b for n, b in llm.bundles if n == name]


def dump(obj):
    """JSON text of any bundle or view data."""
    return json.dumps(obj, default=str)
