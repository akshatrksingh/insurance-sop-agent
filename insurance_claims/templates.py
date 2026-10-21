"""Pre-verification replies. The whole reply is built from fixed templates, never model text.

Templates live in `prompts/verify_templates.json` and use only the slots {count} and {options}.
The choice is deterministic: the template index is the turn number modulo the list length.
"""

import json
import logging
from functools import lru_cache

from insurance_claims import scope
from insurance_claims.extractor import Extraction
from insurance_claims.llm import PROMPT_DIR
from insurance_claims.state import Session
from insurance_claims.verify import REQUIRED_FACTORS, supplied_factors
from insurance_claims.views import FACTORS

logger = logging.getLogger(__name__)
EMPATHY_MIN_INTENSITY = 2
NEGATIVE_LABELS = ('frustration', 'anger', 'anxiety')
OPTION_PHRASES = {
    'full_name': 'full name',
    'dob': 'date of birth',
    'phone': 'phone number',
    'email': 'email',
    'id_last4': 'last four of SSN',
}


@lru_cache(maxsize=1)
def _load() -> dict:
    """Load the template file once."""
    return json.loads((PROMPT_DIR / 'verify_templates.json').read_text(encoding='utf-8'))


def pick_situation(session: Session, extraction: Extraction) -> str:
    """Choose the situation from this turn's extraction. Priority is top to bottom.

    Args:
        session: The session, after the state update. No agent turn yet means first turn.
        extraction: What the extractor read from the caller's message.

    Returns:
        A key of the template file, or `clarify` (the factor is chosen later).
    """
    first_turn = session.turn_count == 0  # error notices do not count as a turn
    upset = _negative(extraction)
    last = session.turns[-1][1] if session.turns else ''
    closing = scope.kind(last) == 'closing'
    if extraction.refused_verification:
        return 'refusal'
    if extraction.asked_about_factor:
        return 'clarify'
    if extraction.requests_protected or scope.is_injection(last):
        return 'claim_request'
    if supplied_factors(extraction.identity):
        return 'partial'
    if not extraction.in_scope:
        return 'off_topic'
    return 'greeting' if first_turn and not upset and not closing else 'general'


def _negative(extraction: Extraction) -> bool:
    """True when the extractor reports a negative emotion at intensity 2 or higher."""
    emotion = extraction.emotion
    return emotion.label in NEGATIVE_LABELS and emotion.intensity >= EMPATHY_MIN_INTENSITY


def options_text(session: Session) -> str:
    """List the unconfirmed options, for example `a, b, or c`."""
    left = [OPTION_PHRASES[f] for f in FACTORS if f not in session.matched_factors]
    return left[0] if len(left) == 1 else ', '.join(left[:-1]) + ', or ' + left[-1]


def verify_reply(session: Session, extraction: Extraction) -> str:
    """Build the full reply for a caller who is not verified yet.

    Every template states the confirmed count and lists only the outstanding options.
    It never says which supplied item failed and never includes a stored value.

    Args:
        session: The session, after the state update.
        extraction: What the extractor read from the caller's message.

    Returns:
        The reply text.
    """
    data = _load()
    situation = pick_situation(session, extraction)
    options = data[situation]
    if situation == 'clarify':
        options = options[extraction.asked_about_factor]
    text = options[session.turn_count % len(options)]
    count = f'{min(len(session.matched_factors), REQUIRED_FACTORS)} of {REQUIRED_FACTORS}'
    text = text.replace('{count}', count).replace('{options}', options_text(session))
    if _negative(extraction):
        empathy = data['empathy']
        text = f'{empathy[session.turn_count % len(empathy)]} {text}'
    logger.info('Pre-verification reply: situation=%s (session=%s)', situation, session.session_id)
    return text


def empathy_line(session: Session, minimum: int = EMPATHY_MIN_INTENSITY) -> str | None:
    """Return a fixed empathy line when the latest emotion is negative at the minimum intensity, else None."""
    emotion = session.emotion
    if emotion.label not in NEGATIVE_LABELS or emotion.intensity < minimum:
        return None
    lines = _load()['empathy']
    return lines[session.turn_count % len(lines)]
