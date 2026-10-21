"""Off-topic replies, the human offer after MAX_OFF_TOPIC strikes, and the handoff (SCOPE-01, SCOPE-02).

All text is fixed. No model text is used for a decline, an offer, or a handoff.
"""

from insurance_claims.config import off_topic_limit
from insurance_claims.extractor import Extraction
from insurance_claims.state import Session
from insurance_claims.views import Event

DECLINES = (
    'That is outside what I can help with, since I handle insurance claim support.',
    'I can only help with insurance claims, so I cannot answer that.',
)
REDIRECT = 'What would you like to know about your claim?'
EMAIL_REDIRECT = 'For now, should I send the summary to the email on file, or skip it?'
HUMAN_OFFER = 'I cannot help with that here. Would you like me to connect you with a human representative?'
HANDOFF = 'I am connecting you with a human representative now. They will take it from here.'
NO_HUMAN = 'Understood. What would you like to know about your claim?'
NO_HUMAN_EMAIL = 'Understood. Should I send the summary to the email on file, or skip it?'
HANDOFF_AGAIN = 'A human representative has this conversation now.'
CLOSED = 'This conversation has ended. Use Reset to start a new one.'


def offer_due(session: Session) -> bool:
    """True when the strike count has reached MAX_OFF_TOPIC."""
    return session.off_topic_strikes >= off_topic_limit()


def decline_reply(session: Session, email_pending: bool) -> tuple[str, list[Event]]:
    """Return the fixed reply for an off-topic turn after verification, and any new events.

    Strikes below the limit get a polite decline and a redirect. At the limit the caller is offered
    a human representative.
    """
    if offer_due(session):
        session.human_offered = True
        session.pending_question = 'human'
        return HUMAN_OFFER, [Event(kind='handoff_offer', text='Human representative offered')]
    decline = DECLINES[session.off_topic_strikes % len(DECLINES)]
    return f'{decline} {EMAIL_REDIRECT if email_pending else REDIRECT}', []


def human_answer(session: Session, extraction: Extraction) -> str | None:
    """Read the caller's answer to an outstanding human offer: `yes`, `no`, or None (unanswered).

    Only meaningful while `pending_question` is `human`. A yes given for any other question is never
    read here, and a yes given here is never email consent.
    """
    if session.pending_question != 'human' or session.escalated:
        return None
    if extraction.wants_human or extraction.consent == 'yes':
        return 'yes'
    return 'no' if extraction.consent == 'no' else None


def decline_human(session: Session, email_open: bool) -> str:
    """The caller said no to the human offer: close that question and return to the one before it."""
    session.human_offered = False
    session.pending_question = 'email' if email_open else None
    return NO_HUMAN_EMAIL if email_open else NO_HUMAN


def escalate(session: Session) -> tuple[str, list[Event]]:
    """Hand off to a human: set the escalated flag (phase becomes ESCALATED) and return the fixed text."""
    session.escalated = True
    session.pending_question = None
    return HANDOFF, [Event(kind='handoff', text='Handed off to a human representative')]
