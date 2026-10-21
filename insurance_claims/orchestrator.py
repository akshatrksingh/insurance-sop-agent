"""Turn handling: `new_session`, `handle_turn`, and `handle_choice` for the email buttons."""

import logging

from pydantic import BaseModel

from insurance_claims.emotion_floor import apply_floor
from insurance_claims.extractor import Extraction
from insurance_claims import gr_lite
from insurance_claims.flow import build_reply
from insurance_claims.handoff import CLOSED, HANDOFF_AGAIN
from insurance_claims.llm import FakeLLM, OpenAICompatLLM
from insurance_claims.config import load_settings
from insurance_claims.phases import update_state
from insurance_claims.postprocess import decide
from insurance_claims.scope import emotional_only, reconcile
from insurance_claims.state import Session
from insurance_claims.textfilter import clean_reply
from insurance_claims.turncap import CAP_NOTICE, cap_reached
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
    capped: bool = False


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


def _finish(
    session: Session, draft: Session, old_phase: str, reply: str, events: list[Event], count: bool = True
) -> str:
    """Stamp events at the reply position, append the reply, count the turn unless `count` is False, and commit.

    Every reply passes the dash filter here (LANG-01), code-built or model-built. Returns the filtered reply.
    """
    reply = clean_reply(reply)
    for event in events:
        event.at = len(draft.turns)
    draft.events += events
    draft.turns.append(('Agent', reply))
    draft.turn_count += 1 if count else 0
    _commit(session, draft, old_phase)
    return reply


def handle_turn(session: Session, text: str, llm: OpenAICompatLLM | FakeLLM) -> TurnResult:
    """Run one caller turn: extract, update state, gate, reply.

    Args:
        session: The session, updated in place.
        text: The caller's message.
        llm: An `OpenAICompatLLM` or `FakeLLM`.

    Returns:
        The reply and any new events. At the MAX_TURNS cap (NFR-08) the
        result has `capped` set and nothing changes, unless the visitor lifted the cap.
        A rejected message returns a notice and counts as no turn.
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
    if cap_reached(session, load_settings().max_turns):  # NFR-08: before any model call, flagged turns count too
        return TurnResult(reply=CAP_NOTICE, capped=True)
    draft = session.model_copy(deep=True)
    old_phase = draft.phase
    draft.turns.append(('Caller', message))
    category = gr_lite.classify(message)  # SAFE-07: decided before any model call
    flagged = gr_lite.respond(draft, category, message) if category else None
    if flagged:  # fixed reply, no state change beyond the transcript, no turn counted
        shown = _finish(session, draft, old_phase, flagged[0], flagged[1], count=False)
        return TurnResult(reply=shown, events=flagged[1])
    if old_phase in ('ESCALATED', 'COMPLETE'):
        reply = CLOSED if old_phase == 'COMPLETE' else HANDOFF_AGAIN
        return TurnResult(reply=_finish(session, draft, old_phase, reply, []))
    extraction = reconcile(_read(llm, message, session), message)
    complaint = emotional_only(extraction, message)
    if complaint:  # a feeling about the service is never an off-topic strike
        extraction = extraction.model_copy(update={'in_scope': True})
    events = update_state(draft, extraction)
    reply, more, preview = build_reply(draft, extraction, message, old_phase, llm, complaint)
    reply = _finish(session, draft, old_phase, reply, more)
    return TurnResult(reply=reply, events=events + more, email_preview=preview)


def record_failed(session: Session, text: str) -> None:
    """Keep the caller message of a failed turn in the transcript, with no reply and no state change.

    Args:
        session: The session, updated in place.
        text: The caller's message. Empty text is ignored.
    """
    message = text.strip()
    if message:
        session.turns.append(('Caller', message))


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
    draft.human_offered = False  # the click answers the email question, so no human offer stays open
    draft.pending_question = None if draft.gates.email_choice_made else 'email'
    reply = _finish(session, draft, old_phase, reply, events)
    return TurnResult(reply=reply, events=events, email_preview=preview)


def _read(llm: OpenAICompatLLM | FakeLLM, message: str, session: Session) -> Extraction:
    """Run the extractor and apply the emotion floor. Anything that is not a valid Extraction becomes an empty one."""
    try:
        extraction = Extraction.model_validate(llm.extract(message, session.view()))
    except (ValueError, TypeError) as exc:
        logger.warning('Extractor output rejected: %s (session=%s)', type(exc).__name__, session.session_id)
        extraction = Extraction()
    return apply_floor(extraction, message)
