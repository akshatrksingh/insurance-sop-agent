"""Per-phase logic: state updates from an extraction, and the scoped context bundles."""

from insurance_claims.data import full_name
from insurance_claims.extractor import Extraction
from insurance_claims.state import Session
from insurance_claims.verify import apply_identity
from insurance_claims.views import Event

HINT_FIELDS = ('case_type', 'status', 'month', 'case_id')
MAX_HINT_CHARS = 80
EMOTION_MIN_INTENSITY = 2


def update_state(session: Session, extraction: Extraction) -> list[Event]:
    """Store hints and emotion, then run verification. Code decides every gate.

    Hints are stored in any phase and are not used before CP2. A strike is counted when
    the (reconciled) extraction is out of scope.

    Args:
        session: Updated in place.
        extraction: The validated extractor output for this turn.

    Returns:
        The new events (also appended to `session.events`).
    """
    at = len(session.turns)
    events = []
    stored = []
    for field in HINT_FIELDS:
        value = (getattr(extraction.hints, field) or '').strip()[:MAX_HINT_CHARS]
        if value:
            session.memory[field] = value
            stored.append(field)
    if extraction.hints.intent:
        session.intent = extraction.hints.intent
        stored.append('intent')
    if stored:
        events.append(Event(kind='memory', text='Stored: ' + ', '.join(stored), level='detail'))
    if not extraction.in_scope:
        session.off_topic_strikes += 1
        events.append(Event(kind='strike', text=f'Off-topic strike {session.off_topic_strikes}', level='detail'))
    session.emotion = extraction.emotion
    if extraction.emotion.label != 'neutral':
        text = f'Emotion: {extraction.emotion.label}, {extraction.emotion.intensity}'
        events.append(Event(kind='emotion', text=text, level='detail'))
    events += apply_identity(session, extraction.identity)
    for event in events:
        event.at = at
    session.events += events
    return events


def _add_common(session: Session, bundle: dict) -> None:
    """Add the greeting flag, and the emotion only when the extractor reports intensity 2 or more."""
    bundle['first_agent_turn'] = not any(who == 'Agent' for who, _ in session.turns)
    if session.emotion.intensity >= EMOTION_MIN_INTENSITY:
        bundle['emotion'] = session.emotion.model_dump()


def build_bundle(session: Session, caller_message: str, verified_this_turn: bool = False) -> tuple[str, dict]:
    """Build the scoped context for a verified caller (SYSTEM_DESIGN 4.3).

    Claim data does not exist in any bundle yet. The full stored name is carried only on
    the verification turn. Before verification no model reply is generated at all.

    Args:
        session: The current session, after the state update.
        caller_message: The caller's text, passed on for the user turn only.
        verified_this_turn: True only on the turn that completed verification.

    Returns:
        The prompt name and the bundle.
    """
    bundle = {
        'phase': session.phase,
        'phase_goal': 'Ask what the caller needs help with.',
        'verified_this_turn': verified_this_turn,
        'caller_message': caller_message,
    }
    name = full_name(session.party_id) if verified_this_turn else None
    if name:
        bundle['full_name'] = name
    _add_common(session, bundle)
    return 'resolve_intent', bundle
