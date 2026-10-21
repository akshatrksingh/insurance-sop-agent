"""Helpers for CP4 tests (scope, email offer, consent). Public names, fixtures and the SessionView only."""
from cp1helpers import Rec
from cp2helpers import S1_EX, S1_TEXT
from insurance_claims.orchestrator import handle_turn, new_session

OFF = 'what is RL?'
DONE = 'bye'
EXTRACTIONS = {S1_TEXT: S1_EX, OFF: {'in_scope': False}, DONE: {'wants_to_end': True}, 'hello, what is RL?': {'in_scope': False},
               'yes': {'consent': 'yes'}, 'no': {'consent': 'no'}, 'skip': {'consent': 'no'}, 'send it': {'consent': 'yes'},
               'maybe': {}, 'hmm': {}, 'deadline?': {}, 'human': {'wants_human': True}}


def start(extra=None, llm_cls=Rec):
    """New session, LLM scripted with EXTRACTIONS plus extra. Returns (session, llm)."""
    return new_session(), llm_cls(extractions={**EXTRACTIONS, **(extra or {})}, replies={})


def say(s, llm, *texts):
    """Play texts in order and return the list of TurnResults."""
    return [handle_turn(s, t, llm) for t in texts]


def verified_case(extra=None):
    """Session that is verified with the case answered (Margaret, CL-2048), no email offer yet."""
    s, llm = start(extra)
    say(s, llm, S1_TEXT)
    return s, llm


def at_offer(extra=None):
    """Session with the case answered, caller done, and the email offer open. Returns (session, llm, offer result)."""
    s, llm = verified_case(extra)
    return s, llm, say(s, llm, DONE)[0]


def strikes(s):
    """Off-topic strike count from the view."""
    return int(next(r['value'] for r in s.view().model_dump()['memory_rows'] if r['label'] == 'Off-topic strikes'))


def kinds(r):
    """Event kinds of one result."""
    return [e.kind for e in r.events]


def all_kinds(s):
    """Event kinds of the whole session."""
    return [e['kind'] for e in s.view().model_dump()['events']]
