"""Session state, gates, and phase derivation. The UI reads `Session.view()` only."""

import uuid

from pydantic import BaseModel, Field

from insurance_claims.extractor import Emotion
from insurance_claims.views import (
    PHASE_GATES,
    PHASES,
    Event,
    SessionView,
    build_view,
)

__all__ = ['Gates', 'Session', 'Event', 'SessionView']


class Gates(BaseModel):
    """SOP progress booleans. Only code sets them."""

    verified: bool = False
    intent_set: bool = False
    case_resolved: bool = False
    case_answered: bool = False
    caller_done: bool = False
    email_offered: bool = False
    email_choice_made: bool = False


class Session(BaseModel):
    """All short-term state for one conversation. Never written to disk."""

    session_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    gates: Gates = Gates()
    escalated: bool = False
    party_id: str | None = None
    matched_factors: set[str] = set()
    failed_rounds: int = 0
    memory: dict[str, str] = {}
    intent: str | None = None
    resolved_case_id: str | None = None
    off_topic_strikes: int = 0
    resistance_count: int = 0
    emotion: Emotion = Emotion()
    email_consent: bool | None = None
    turn_count: int = 0
    turns: list[tuple[str, str]] = []
    events: list[Event] = []

    def phase_done(self, phase: str) -> bool:
        """Return True when every gate of the phase is set."""
        return all(getattr(self.gates, g) for g in PHASE_GATES[phase])

    @property
    def phase(self) -> str:
        """The derived phase: ESCALATED, the first phase not done, or COMPLETE."""
        if self.escalated:
            return 'ESCALATED'
        for name in PHASES:
            if not self.phase_done(name):
                return name
        return 'COMPLETE'

    def view(self) -> SessionView:
        """Return the data the UI may render."""
        return build_view(self)
