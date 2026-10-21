"""Turn handling: `new_session` and `handle_turn`."""

import logging

from pydantic import BaseModel

from insurance_claims.llm import FakeLLM, OpenAICompatLLM
from insurance_claims.extractor import Extraction
from insurance_claims.bundles import build_bundle
from insurance_claims.cases import CASE_QUESTION
from insurance_claims.grounded import field_reply, first_reply
from insurance_claims.phases import mark_answered, update_state
from insurance_claims.responder import compose_reply
from insurance_claims.scope import reconcile
from insurance_claims.templates import verify_reply
from insurance_claims.state import Session
from insurance_claims.views import Event

logger = logging.getLogger(__name__)
MAX_MESSAGE_CHARS = 2000


class EmailPreview(BaseModel):
    """The mock email shown in the UI. Used from CP4."""

    to: str
    subject: str
    body: str


class TurnResult(BaseModel):
    """What one turn produced."""

    reply: str
    events: list[Event] = []
    email_preview: EmailPreview | None = None


def new_session() -> Session:
    """Return a fresh session with no gates set."""
    return Session()


def handle_turn(session: Session, text: str, llm: OpenAICompatLLM | FakeLLM) -> TurnResult:
    """Run one caller turn: extract, update state, gate, reply.

    Args:
        session: The session, updated in place.
        text: The caller's message.
        llm: An `OpenAICompatLLM` or `FakeLLM`.

    Returns:
        The reply and any new events. A rejected message returns a notice and counts as no turn.
        State is committed only after the reply succeeds.

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
    extraction = reconcile(_read(llm, message, draft), message)
    draft.turns.append(('Caller', message))
    old_phase = draft.phase
    events = update_state(draft, extraction)
    if draft.phase == 'VERIFY_ID':
        reply = verify_reply(draft, extraction)
    elif draft.case_hint_dropped and old_phase != 'VERIFY_ID' and not draft.gates.case_resolved:
        reply = CASE_QUESTION
    else:
        verified_this_turn = old_phase == 'VERIFY_ID'
        prompt_name, bundle = build_bundle(draft, message, verified_this_turn)
        if prompt_name == 'process_case' and bundle['first_answer']:
            reply = first_reply(bundle)  # the first claim answer is built by code from the bundle
        else:
            reply = (field_reply(bundle) if prompt_name == 'process_case' else None) or compose_reply(
                llm, prompt_name, bundle
            )
        mark_answered(draft)
    draft.turns.append(('Agent', reply))
    draft.turn_count += 1
    for name in Session.model_fields:
        setattr(session, name, getattr(draft, name))
    if old_phase != session.phase:
        logger.info('Phase change: %s -> %s (session=%s)', old_phase, session.phase, session.session_id)
    logger.info('Turn %d done (session=%s)', session.turn_count, session.session_id)
    return TurnResult(reply=reply, events=events)


def _read(llm: OpenAICompatLLM | FakeLLM, message: str, session: Session) -> Extraction:
    """Run the extractor. Anything that is not a valid Extraction becomes an empty one."""
    try:
        return Extraction.model_validate(llm.extract(message, session.view()))
    except (ValueError, TypeError) as exc:
        logger.warning('Extractor output rejected: %s (session=%s)', type(exc).__name__, session.session_id)
        return Extraction()
