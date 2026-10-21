"""Identity verification: normalization and factor matching (SYSTEM_DESIGN 4.4).

This is the only module that sets `gates.verified`.
"""

import re
from datetime import datetime

from insurance_claims.data import Policyholder, find_by_policy, get_party, load_policyholders
from insurance_claims.extractor import Identity
from insurance_claims.state import Session
from insurance_claims.views import FACTOR_LABELS, FACTORS, Event

REQUIRED_FACTORS = 3
_DATE_FORMATS = (
    '%Y-%m-%d', '%Y/%m/%d', '%m/%d/%Y', '%m-%d-%Y', '%B %d %Y', '%b %d %Y', '%d %B %Y', '%d %b %Y',
)


def norm_name(value: str) -> str | None:
    """Casefold, drop punctuation, collapse spaces."""
    text = ' '.join(re.sub(r'[^\w\s]', ' ', value.casefold()).split())
    return text or None


def norm_dob(value: str) -> str | None:
    """Parse common date formats to ISO, or None."""
    text = re.sub(r'(?<=\d)(st|nd|rd|th)\b', '', value.strip(), flags=re.I).replace(',', ' ')
    text = ' '.join(text.split())
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def norm_phone(value: str) -> str | None:
    """Last 10 digits, or None when fewer than 10 digits were given."""
    digits = re.sub(r'\D', '', value)
    return digits[-10:] if len(digits) >= 10 else None


def norm_email(value: str) -> str | None:
    """Trimmed lowercase address, or None when it has no @."""
    text = value.strip().lower()
    return text if '@' in text else None


def norm_last4(value: str) -> str | None:
    """Exactly four digits, or None."""
    digits = re.sub(r'\D', '', value)
    return digits if len(digits) == 4 else None


NORMALIZERS = {
    'full_name': norm_name,
    'dob': norm_dob,
    'phone': norm_phone,
    'email': norm_email,
    'id_last4': norm_last4,
}


def _record_values(rec: Policyholder, factor: str) -> list[str]:
    """Raw stored values (with aliases) for one factor."""
    return {
        'full_name': [rec.name, *rec.name_aliases],
        'dob': [rec.dob],
        'phone': [rec.phone, *rec.phone_aliases],
        'email': [rec.email, *rec.email_aliases],
        'id_last4': [rec.id_last4],
    }[factor]


def factor_matches(rec: Policyholder, factor: str, normalized: str) -> bool:
    """Check one normalized caller value against a record.

    Args:
        rec: The policyholder record.
        factor: One of the five factor names.
        normalized: The caller value after normalization.

    Returns:
        True when it matches the stored value or an alias.
    """
    return any(NORMALIZERS[factor](v) == normalized for v in _record_values(rec, factor))


def supplied_factors(identity: Identity) -> dict[str, str]:
    """Normalize the identity fields the caller gave.

    Args:
        identity: The extractor's identity fields.

    Returns:
        Factor name to normalized value. Unusable values are dropped.
    """
    out = {}
    for factor in FACTORS:
        raw = getattr(identity, factor)
        norm = NORMALIZERS[factor](raw) if raw else None
        if norm:
            out[factor] = norm
    return out


def _choose_party(session: Session, identity: Identity, supplied: dict[str, str]) -> None:
    """Set `party_id` from the policy number, or from the best factor match."""
    by_policy = find_by_policy(identity.policy_number)
    if by_policy and by_policy.party_id != session.party_id:
        session.party_id = by_policy.party_id
        session.matched_factors = set()
    elif session.party_id is None and supplied:
        scored = [
            (sum(factor_matches(p, f, v) for f, v in supplied.items()), p)
            for p in load_policyholders()
        ]
        best, party = max(scored, key=lambda pair: pair[0])
        if best > 0:
            session.party_id = party.party_id


def apply_identity(session: Session, identity: Identity) -> list[Event]:
    """Match supplied factors, accumulate them, and set the verified gate.

    Args:
        session: Updated in place. Nothing happens once the session is verified.
        identity: What the extractor read from the caller's message.

    Returns:
        New events. Detail events carry factor names only, never values.
    """
    if session.gates.verified:
        return []
    supplied = supplied_factors(identity)
    _choose_party(session, identity, supplied)
    rec = get_party(session.party_id)
    matched = {f for f, v in supplied.items() if rec and factor_matches(rec, f, v)}
    session.matched_factors |= matched
    events = []
    if matched:
        names = ', '.join(FACTOR_LABELS[f] for f in FACTORS if f in matched)
        events.append(Event(kind='factors', text=f'Matched: {names}', level='detail'))
    if set(supplied) - matched:
        session.failed_rounds += 1
        events.append(
            Event(kind='verify_round', text=f'Round {session.failed_rounds} did not match', level='detail')
        )
    if rec and len(session.matched_factors) >= REQUIRED_FACTORS:
        session.gates.verified = True
        count = min(len(session.matched_factors), REQUIRED_FACTORS)
        events.append(Event(kind='phase_done', text=f'Verification complete, {count} of {REQUIRED_FACTORS}'))
    return events
