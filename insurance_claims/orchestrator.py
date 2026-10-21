"""Turn handling: `new_session`, `handle_turn`, and `handle_choice` for the email buttons."""

import logging

from pydantic import BaseModel

from insurance_claims.extractor import Extraction
from insurance_claims.flow import build_reply
from insurance_claims.handoff import CLOSED, HANDOFF_AGAIN
from insurance_claims.llm import FakeLLM, OpenAICompatLLM
from insurance_claims.phases import update_state
from insurance_claims.postprocess import decide
from insurance_claims.scope import reconcile
from insurance_claims.state import Session
from insurance_claims.views import EmailPreview, Event

logger = logging.getLogger(__name__)
MAX_MESSAGE_CHARS = 2000
CHOICES = {'yes': 'Send summary', 'no': 'Skip'}
NO_OFFER = 'There is no email offer to answer right now.'


class TurnResult(BaseModel):
    """What one turn produced."""

    reply: str
    events: list[Event] = []
    email_preview: EmailPreview | None = None


def new_session() -> Session:
    """Return a fresh session with no gates set."""
    return Session()


def _commit(session: Session, draft: Session, old_phase: str) -> None:
    """Copy the finished working copy into the session and log the phase change."""
    for name in Session.model_fields:
        setattr(session, name, getattr(draft, name))
    if old_phase != session.phase:
        logger.info('Phase change: %s -> %s (session=%s)', old_phase, session.phase, session.session_id)
    logger.info('Turn %d done (session=%s)', session.turn_count, session.session_id)


def _finish(session: Session, draft: Session, old_phase: str, reply: str, events: list[Event]) -> None:
    """Stamp events at the reply position, append the reply, count the turn, and commit."""
    for event in events:
        event.at = len(draft.turns)
    draft.events += events
    draft.turns.append(('Agent', reply))
    draft.turn_count += 1
    _commit(session, draft, old_phase)


def handle_turn(session: Session, text: str, llm: OpenAICompatLLM | FakeLLM) -> TurnResult:
    """Run one caller turn: extract, update state, gate, reply.

    Args:
        session: The session, updated in place.
        text: The caller's message.
        llm: An `OpenAICompatLLM` or `FakeLLM`.

    Returns:
        The reply and any new events. A rejected message returns a notice and counts as no turn.
        State is committed only after the reply succeeds. After a handoff or the end of the call
        the reply is fixed and no model is called.

    Raises:
        LLMError: When the model call fails. The session is left unchanged.
    """
    message = text.strip()
    notice = None
    if not message:
        notice = 'Type a message to continue.'
    elif len(message) > MAX_MESSAGE_CHARS:
        notice = f'That message is too long. Keep it under {MAX_MESSAGE_CHARS} characters.'
    if notice:
        session.turns.append(('Agent', notice))
        return TurnResult(reply=notice)
    draft = session.model_copy(deep=True)
    old_phase = draft.phase
    draft.turns.append(('Caller', message))
    if old_phase in ('ESCALATED', 'COMPLETE'):
        reply = CLOSED if old_phase == 'COMPLETE' else HANDOFF_AGAIN
        _finish(session, draft, old_phase, reply, [])
        return TurnResult(reply=reply)
    extraction = reconcile(_read(llm, message, session), message)
    events = update_state(draft, extraction)
    reply, more, preview = build_reply(draft, extraction, message, old_phase, llm)
    _finish(session, draft, old_phase, reply, more)
    return TurnResult(reply=reply, events=events + more, email_preview=preview)


def handle_choice(session: Session, choice: str) -> TurnResult:
    """Apply an email button (`yes` for Send summary, `no` for Skip) through the same path as typed consent.

    Args:
        session: The session, updated in place.
        choice: `yes` or `no`.

    Returns:
        The reply, events, and the preview when an email was sent. When no offer is open, a notice
        and no change.
    """
    gates = session.gates
    if choice not in CHOICES or not gates.email_offered or gates.email_choice_made or session.escalated:
        return TurnResult(reply=NO_OFFER)
    draft = session.model_copy(deep=True)
    old_phase = draft.phase
    draft.turns.append(('Caller', CHOICES[choice]))
    reply, events, preview = decide(draft, choice)
    _finish(session, draft, old_phase, reply, events)
    return TurnResult(reply=reply, events=events, email_preview=preview)


def _read(llm: OpenAICompatLLM | FakeLLM, message: str, session: Session) -> Extraction:
    """Run the extractor. Anything that is not a valid Extraction becomes an empty one."""
    try:
        return Extraction.model_validate(llm.extract(message, session.view()))
    except (ValueError, TypeError) as exc:
        logger.warning('Extractor output rejected: %s (session=%s)', type(exc).__name__, session.session_id)
        return Extraction()
