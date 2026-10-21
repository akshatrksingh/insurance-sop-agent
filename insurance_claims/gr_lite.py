"""GR-lite guardrail (SAFE-07 to SAFE-09): code-only screen run before the extractor.

A flagged message gets a fixed reply and changes nothing in the session except the transcript.
Self-harm text gets a supportive fixed reply and a human offer, and is not treated as an attack.
No model is called.
"""

from insurance_claims.allowlist import normalize
from insurance_claims import flow, handoff
from insurance_claims.gr_log import log_flag
from insurance_claims.gr_patterns import PATTERNS, SELF_HARM
from insurance_claims.gr_text import NOTICE, REFUSAL, SUPPORT
from insurance_claims.state import Session
from insurance_claims.views import Event

CLOSED_PHASES = ('ESCALATED', 'COMPLETE')


def classify(text: str) -> str | None:
    """Return the category of a flagged message, or None.

    Args:
        text: The caller's message.

    Returns:
        `self_harm`, `system_probe`, `other_data`, `harmful`, or None for a clean message.
    """
    normalized = normalize(text)
    for category, pattern in PATTERNS:
        if pattern.search(normalized):
            return category
    return None


def respond(session: Session, category: str, message: str) -> tuple[str, list[Event]] | None:
    """Log the flag and return the fixed reply and events, or None when the session is already closed.

    Only a self-harm reply touches state: it opens the human offer through the one pending question.

    Args:
        session: The working copy, updated in place only for self-harm.
        category: The category from `classify`.
        message: The caller's message (logged redacted, never stored).

    Returns:
        The reply and its events, or None for a closed session (the caller keeps its fixed closing reply).
    """
    turns = sum(1 for who, _ in session.turns if who == 'Caller')
    log_flag(session.session_id, turns, session.phase, category, message)
    if session.phase in CLOSED_PHASES:
        return None
    if category == SELF_HARM:
        session.human_offered = True
        session.pending_question = 'human'
        return SUPPORT, [Event(kind='handoff_offer', text='Human representative offered')]
    if session.pending_question == 'human':  # a self-harm offer lapses on a flagged attack, like an ignored offer
        handoff.drop_human_offer(session, flow.email_pending(session, session.phase))
    return f'{REFUSAL} {NOTICE}', [Event(kind='flagged', text='Message flagged')]
