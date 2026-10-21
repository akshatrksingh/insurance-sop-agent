"""Per-phase logic: state updates from an extraction."""

from insurance_claims.cases import advance
from insurance_claims.extractor import Extraction
from insurance_claims.state import Session
from insurance_claims.verify import apply_identity
from insurance_claims.views import Event

HINT_FIELDS = ('case_type', 'status', 'month', 'case_id')
MAX_HINT_CHARS = 80


def field_names(extraction: Extraction) -> list[str]:
    """Return the names (never values) of the extractor fields that were filled this turn."""
    names = []
    for group in ('identity', 'hints'):
        for key, value in getattr(extraction, group).model_dump().items():
            if value:
                names.append(f'{group}.{key}')
    if not extraction.in_scope:
        names.append('out_of_scope')
    for key in ('wants_human', 'refused_verification', 'wants_to_end', 'requests_protected'):
        if getattr(extraction, key):
            names.append(key)
    for key in ('consent', 'asked_about_factor'):
        if getattr(extraction, key):
            names.append(key)
    if extraction.emotion.label != 'neutral':
        names.append('emotion')
    return names


def mark_answered(session: Session) -> None:
    """Set the case_answered gate after a grounded answer was given in PROCESS_CASE."""
    if session.phase == 'PROCESS_CASE':
        session.gates.case_answered = True


def _resists(session: Session, extraction: Extraction) -> bool:
    """True when this turn pushes back on a gate: a refusal, or negative emotion before verification
    with no identity given. Counted by code from the extraction (EMO-03)."""
    emotion = extraction.emotion  # runs after apply_identity: a turn that verifies is never resistance
    if extraction.refused_verification or emotion.label == 'refusal':
        return not session.gates.verified
    gave_identity = any(extraction.identity.model_dump().values())
    upset = emotion.label in ('frustration', 'anger', 'anxiety') and emotion.intensity >= 2
    return upset and not session.gates.verified and not gave_identity


def update_state(session: Session, extraction: Extraction) -> list[Event]:
    """Store hints and emotion, then run verification. Code decides every gate.

    Hints are stored in any phase. After verification they resolve the case. A strike is counted when
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
    if _resists(session, extraction):
        session.resistance_count += 1
        events.append(Event(kind='resistance', text=f'Resistance round {session.resistance_count}', level='detail'))
    session.extracted_fields = field_names(extraction)
    events += advance(session)
    for event in events:
        event.at = at
    session.events += events
    return events
