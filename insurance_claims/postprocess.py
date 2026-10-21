"""POST_PROCESS: the email offer, consent, summary and mock send (POST-01 to POST-04).

Consent is decided here, in code, from the extractor's `consent` field or a UI button.
Only an explicit yes sends. No or skip sends nothing. Anything else asks again.
Replies are fixed text, so no stored value or claim data can reach a model.
"""

import logging
import re

from insurance_claims import tools
from insurance_claims.data import get_party
from insurance_claims.fields import asked_field
from insurance_claims.state import Session
from insurance_claims.views import EmailPreview, Event

logger = logging.getLogger(__name__)
OFFER = (
    'Before you go, I can email you a summary of this call. It covers what we discussed, the claim status, '
    'and next steps, and it goes to the email on file. Do you want me to send it, or skip it?'
)
REASK = 'I did not catch a clear answer. Should I send the summary to the email on file, or skip it?'
SENT = 'I sent the summary to the email on file. The preview is below, and that completes your call.'
SKIPPED = 'Understood. Nothing was sent, and that completes your call.'
SEND_FAILED = 'The summary could not be sent. Say yes to try again, or skip it.'
NO_SUMMARY = 'I could not build the summary. A human representative can follow up with you.'
TOPIC_LABELS = {
    'documents': 'documents needed',
    'status': 'claim status',
    'reason': 'denial reason',
    'deadline': 'appeal deadline',
    'net_pay': 'net pay',
    'expected': 'expected reimbursement',
    'allowed': 'allowed maximum',
}


DECLINE_PHRASES = frozenset({
    'no', 'no thanks', 'no thank you', 'skip', 'skip it', 'dont send it', 'do not send it', 'not now',
    'i am good', 'im good', 'no need', 'nope', 'no thanks i am good', 'no thank you i am good',
})


def is_decline(message: str) -> bool:
    """True when the whole message is a plain decline such as "no thanks" or "skip it"."""
    plain = ' '.join(re.sub(r'[^\w\s]', ' ', message.lower().replace('\u2019', "'").replace('\u2018', "'").replace("'", '')).split())
    return plain in DECLINE_PHRASES


def read_consent(consent: str | None, message: str) -> str | None:
    """Return the consent for the open email offer. A plain decline counts as no when the extractor
    returned null. This fallback never produces a yes: a send needs the extractor's explicit yes."""
    return 'no' if consent is None and is_decline(message) else consent


def note_topic(session: Session, message: str) -> None:
    """Record the claim topic an in-scope PROCESS_CASE message asked about, for the summary."""
    label = TOPIC_LABELS.get(asked_field(message) or '')
    if label and label not in session.topics:
        session.topics.append(label)


def offer(session: Session) -> tuple[str, list[Event]]:
    """Open the email offer: set the email_offered gate and return the fixed offer text."""
    session.gates.email_offered = True
    session.pending_question = 'email'
    return OFFER, [Event(kind='email_offer', text='Email summary offered', level='detail')]


def decide(session: Session, consent: str | None) -> tuple[str, list[Event], EmailPreview | None]:
    """Apply the caller's email choice. Same path for typed consent and the UI buttons.

    Args:
        session: Updated in place.
        consent: `yes`, `no`, or None (unclear).

    Returns:
        The fixed reply, new events, and the preview when an email was sent.
    """
    if consent == 'no':
        session.email_consent = False
        session.gates.email_choice_made = True
        session.pending_question = None
        return SKIPPED, [Event(kind='email_skipped', text='Skipped email summary')], None
    if consent != 'yes':
        return REASK, [], None
    session.email_consent = True
    result = _send(session)
    if 'error' in result:
        session.email_consent = None  # a retry needs a new explicit yes
        logger.warning('Email send failed: %s (session=%s)', result['error'], session.session_id)
        reply = NO_SUMMARY if result['error'] in ('NO_CASE', 'NOT_VERIFIED') else SEND_FAILED
        return reply, [Event(kind='email_failed', text='Email not sent')], None
    session.gates.email_choice_made = True
    session.pending_question = None
    preview = EmailPreview(**result)
    session.email_preview = preview
    return SENT, [Event(kind='email_sent', text='Email sent')], preview


def _send(session: Session) -> dict:
    """Guard on consent, build the summary, and send it to the email on file. Never retries."""
    if session.email_consent is not True:
        return tools.error_result('NO_CONSENT', 'Caller has not agreed to the email.', 'Ask for a clear yes or skip.')
    summary = tools.build_summary(session)
    if 'error' in summary:
        return summary
    party = get_party(session.party_id)
    try:
        return tools.send_email(party.email if party else '', summary['subject'], summary['body'])
    except Exception as exc:
        logger.warning('Email send raised %s (session=%s)', type(exc).__name__, session.session_id)
        return tools.error_result('SEND_FAILED', 'The email could not be sent.', 'Ask the caller to try again or skip.')
