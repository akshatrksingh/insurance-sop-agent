"""Fixture loading: policyholder records and lookups. Read-only."""

import json
import re
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

FIXTURES = Path(__file__).parent / 'fixtures'


class Policyholder(BaseModel):
    """One policyholder record. Stored values never leave the harness."""

    party_id: str
    name: str
    name_aliases: list[str] = []
    policy_number: str
    dob: str
    id_type: str
    id_last4: str
    phone: str
    phone_aliases: list[str] = []
    email: str
    email_aliases: list[str] = []


@lru_cache(maxsize=1)
def load_policyholders() -> tuple[Policyholder, ...]:
    """Load all policyholder records from the fixture file."""
    raw = json.loads((FIXTURES / 'policyholders.json').read_text(encoding='utf-8'))
    return tuple(Policyholder(**item) for item in raw)


def get_party(party_id: str | None) -> Policyholder | None:
    """Return the record for a party id, or None."""
    return next((p for p in load_policyholders() if p.party_id == party_id), None)


def find_by_policy(policy_number: str | None) -> Policyholder | None:
    """Return the record for a policy number (compared on digits), or None."""
    digits = re.sub(r'\D', '', policy_number or '')
    if not digits:
        return None
    return next(
        (p for p in load_policyholders() if re.sub(r'\D', '', p.policy_number) == digits), None
    )


def full_name(party_id: str | None) -> str | None:
    """Return the stored full name of a party, or None."""
    party = get_party(party_id)
    return party.name if party and party.name.strip() else None
