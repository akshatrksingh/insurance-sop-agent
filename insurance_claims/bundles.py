"""Scoped context bundles for a verified caller (SYSTEM_DESIGN 4.3). Excluded data is never put in."""

from datetime import date

from insurance_claims import gr_text
from insurance_claims.cases import hints_of, matching_ids
from insurance_claims.data import full_name
from insurance_claims.state import Session
from insurance_claims.tools import get_claim, get_claims

EMOTION_MIN_INTENSITY = 2


def _add_common(session: Session, bundle: dict) -> None:
    """Add the greeting flag, and the emotion only when the extractor reports intensity 2 or more."""
    bundle['first_agent_turn'] = session.turn_count == 0 and not gr_text.replied(session)  # error notices do not count as a turn
    if session.emotion.intensity >= EMOTION_MIN_INTENSITY:
        bundle['emotion'] = session.emotion.model_dump()


def _resolve_bundle(session: Session, bundle: dict) -> None:
    """Fill the RESOLVE_INTENT bundle: claim summaries and the hints, no amounts or denial detail."""
    hints = hints_of(session)
    claims = get_claims(session.party_id)
    ids = matching_ids(session)
    if not hints and not session.intent:
        state = 'ask_need'
    elif session.gates.case_resolved:
        state = 'ask_intent'
        ids = [session.resolved_case_id]
    else:
        state = 'several' if len(ids) > 1 else 'none'
    bundle['case_state'] = state
    bundle['hints'] = hints
    bundle['intent'] = session.intent
    bundle['claims'] = [] if isinstance(claims, dict) else claims
    bundle['matching_case_ids'] = ids


def _process_bundle(session: Session, bundle: dict) -> None:
    """Fill the PROCESS_CASE bundle with the one resolved claim and the intent."""
    claim = get_claim(session.party_id, session.resolved_case_id)
    deadline = claim.get('appeal_deadline')
    bundle['claim'] = claim
    bundle['intent'] = session.intent
    bundle['first_answer'] = not session.gates.case_answered
    bundle['deadline_passed'] = bool(deadline) and deadline < date.today().isoformat()


def build_bundle(session: Session, caller_message: str, verified_this_turn: bool = False) -> tuple[str, dict]:
    """Build the prompt name and scoped context for a verified caller.

    Args:
        session: The current session, after the state update.
        caller_message: The caller's text, passed on for the user turn only.
        verified_this_turn: True only on the turn that completed verification.

    Returns:
        The prompt name (`resolve_intent` or `process_case`) and the bundle.
    """
    bundle = {
        'phase': session.phase,
        'verified_this_turn': verified_this_turn,
        'caller_message': caller_message,
    }
    name = full_name(session.party_id) if verified_this_turn else None
    if name:
        bundle['full_name'] = name
    _add_common(session, bundle)
    if session.phase == 'PROCESS_CASE':
        _process_bundle(session, bundle)
        return 'process_case', bundle
    _resolve_bundle(session, bundle)
    return 'resolve_intent', bundle
