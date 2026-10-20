"""Session state, gates, phase derivation, and the UI view."""

import uuid
from typing import Literal

from pydantic import BaseModel, Field

from insurance_claims.extractor import Emotion

PHASES = ('VERIFY_ID', 'RESOLVE_INTENT', 'PROCESS_CASE', 'POST_PROCESS')
PHASE_LABELS = {
    'VERIFY_ID': 'Verify ID',
    'RESOLVE_INTENT': 'Resolve intent',
    'PROCESS_CASE': 'Process case',
    'POST_PROCESS': 'Wrap up',
    'ESCALATED': 'Human handoff',
    'COMPLETE': 'Complete',
}
PHASE_GATES = {
    'VERIFY_ID': ('verified',),
    'RESOLVE_INTENT': ('intent_set', 'case_resolved'),
    'PROCESS_CASE': ('case_answered', 'caller_done'),
    'POST_PROCESS': ('email_offered', 'email_choice_made'),
}
GATE_LABELS = {
    'verified': 'Identity verified',
    'intent_set': 'Intent set',
    'case_resolved': 'Case resolved',
    'case_answered': 'Case answered',
    'caller_done': 'Caller done',
    'email_offered': 'Email offered',
    'email_choice_made': 'Email choice made',
}


class Gates(BaseModel):
    """SOP progress booleans. Only code sets them."""

    verified: bool = False
    intent_set: bool = False
    case_resolved: bool = False
    case_answered: bool = False
    caller_done: bool = False
    email_offered: bool = False
    email_choice_made: bool = False


class Event(BaseModel):
    """A timeline entry. Level is key (always shown) or detail (Show details only)."""

    kind: str
    text: str
    level: Literal['key', 'detail'] = 'key'


class GateView(BaseModel):
    """One gate with its ticked flag."""

    label: str
    done: bool


class PhaseView(BaseModel):
    """One phase with status and its gates."""

    name: str
    label: str
    status: Literal['pending', 'current', 'done']
    gates: list[GateView]


class MemoryRow(BaseModel):
    """One label and value row for the Session memory section."""

    label: str
    value: str


class SessionView(BaseModel):
    """The only data the UI renders."""

    phase: str
    phase_label: str
    phases: list[PhaseView]
    memory_rows: list[MemoryRow]
    turns: list[tuple[str, str]]
    events: list[Event]


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

    def _done(self, phase: str) -> bool:
        """Return True when every gate of the phase is set."""
        return all(getattr(self.gates, g) for g in PHASE_GATES[phase])

    @property
    def phase(self) -> str:
        """The derived phase: ESCALATED, the first phase not done, or COMPLETE."""
        if self.escalated:
            return 'ESCALATED'
        for name in PHASES:
            if not self._done(name):
                return name
        return 'COMPLETE'

    def view(self) -> SessionView:
        """Return the data the UI may render."""
        current = self.phase
        phases = []
        for name in PHASES:
            if self._done(name):
                status = 'done'
            elif name == current:
                status = 'current'
            else:
                status = 'pending'
            gates = [
                GateView(label=GATE_LABELS[g], done=getattr(self.gates, g))
                for g in PHASE_GATES[name]
            ]
            phases.append(
                PhaseView(name=name, label=PHASE_LABELS[name], status=status, gates=gates)
            )
        return SessionView(
            phase=current,
            phase_label=PHASE_LABELS[current],
            phases=phases,
            memory_rows=[],
            turns=list(self.turns),
            events=list(self.events),
        )
