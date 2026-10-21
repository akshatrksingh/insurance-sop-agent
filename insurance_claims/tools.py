"""Claim tools: plain synchronous lookups that return curated data or a structured error."""

import json
import logging
from datetime import date
from functools import lru_cache

from insurance_claims.data import FIXTURES, get_party
from insurance_claims.grounded import join_items
from insurance_claims.state import Session

logger = logging.getLogger(__name__)
SUMMARY_FIELDS = ('case_id', 'case_type', 'status', 'created_at', 'summary')


def error_result(error: str, message: str, suggestion: str, recoverable: bool = True) -> dict:
    """Return the structured error shape from the coding guidelines."""
    return {'error': error, 'message': message, 'recoverable': recoverable, 'suggestion': suggestion}


@lru_cache(maxsize=1)
def load_claims() -> tuple[dict, ...]:
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
        return error_result('NO_PARTY', 'No verified party.', 'Continue verification.')
    mine = [{k: c.get(k) for k in SUMMARY_FIELDS} for c in load_claims() if c['party_id'] == party_id]
    if not mine:
        return error_result('NO_CLAIMS', 'No claims on file for this party.', 'Offer a human representative.', False)
    return mine


def get_claim(party_id: str | None, case_id: str | None) -> dict:
    """Return one curated claim owned by the party, or a structured error.

    Args:
        party_id: The verified party.
        case_id: The case id to fetch.

    Returns:
        The claim without its party id, or an error dict (`NOT_FOUND`).
    """
    for claim in load_claims():
        if claim['party_id'] == party_id and claim['case_id'] == case_id:
            return {k: v for k, v in claim.items() if k != 'party_id'}
    logger.info('Claim lookup found nothing (case=%s)', case_id)
    return error_result('NOT_FOUND', 'No such claim for this party.', 'Ask the caller which claim they mean.')


def build_summary(session: Session) -> dict:
    """Build the email summary from state and the resolved claim only (POST-03).

    What was discussed, the claim status or outcome, and follow-up items or next steps.
    The text comes from the session's topics and the claim record, never from caller messages,
    so a rejected or off-topic message cannot reach it.

    Args:
        session: A verified session with a resolved case.

    Returns:
        A dict with `subject` and `body`, or an error dict (`NOT_VERIFIED`, `NO_CASE`).
    """
    if not session.gates.verified:
        return error_result('NOT_VERIFIED', 'Identity not verified.', 'Continue verification.')
    claim = get_claim(session.party_id, session.resolved_case_id)
    if 'error' in claim:
        return error_result('NO_CASE', 'No resolved case to summarize.', 'Resolve the case first.')
    topics = [(session.intent or 'general_claim_question').replace('_', ' ')]
    topics += [t for t in session.topics if t not in topics]
    status = f"Status: {claim['status']}."
    if claim.get('denial_reason'):
        status += f" Reason on file: {claim['denial_reason']}."
    steps = []
    if claim.get('documents_needed'):
        steps.append(f"Documents needed: {join_items(claim['documents_needed'])}.")
    if claim.get('appeal_deadline'):
        passed = claim['appeal_deadline'] < date.today().isoformat()
        steps.append(f"Appeal deadline: {claim['appeal_deadline']}." + (' That date has passed.' if passed else ''))
        if passed:
            steps.append('A human representative can go over next steps with you.')
    steps = steps or ['No follow-up items are recorded on this claim.']
    lines = [
        f"Summary of your call about {claim['case_type']} claim {claim['case_id']}.",
        '',
        'What we discussed: ' + ', '.join(topics) + '.',
        status,
        '',
        'Next steps:',
        *[f'  {step}' for step in steps],
    ]
    return {'subject': f"Your claims support summary for {claim['case_id']}", 'body': '\n'.join(lines)}


def send_email(to: str, subject: str, body: str) -> dict:
    """Mock send: nothing leaves the process. Returns the preview, or a structured error.

    Args:
        to: The address on file.
        subject: The subject line.
        body: The body text.

    Returns:
        A dict with `to`, `subject` and `body` (the exact email), or an error dict (`BAD_ADDRESS`).
    """
    if '@' not in (to or ''):
        return error_result('BAD_ADDRESS', 'No usable email address on file.', 'Offer a human representative.', False)
    logger.info('Mock email recorded (subject length=%d)', len(subject))
    return {'to': to, 'subject': subject, 'body': body}
