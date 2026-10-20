"""Turn handling: `new_session` and `handle_turn`."""

import logging

from pydantic import BaseModel

from insurance_claims.llm import FakeLLM, OpenAICompatLLM
from insurance_claims.phases import build_bundle
from insurance_claims.responder import clean_reply
from insurance_claims.state import Event, Session

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
    """Run one caller turn: validate, build the scoped bundle, reply through the LLM.

    Args:
        session: The session, updated in place.
        text: The caller's message.
        llm: An `OpenAICompatLLM` or `FakeLLM`.

    Returns:
        The reply and any new events. A rejected message returns a notice and counts as no turn.

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
    prompt_name, bundle = build_bundle(session, message)
    reply = clean_reply(llm.reply(prompt_name, bundle))
    session.turns.append(('Caller', message))
    session.turns.append(('Agent', reply))
    session.turn_count += 1
    logger.info('Turn %d done (session=%s, phase=%s)', session.turn_count, session.session_id, session.phase)
    return TurnResult(reply=reply)
