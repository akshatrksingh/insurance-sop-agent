"""Reply selection for one turn: which fixed text or model reply the caller gets, and which gates move.

Code decides every gate here. The model only phrases replies for a verified caller's case answers.
"""

from insurance_claims import handoff, other_party, postprocess, scope, tools
from insurance_claims.bundles import build_bundle
from insurance_claims.cases import CASE_QUESTION
from insurance_claims.extractor import Extraction
from insurance_claims.fields import asked_field
from insurance_claims.grounded import field_reply, first_reply
from insurance_claims.leakscan import safe_reply
from insurance_claims.llm import FakeLLM, OpenAICompatLLM
from insurance_claims.phases import mark_answered
from insurance_claims.responder import compose_reply
from insurance_claims.state import Session
from insurance_claims.config import verify_fail_limit
from insurance_claims.templates import empathy_line, verify_reply
from insurance_claims.views import EmailPreview, Event

Result = tuple[str, list[Event], EmailPreview | None]


def email_pending(session: Session, old_phase: str) -> bool:
    """True when the email offer was made on an earlier turn and no choice has been made."""
    return old_phase == 'POST_PROCESS' and session.gates.email_offered and not session.gates.email_choice_made


def _failed_round_over_limit(session: Session) -> bool:
    """True when this turn was a failed verification round and the rounds have reached MAX_VERIFY_FAILS."""
    here = len(session.turns)
    failed_now = any(e.kind == 'verify_round' and e.at == here for e in session.events)
    return failed_now and session.failed_rounds >= verify_fail_limit()


def _guided(session: Session, bundle: dict) -> tuple[str, list[Event]] | None:
    """Answer a document follow-up from the guideline file (CASE-02), or None to use the other paths.

    A cannot-obtain message (CASE-03) opens the human offer through the one pending question.
    """
    if bundle['first_answer']:
        return None
    found = tools.get_guidance(bundle['claim'], session.intent, bundle['caller_message'])
    if not found or 'error' in found or (not found['human'] and asked_field(bundle['caller_message'])):
        return None  # a single-field question keeps its own code answer
    if found['human']:
        session.human_offered = True
        session.pending_question = 'human'
    events = [Event(kind='guidance', text=f"Guidance matched: {found['topic']}", level='detail')]
    return ' '.join(found['texts']), events


def _answer(
    session: Session, message: str, verified_now: bool, llm: OpenAICompatLLM | FakeLLM
) -> tuple[str, list[Event]]:
    """Build the case or intent reply for a verified caller and mark the case answered."""
    prompt_name, bundle = build_bundle(session, message, verified_now)
    is_case = prompt_name == 'process_case'
    guided = _guided(session, bundle) if is_case else None
    if guided:
        reply, events = guided
        if empathy_line(session):
            reply = f'{empathy_line(session)} {reply}'
        mark_answered(session)
        return reply, events
    # The first claim answer and single-field answers are built by code from the bundle.
    reply = first_reply(bundle) if is_case and bundle['first_answer'] else (field_reply(bundle) if is_case else None)
    if reply is None:
        reply = compose_reply(llm, prompt_name, bundle)  # the prompt handles emotion for model text
    elif empathy_line(session):
        reply = f'{empathy_line(session)} {reply}'
    if session.phase == 'PROCESS_CASE':
        postprocess.note_topic(session, message)
    mark_answered(session)
    return reply, []


def _verified_flow(session: Session, ex: Extraction, message: str, old_phase: str, llm: OpenAICompatLLM | FakeLLM) -> Result:
    """Case answer, then the caller_done gate and the email offer once the caller is finished."""
    if session.case_hint_dropped and old_phase != 'VERIFY_ID' and not session.gates.case_resolved:
        return CASE_QUESTION, [], None
    finished = ex.wants_to_end or scope.kind(message) == 'closing'
    only_done = finished and session.phase == 'PROCESS_CASE' and session.gates.case_answered
    reply, events = ('', []) if only_done else _answer(session, message, old_phase == 'VERIFY_ID', llm)
    if finished and session.phase == 'PROCESS_CASE' and session.gates.case_answered:
        session.gates.caller_done = True
    if session.phase == 'POST_PROCESS' and not session.gates.email_offered:
        text, offer_events = postprocess.offer(session)
        events = events + offer_events
        reply = f'{reply} {text}'.strip()
    return reply, events, None


def build_reply(session: Session, ex: Extraction, message: str, old_phase: str, llm: OpenAICompatLLM | FakeLLM, complaint: bool = False
) -> Result:
    """Choose the reply for this turn, after the state update.

    Order: handoff when persuasion stops (human request, anger 3, resistance limit), answer to an open
    human offer, off-topic decline or offer, VER-07 human offer, verification templates (with the
    SAFE-05 scan), the email choice, then the case flow.

    Args:
        session: The working copy, after `update_state`. Gates may change here.
        ex: The reconciled extraction.
        message: The caller's text.
        old_phase: The phase before this turn.
        llm: Used only for model replies in the case flow.
        complaint: True for an emotion-only message the extractor called out of scope (no strike).

    Returns:
        The reply, new events, and the email preview when one was sent.
    """
    pending = email_pending(session, old_phase)
    if handoff.emotion_handoff(session, ex):  # persuasion stops: a request for a human, anger 3, or resistance
        reply, events = handoff.escalate(session)
        return reply, events, None
    answer = handoff.human_answer(session, ex, message)  # one open question at a time: a yes answers only that one
    if session.pending_question == 'human' and answer is None:
        handoff.drop_human_offer(session, pending)  # an offer is valid for the next turn only
    if answer == 'yes':
        reply, events = handoff.escalate(session)
        return reply, events, None
    if answer == 'no':
        reply = handoff.decline_human(session, pending)
        return (verify_reply(session, ex) if session.phase == 'VERIFY_ID' else reply), [], None
    if complaint and session.phase != 'VERIFY_ID':  # empathy first, then back to the claim; no gate moves
        line = empathy_line(session, 1) or ''
        return f'{line} {handoff.EMAIL_REDIRECT if pending else handoff.REDIRECT}'.strip(), [], None
    if not ex.in_scope and (handoff.offer_due(session) or session.phase != 'VERIFY_ID'):
        reply, events = handoff.decline_reply(session, pending)
        line = empathy_line(session, 1)
        reply = f'{line} {reply}' if line and not session.human_offered else reply
        return reply, events, None
    if session.phase == 'VERIFY_ID' and _failed_round_over_limit(session):
        reply, events = handoff.verify_offer(session)
        return reply, events, None
    if session.phase == 'VERIFY_ID':
        reply = verify_reply(session, ex)
        return safe_reply(reply, verify_reply(session, Extraction(requests_protected=True))), [], None
    if pending and session.pending_question == 'email':
        return postprocess.decide(session, postprocess.read_consent(ex.consent, message))
    reply, events, preview = _verified_flow(session, ex, message, old_phase, llm)
    if other_party.asks_other_party(session, ex, message):  # B38: one fixed refusal line, then the own-claim reply
        reply = other_party.with_refusal(reply)
    return reply, events, preview
