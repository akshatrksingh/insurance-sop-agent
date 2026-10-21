"""Fixed replies built by code from bundle data. Used when a model reply fails the output checks."""

ASK = 'What do you need help with on your claim?'
HUMAN_OFFER = 'I can connect you with a human representative to talk through next steps.'


def _claim_line(claim: dict) -> str:
    """Return a short description of one claim from its summary fields."""
    return f"{claim['case_type']} claim {claim['case_id']} ({claim['status']}, created {claim['created_at']})"


OPENERS = (
    'Your {type} claim {id} is {status}.',
    'I found your {type} claim {id}. Its status is {status}.',
    'Claim {id} is a {type} claim, and its status is {status}.',
    'Here is where claim {id} stands. It is a {type} claim and its status is {status}.',
)
DENIALS = (
    'It was denied because {reason}.',
    'The reason for the denial is that {reason}.',
    'The denial reason on file is that {reason}.',
)
DOCUMENTS = (
    'The documents needed are {docs}.',
    'It needs {docs}.',
    'What is needed is {docs}.',
)
OPEN_DEADLINES = (
    'The appeal deadline is {date}, and it has not passed.',
    'You have until {date} to appeal, so that date has not passed.',
    'The deadline to appeal is {date}. It has not passed.',
)
PASSED_DEADLINES = (
    'The appeal deadline was {date} and that date has passed.',
    'The deadline to appeal was {date}. It has passed.',
    'The appeal deadline, {date}, has passed.',
)
HUMAN_OFFERS = (
    HUMAN_OFFER,
    'A human representative can go over next steps with you, and I can connect you.',
    'I can put you in touch with a human representative about what to do next.',
)
LEADS = ('Thanks, {name}. You are verified.', 'You are verified, {name}.')


def _pick(options: tuple[str, ...], seed: int, offset: int) -> str:
    """Choose a phrasing deterministically from the claim id seed, no randomness."""
    return options[(seed + offset) % len(options)]


def join_items(items: list[str]) -> str:
    """Join items with articles and 'and': 'the a', 'the a and the b', 'the a, the b, and the c'."""
    words = [f'the {item}' for item in items]
    if len(words) <= 2:
        return ' and '.join(words)
    return ', '.join(words[:-1]) + f', and {words[-1]}'


def _money(value: str) -> str:
    """Format a recorded amount such as 780.00 as $780.00."""
    return f'${float(value):,.2f}'


def _claim_answer(bundle: dict) -> str:
    """Build the answer for the resolved claim from its recorded fields only.

    Phrasings are picked by claim id so the same claim always reads the same and
    different claims do not all sound alike. Only fields present in the claim are stated.
    """
    claim = bundle['claim']
    seed = sum(ord(ch) for ch in claim['case_id'])
    parts = [_pick(OPENERS, seed, 0).format(type=claim['case_type'], id=claim['case_id'], status=claim['status'])]
    if claim.get('denial_reason'):
        parts.append(_pick(DENIALS, seed, 1).format(reason=claim['denial_reason']))
    elif claim.get('net_pay') and float(claim['net_pay']) > 0:
        parts.append(f"The net pay is {_money(claim['net_pay'])}.")
    else:
        parts.append(f"{claim['summary']}.")
    if claim.get('documents_needed'):
        docs = join_items(claim['documents_needed'])
        parts.append(_pick(DOCUMENTS, seed, 2).format(docs=docs))
    if claim.get('appeal_deadline'):
        date = claim['appeal_deadline']
        if bundle.get('deadline_passed'):
            parts.append(_pick(PASSED_DEADLINES, seed, 0).format(date=date))
            parts.append(_pick(HUMAN_OFFERS, seed, 1))
        else:
            parts.append(_pick(OPEN_DEADLINES, seed, 0).format(date=date))
    return ' '.join(parts)


FIELD_WORDS = {
    'documents': ('document', 'paperwork'),
    'status': ('status',),
    'reason': ('why', 'reason'),
    'deadline': ('deadline', 'appeal by', 'too late'),
    'net_pay': ('net pay',),
    'expected': ('reimburs', 'expected'),
    'allowed': ('allowed', 'maximum'),
}
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
    """Return the one field a message asks for, or None when none or several match."""
    text = message.lower()
    if text.count('?') > 1:
        return None
    found = [f for f, words in FIELD_WORDS.items() if any(w in text for w in words)]
    return found[0] if len(found) == 1 else None


def field_reply(bundle: dict) -> str | None:
    """Answer a single-field follow-up from the claim, or None to use the model path."""
    claim = bundle.get('claim')
    field = asked_field(bundle.get('caller_message', ''))
    if not claim or not field:
        return None
    seed = sum(ord(ch) for ch in claim['case_id'])
    if field == 'documents' and claim.get('documents_needed'):
        return _pick(DOCUMENTS, seed, 2).format(docs=join_items(claim['documents_needed']))
    if field == 'status':
        return _pick(OPENERS, seed, 0).format(type=claim['case_type'], id=claim['case_id'], status=claim['status'])
    if field == 'reason' and claim.get('denial_reason'):
        return _pick(DENIALS, seed, 1).format(reason=claim['denial_reason'])
    if field == 'deadline' and claim.get('appeal_deadline'):
        date = claim['appeal_deadline']
        if bundle.get('deadline_passed'):
            return f"{_pick(PASSED_DEADLINES, seed, 0).format(date=date)} {_pick(HUMAN_OFFERS, seed, 1)}"
        return _pick(OPEN_DEADLINES, seed, 0).format(date=date)
    if field in AMOUNTS:
        key, *phrasings = AMOUNTS[field]
        if claim.get(key) is not None:
            return _pick(tuple(phrasings), seed, 0).format(m=_money(claim[key]))
    return None


def _resolve_question(bundle: dict) -> str:
    """Build the one question for an unresolved or intent-less case."""
    state = bundle.get('case_state')
    claims = bundle.get('claims', [])
    if state == 'ask_intent':
        return f"I found your claim {bundle['matching_case_ids'][0]}. What would you like to know about it?"
    if state == 'ask_need' or not claims:
        return ASK
    ids = bundle.get('matching_case_ids') or []
    shown = [c for c in claims if c['case_id'] in ids] if state == 'several' else claims
    listing = '; '.join(_claim_line(c) for c in shown)
    if state == 'several':
        return f'Several claims fit: {listing}. Which one do you mean?'
    return f'I could not match that to one claim. Your claims: {listing}. Which one do you mean?'


def first_reply(bundle: dict) -> str:
    """Return the first reply after a case is resolved. Built by code, no model text."""
    return fallback_reply(bundle)


def fallback_reply(bundle: dict) -> str:
    """Return the fixed reply for a bundle. It announces verification only on that turn."""
    if bundle.get('claim'):
        body = _claim_answer(bundle)
    else:
        body = _resolve_question(bundle)
    if not bundle.get('verified_this_turn'):
        return body
    name = bundle.get('full_name')
    if name:
        seed = sum(ord(ch) for ch in (bundle.get('claim') or {}).get('case_id', ''))
        lead = _pick(LEADS, seed, 0).format(name=name)
    else:
        lead = 'Thanks, you are verified.'
    return f'{lead} {body}'
