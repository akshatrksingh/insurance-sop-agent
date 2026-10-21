"""Claim tools: plain synchronous lookups that return curated data or a structured error."""

import json
import logging
from functools import lru_cache

from insurance_claims.data import FIXTURES

logger = logging.getLogger(__name__)
SUMMARY_FIELDS = ('case_id', 'case_type', 'status', 'created_at', 'summary')


def _error(error: str, message: str, suggestion: str, recoverable: bool = True) -> dict:
    """Return the structured error shape from the coding guidelines."""
    return {'error': error, 'message': message, 'recoverable': recoverable, 'suggestion': suggestion}


@lru_cache(maxsize=1)
def _load_claims() -> tuple[dict, ...]:
    """Load the claim records from the fixture file once."""
    raw = json.loads((FIXTURES / 'claims.json').read_text(encoding='utf-8'))
    return tuple(raw)


def get_claims(party_id: str | None) -> list[dict] | dict:
    """Return summaries of one party's claims, or a structured error.

    Args:
        party_id: The verified party. Only this party's claims are ever returned.

    Returns:
        A list of dicts with case_id, case_type, status, created_at and summary,
        or an error dict (`NO_PARTY`, `NO_CLAIMS`).
    """
    if not party_id:
        return _error('NO_PARTY', 'No verified party.', 'Continue verification.')
    mine = [{k: c.get(k) for k in SUMMARY_FIELDS} for c in _load_claims() if c['party_id'] == party_id]
    if not mine:
        return _error('NO_CLAIMS', 'No claims on file for this party.', 'Offer a human representative.', False)
    return mine


def get_claim(party_id: str | None, case_id: str | None) -> dict:
    """Return one curated claim owned by the party, or a structured error.

    Args:
        party_id: The verified party.
        case_id: The case id to fetch.

    Returns:
        The claim without its party id, or an error dict (`NOT_FOUND`).
    """
    for claim in _load_claims():
        if claim['party_id'] == party_id and claim['case_id'] == case_id:
            return {k: v for k, v in claim.items() if k != 'party_id'}
    logger.info('Claim lookup found nothing (case=%s)', case_id)
    return _error('NOT_FOUND', 'No such claim for this party.', 'Ask the caller which claim they mean.')
