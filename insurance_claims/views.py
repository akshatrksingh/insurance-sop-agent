"""View models and constants shared by state and the UI. `build_view` makes `SessionView`."""

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel

if TYPE_CHECKING:
    from insurance_claims.state import Session

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
FACTORS = ('full_name', 'dob', 'phone', 'email', 'id_last4')
FACTOR_LABELS = {
    'full_name': 'Full name',
    'dob': 'Date of birth',
    'phone': 'Phone',
    'email': 'Email',
    'id_last4': 'ID last 4',
}
HINT_LABELS = {
    'case_type': 'Claim type',
    'status': 'Status',
    'month': 'Month',
    'case_id': 'Case id',
}


class Event(BaseModel):
    """A timeline entry. Level is key (always shown) or detail (Show details only).

    `at` is the transcript position (number of turns before it) where the row belongs.
    """

    kind: str
    text: str
    level: Literal['key', 'detail'] = 'key'
    at: int | None = None


class EmailPreview(BaseModel):
    """The mock email shown in the UI. `to` is the preview recipient, the only place the address appears."""

    to: str
    subject: str
    body: str


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
    tone: Literal['', 'good', 'warn'] = ''


class SessionView(BaseModel):
    """The only data the UI renders."""

    phase: str
    phase_label: str
    phases: list[PhaseView]
    memory_rows: list[MemoryRow]
    turns: list[tuple[str, str]]
    events: list[Event]
    extracted_fields: list[str] = []
    email_offer_open: bool = False
    email_preview: EmailPreview | None = None


def _memory_rows(session: 'Session') -> list[MemoryRow]:
    """Build the Session memory rows. Factor names only, never stored values."""
    rows = []
    for factor in FACTORS:
        hit = factor in session.matched_factors
        rows.append(
            MemoryRow(
                label=FACTOR_LABELS[factor],
                value='matched' if hit else 'pending',
                tone='good' if hit else 'warn',
            )
        )
    for key, label in HINT_LABELS.items():
        if session.memory.get(key):
            rows.append(MemoryRow(label=label, value=session.memory[key]))
    if session.intent:
        rows.append(MemoryRow(label='Intent', value=session.intent.replace('_', ' ')))
    if session.gates.verified and session.resolved_case_id:
        rows.append(MemoryRow(label='Resolved case', value=session.resolved_case_id))
    consent = {None: 'not asked', True: 'yes', False: 'no'}[session.email_consent]
    rows.append(MemoryRow(label='Email consent', value=consent))
    rows.append(MemoryRow(label='Failed verification rounds', value=str(session.failed_rounds)))
    rows.append(MemoryRow(label='Off-topic strikes', value=str(session.off_topic_strikes)))
    rows.append(MemoryRow(label='Resistance rounds', value=str(session.resistance_count)))
    return rows


def _offer_open(session: 'Session') -> bool:
    """True while the email offer waits for a choice."""
    gates = session.gates
    return gates.email_offered and not gates.email_choice_made and not session.escalated


def build_view(session: 'Session') -> SessionView:
    """Return the data the UI may render for this session."""
    current = session.phase
    phases = []
    for name in PHASES:
        if session.phase_done(name):
            status = 'done'
        elif name == current:
            status = 'current'
        else:
            status = 'pending'
        gates = [
            GateView(label=GATE_LABELS[g], done=getattr(session.gates, g))
            for g in PHASE_GATES[name]
        ]
        phases.append(PhaseView(name=name, label=PHASE_LABELS[name], status=status, gates=gates))
    return SessionView(
        phase=current,
        phase_label=PHASE_LABELS[current],
        phases=phases,
        memory_rows=_memory_rows(session),
        turns=list(session.turns),
        events=list(session.events),
        extracted_fields=list(session.extracted_fields),
        email_offer_open=_offer_open(session),
        email_preview=session.email_preview,
    )
