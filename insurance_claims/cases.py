"""Case resolution: filter the verified party's claims with the stored hints (INT-02)."""

import re

from insurance_claims.state import Session
from insurance_claims.tools import get_claim, get_claims
from insurance_claims.views import Event

MONTHS = (
    'january', 'february', 'march', 'april', 'may', 'june',
    'july', 'august', 'september', 'october', 'november', 'december',
)
CASE_QUESTION = 'Which case is this about? You can give me the case ID, or the type of claim and about when it was filed.'
STATUS_ALIASES = {'rejected': 'denied', 'declined': 'denied'}


def _month_year(text: str) -> tuple[int | None, int | None]:
    """Read a month number and optional year from a hint such as 'January' or '2026-01'."""
    low = text.casefold()
    year = re.search(r'\b(\d{4})\b', low)
    year_value = int(year.group(1)) if year else None
    for number, name in enumerate(MONTHS, start=1):
        if re.search(rf'\b{name[:3]}[a-z]*', low):
            return number, year_value
    pair = re.search(r'\b\d{4}[-/](\d{1,2})\b', low) or re.fullmatch(r'\s*(\d{1,2})\s*', low)
    return (int(pair.group(1)), year_value) if pair else (None, year_value)


def _fits(claim: dict, hints: dict[str, str]) -> bool:
    """Return True when the claim satisfies every stored hint."""
    if 'case_id' in hints and claim['case_id'].casefold() != hints['case_id'].strip().casefold():
        return False
    if 'case_type' in hints and claim['case_type'].casefold() not in hints['case_type'].casefold():
        return False
    if 'status' in hints:
        wanted = STATUS_ALIASES.get(hints['status'].strip().casefold(), hints['status'].strip().casefold())
        if claim['status'].casefold() != wanted:
            return False
    if 'month' in hints:
        month, year = _month_year(hints['month'])
        created = claim['created_at']
        if month is None or int(created[5:7]) != month or (year and int(created[:4]) != year):
            return False
    return True


def hints_of(session: Session) -> dict[str, str]:
    """Return the non-empty case hints stored in memory."""
    return {k: v for k, v in session.memory.items() if v}


def matching_ids(session: Session) -> list[str]:
    """Return the case ids of the party's claims that fit the stored hints."""
    claims = get_claims(session.party_id)
    if isinstance(claims, dict):
        return []
    hints = hints_of(session)
    return [c['case_id'] for c in claims if _fits(c, hints)]


def _drop_stale_case_hint(session: Session) -> bool:
    """Drop a stored case_id hint that matches none of the verified party's claims. Return True if dropped."""
    wanted = session.memory.get('case_id', '').strip().casefold()
    claims = get_claims(session.party_id)
    if not wanted or isinstance(claims, dict) or any(c['case_id'].casefold() == wanted for c in claims):
        return False
    del session.memory['case_id']
    return True


def advance(session: Session) -> list[Event]:
    """After verification, set the intent gate and try to resolve the case from the hints.

    Resolution runs only when a hint or an intent is stored. One match resolves the case.
    Zero or several leave it open for a disambiguating question. Code sets the gates.

    Args:
        session: Updated in place.

    Returns:
        New events: tool calls (detail) and "Case found" (key). The caller stamps `at`.
    """
    events: list[Event] = []
    gates = session.gates
    if not gates.verified:
        return events
    session.case_hint_dropped = False
    if not gates.case_resolved and _drop_stale_case_hint(session):
        session.case_hint_dropped = True
        events.append(Event(kind='memory', text='Dropped: case_id (no such claim)', level='detail'))
    hints = hints_of(session)
    if not gates.case_resolved and (hints or session.intent):
        events.append(Event(kind='tool', text='Tool called: get_claims', level='detail'))
        ids = matching_ids(session)
        if len(ids) == 1:
            claim = get_claim(session.party_id, ids[0])
            events.append(Event(kind='tool', text=f'Tool called: get_claim {ids[0]}', level='detail'))
            if 'error' not in claim:
                session.resolved_case_id = ids[0]
                gates.case_resolved = True
                events.append(Event(kind='case_found', text=f'Case found: {ids[0]}'))
        else:
            events.append(Event(kind='tool', text=f'Claims matching the hints: {len(ids)}', level='detail'))
    if gates.case_resolved and not session.intent:
        status = STATUS_ALIASES.get(hints.get('status', '').casefold(), hints.get('status', '').casefold())
        if status == 'denied':
            session.intent = 'denial_question'
    if session.intent:
        gates.intent_set = True
    return events
