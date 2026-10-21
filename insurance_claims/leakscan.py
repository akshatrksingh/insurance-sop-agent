"""SAFE-05: before verification, scan a reply for stored policyholder values and claim fields.

A hit is replaced with a safe template. The pre-verification templates hold no such values, so
this is a second line of defence, not the first.
"""

import logging
import re
from functools import lru_cache

from insurance_claims.data import load_policyholders
from insurance_claims.tools import load_claims

logger = logging.getLogger(__name__)
MIN_LENGTH = 5
CLAIM_TEXT_FIELDS = ('case_id', 'summary', 'denial_reason', 'appeal_deadline')


def _digits(text: str) -> str:
    """Return only the digits of the text."""
    return re.sub(r'\D', '', text)


@lru_cache(maxsize=1)
def _protected() -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Return (text values, four digit ids, digit strings) from the records. Built once, never logged."""
    words: set[str] = set()
    fours: set[str] = set()
    numbers: set[str] = set()
    for p in load_policyholders():
        for value in [p.name, *p.name_aliases, p.email, *p.email_aliases, p.policy_number, p.dob]:
            if len(value.strip()) >= MIN_LENGTH:
                words.add(value.strip().casefold())
        fours.add(p.id_last4)
        for phone in [p.phone, *p.phone_aliases]:
            if len(_digits(phone)) >= 10:
                numbers.add(_digits(phone)[-10:])
    for claim in load_claims():
        for key in CLAIM_TEXT_FIELDS:
            if len(str(claim.get(key) or '')) >= MIN_LENGTH:
                words.add(str(claim[key]).casefold())
        words.update(d.casefold() for d in claim.get('documents_needed') or [] if len(d) >= MIN_LENGTH)
        for key in ('net_pay', 'expected_reimbursement_amount', 'allowed_max_amount'):
            if len(str(claim.get(key) or '')) >= MIN_LENGTH:
                words.add(str(claim[key]))
    return tuple(words), tuple(fours), tuple(numbers)


def leaks(text: str) -> bool:
    """Return True when the text holds a stored policyholder value or a claim field."""
    words, fours, numbers = _protected()
    low = text.casefold()
    if any(w in low for w in words):
        return True
    if any(re.search(rf'(?<!\d){f}(?!\d)', text) for f in fours):
        return True
    return any(n in _digits(text) for n in numbers)


def safe_reply(text: str, fallback: str) -> str:
    """Return the text, or the fallback template when the text leaks a stored value."""
    if leaks(text):
        logger.warning('Pre-verification reply replaced by a safe template')
        return fallback
    return text
