"""Which single claim field a follow-up message asks for. Whole words and phrases only (CASE-01)."""

import re

from insurance_claims.claims import ACTION_VERBS

# Each entry is a regex with word boundaries. "allowed" alone is not a field word ("Am I allowed to appeal?").
FIELD_WORDS = {
    'documents': r'\b(?:documents?|paperwork)\b',
    'status': r'\bstatus\b',
    'reason': r'\b(?:why|reasons?)\b',
    'deadline': r'\b(?:deadline|appeal by|too late)\b',
    'net_pay': r'\bnet pay\b',
    'expected': r'\b(?:reimburse(?:d|ment)?|expected)\b',
    'allowed': r'\b(?:allowed (?:max(?:imum)?|amount)|max(?:imum)?(?: allowed)?)\b',
}
# A request that the agent do something ("Can you file it before the deadline?") is not a field question.
_REQUEST = re.compile(rf'\b(?:can|could|would|will|please)\b[^?.!]*\byou\b[^?.!]*\b{ACTION_VERBS}\b|\bplease\s+{ACTION_VERBS}\b')
AMOUNTS = {
    'net_pay': ('net_pay', 'The net pay is {m}.', 'Your net pay on this claim is {m}.', 'The net pay recorded is {m}.'),
    'expected': (
        'expected_reimbursement_amount',
        'The expected reimbursement is {m}.',
        'You can expect a reimbursement of {m}.',
        'The expected reimbursement recorded is {m}.',
    ),
    'allowed': (
        'allowed_max_amount',
        'The allowed maximum is {m}.',
        'The most that is allowed on this claim is {m}.',
        'The allowed maximum recorded is {m}.',
    ),
}



def asked_field(message: str) -> str | None:
    """Return the one field a message asks for, or None (use the model path) when none, several or an action request."""
    text = re.sub(r'\s+', ' ', message.lower())
    if text.count('?') > 1 or _REQUEST.search(text.replace('net pay', 'net_pay_field')):
        return None
    found = [f for f, pattern in FIELD_WORDS.items() if re.search(pattern, text)]
    return found[0] if len(found) == 1 else None


def mentions_field(message: str) -> bool:
    """True when the message uses the words of any claim field, alone or with others."""
    text = re.sub(r'\s+', ' ', message.lower())
    return any(re.search(pattern, text) for pattern in FIELD_WORDS.values())
