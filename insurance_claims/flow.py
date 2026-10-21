"""Reply selection for one turn: which fixed text or model reply the caller gets, and which gates move.

Code decides every gate here. The model only phrases replies for a verified caller's case answers.
"""

from insurance_claims import handoff, postprocess, scope
from insurance_claims.bundles import build_bundle
from insurance_claims.cases import CASE_QUESTION
from insurance_claims.extractor import Extraction
from insurance_claims.grounded import field_reply, first_reply
from insurance_claims.leakscan import safe_reply
from insurance_claims.llm import FakeLLM, OpenAICompatLLM
from insurance_claims.phases import mark_answered
from insurance_claims.responder import compose_reply
from insurance_claims.state import Session
from insurance_claims.templates import verify_reply
from insurance_claims.views import EmailPreview, Event

Result = tuple[str, list[Event], EmailPreview | None]


def email_pending(session: Session, old_phase: str) -> bool:
    """True when the email offer was made on an earlier turn and no choice has been made."""
    return old_phase == 'POST_PROCESS' and session.gates.email_offered and not session.gates.email_choice_made


def _answer(session: Session, message: str, verified_now: bool, llm: OpenAICompatLLM | FakeLLM) -> str:
    """Build the case or intent reply for a verified caller and mark the case answered."""
    prompt_name, bundle = build_bundle(session, message, verified_now)
    if prompt_name == 'process_case' and bundle['first_answer']:
        reply = first_reply(bundle)  # the first claim answer is built by code from the bundle
    else:
        reply = (field_reply(bundle) if prompt_name == 'process_case' else None) or compose_reply(
            llm, prompt_name, bundle
        )
    if session.phase == 'PROCESS_CASE':
        postprocess.note_topic(session, message)
    mark_answered(session)
    return reply


def _verified_flow(session: Session, ex: Extraction, message: str, old_phase: str, llm: OpenAICompatLLM | FakeLLM) -> Result:
    """Case answer, then the caller_done gate and the email offer once the caller is finished."""
    if session.case_hint_dropped and old_phase != 'VERIFY_ID' and not session.gates.case_resolved:
        return CASE_QUESTION, [], None
    finished = ex.wants_to_end or scope.kind(message) == 'closing'
    only_done = finished and session.phase == 'PROCESS_CASE' and session.gates.case_answered
    reply = '' if only_done else _answer(session, message, old_phase == 'VERIFY_ID', llm)
    if finished and session.phase == 'PROCESS_CASE' and session.gates.case_answered:
        session.gates.caller_done = True
    events: list[Event] = []
    if session.phase == 'POST_PROCESS' and not session.gates.email_offered:
        text, events = postprocess.offer(session)
        reply = f'{reply} {text}'.strip()
    return reply, events, None


def build_reply(session: Session, ex: Extraction, message: str, old_phase: str, llm: OpenAICompatLLM | FakeLLM) -> Result:
    """Choose the reply for this turn, after the state update.

    Order: human handoff accepted, off-topic decline or offer, verification templates (with the
    SAFE-05 scan), the email choice, then the case flow.

    Args:
        session: The working copy, after `update_state`. Gates may change here.
        ex: The reconciled extraction.
        message: The caller's text.
        old_phase: The phase before this turn.
        llm: Used only for model replies in the case flow.

    Returns:
        The reply, new events, and the email preview when one was sent.
    """
    pending = email_pending(session, old_phase)
    answer = handoff.human_answer(session, ex)  # one open question at a time: a yes answers only that one
    if answer == 'yes':
        reply, events = handoff.escalate(session)
        return reply, events, None
    if answer == 'no':
        return handoff.decline_human(session, pending), [], None
    if pending and session.pending_question == 'human' and ex.in_scope:
        return handoff.HUMAN_OFFER, [], None  # unanswered: ask the open question again, never email
    if not ex.in_scope and (handoff.offer_due(session) or session.phase != 'VERIFY_ID'):
        reply, events = handoff.decline_reply(session, pending)
        return reply, events, None
    if session.phase == 'VERIFY_ID':
        reply = verify_reply(session, ex)
        return safe_reply(reply, verify_reply(session, Extraction(requests_protected=True))), [], None
    if pending and session.pending_question == 'email':
        return postprocess.decide(session, postprocess.read_consent(ex.consent, message))
    return _verified_flow(session, ex, message, old_phase, llm)
