"""Off-topic replies, the human offer after MAX_OFF_TOPIC strikes, and the handoff (SCOPE-01, SCOPE-02).

All text is fixed. No model text is used for a decline, an offer, or a handoff.
"""

import re

from insurance_claims.config import off_topic_limit
from insurance_claims.extractor import Extraction
from insurance_claims.postprocess import is_decline
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
VERIFY_HUMAN_OFFER = (
    'I could not confirm your identity with those details. Would you like me to connect you with a human representative?'
)
HANDOFF_AGAIN = 'A human representative has this conversation now.'
CLOSED = 'This conversation has ended. Use Reset to start a new one.'


_YES_WORDS = ('yes', 'yeah', 'yep', 'sure', 'ok', 'okay')
AFFIRMATIVES = frozenset(
    {'go ahead', 'please do', 'connect me', 'please connect me', 'yes please'}
    | set(_YES_WORDS)
    | {f'{word} {tail}'.strip() for word in _YES_WORDS for tail in ('please', 'connect me', 'please connect me')}
)


def is_affirmative(message: str) -> bool:
    """True when the whole message is a plain yes such as "yes please" or "connect me"."""
    text = message.lower().replace('\u2019', "'").replace('\u2018', "'").replace("'", '')
    return ' '.join(re.sub(r'[^\w\s]', ' ', text).split()) in AFFIRMATIVES


RESISTANCE_LIMIT = 3  # the first resistance round plus 2 further rounds


def emotion_handoff(session: Session, extraction: Extraction) -> bool:
    """True when persuasion stops (EMO-03): an explicit request for a human in any phase, anger at
    intensity 3, or the resistance counter at its limit. Code decides, not the reply text."""
    anger = extraction.emotion.label == 'anger' and extraction.emotion.intensity >= 3
    return extraction.wants_human or anger or session.resistance_count >= RESISTANCE_LIMIT


def verify_offer(session: Session) -> tuple[str, list[Event]]:
    """Offer a human after the failed verification rounds reach MAX_VERIFY_FAILS (VER-07).
    The text names nothing that failed (VER-06)."""
    session.human_offered = True
    session.pending_question = 'human'
    return VERIFY_HUMAN_OFFER, [Event(kind='handoff_offer', text='Human representative offered')]


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


def human_answer(session: Session, extraction: Extraction, message: str = '') -> str | None:
    """Read the caller's answer to an outstanding human offer: `yes`, `no`, or None (unanswered).

    Only meaningful while `pending_question` is `human`. A yes given for any other question is never
    read here, and a yes given here is never email consent.
    """
    if session.pending_question != 'human' or session.escalated:
        return None
    if extraction.consent == 'yes' or (extraction.consent is None and is_affirmative(message)):
        return 'yes'  # the plain yes fallback covers an extractor that reports no consent
    declined = extraction.consent == 'no' or (extraction.consent is None and is_decline(message))
    return 'no' if declined else None


def drop_human_offer(session: Session, email_open: bool) -> None:
    """The caller ignored the human offer: it expires. Return to the email question if it is still open."""
    session.human_offered = False
    session.pending_question = 'email' if email_open else None


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
