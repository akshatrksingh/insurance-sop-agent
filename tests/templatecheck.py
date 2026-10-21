"""Template membership check for pre-verification replies. Reads only insurance_claims/prompts/verify_templates.json
(a narrow exception to black box, used to build the membership sets)."""
import json
import re

from conftest import ROOT

TEMPLATES = json.loads((ROOT / 'insurance_claims' / 'prompts' / 'verify_templates.json').read_text(encoding='utf-8'))
ORDER = ['Full name', 'Date of birth', 'Phone', 'Email', 'ID last 4']
WORDS = {'Full name': 'full name', 'Date of birth': 'date of birth', 'Phone': 'phone number', 'Email': 'email',
         'ID last 4': 'last four of SSN'}
FACTOR_KEYS = {'full_name': 'Full name', 'dob': 'Date of birth', 'phone': 'Phone', 'email': 'Email', 'id_last4': 'ID last 4'}
EMPATHY = TEMPLATES['empathy']
NEGATIVE = ('frustration', 'anger', 'anxiety')
# Fixed pre-verification human offer (SCOPE-02). It is code text, not a key of verify_templates.json, so it is accepted
# only as this exact string and only once the off-topic strike count has reached the default limit.
HUMAN_OFFER = 'I cannot help with that here. Would you like me to connect you with a human representative?'
OFFER_AFTER_STRIKES = 3
# Fixed VER-07 offer after the third failed verification round (CP5). Accepted only as this exact string.
VERIFY_OFFER = 'I could not confirm your identity with those details. Would you like me to connect you with a human representative?'


def options_text(unconfirmed):
    """Option words for the unconfirmed factors in file order. Two options are accepted with or without a comma."""
    words = [WORDS[f] for f in ORDER if f in unconfirmed]
    if len(words) <= 1:
        return [' '.join(words)]
    head = ', '.join(words[:-1])
    forms = [f'{head}, or {words[-1]}']
    if len(words) == 2:
        forms.append(f'{words[0]} or {words[1]}')
    return forms


def groups():
    """Template groups: name -> list of template strings. Clarify entries are flattened per factor key."""
    out = {k: v for k, v in TEMPLATES.items() if k not in ('empathy', 'clarify')}
    for key, lst in TEMPLATES['clarify'].items():
        out[f'clarify:{key}'] = lst
    return out


def filled(group, confirmed):
    """All allowed replies of one group for a set of confirmed factor labels."""
    count = f'{min(len(confirmed), 3)} of 3'
    unconfirmed = set(ORDER) - set(confirmed)
    return {t.replace('{count}', count).replace('{options}', opt) for t in groups()[group] for opt in options_text(unconfirmed)}


def allowed(confirmed, groups_=None):
    """Every allowed template reply (without empathy) for the confirmed set, optionally limited to some groups."""
    names = groups_ or list(groups())
    return set().union(*(filled(g, confirmed) for g in names))


def split_empathy(reply):
    """Return (empathy line or None, rest) when the reply starts with an empathy line."""
    for line in EMPATHY:
        if reply.startswith(line):
            return line, reply[len(line):].lstrip()
    return None, reply


def empathy_allowed(label, intensity):
    """True when the empathy line may be prepended."""
    return label in NEGATIVE and intensity >= 2


def check_reply(reply, confirmed, label='neutral', intensity=0, groups_=None, strikes=None):
    """Return a list of problems (empty when the reply is an allowed template with correct slots).
    HUMAN_OFFER is accepted only when strikes is given and at least OFFER_AFTER_STRIKES."""
    if reply == HUMAN_OFFER and strikes is not None and strikes >= OFFER_AFTER_STRIKES:
        return []
    if reply == VERIFY_OFFER:
        return []
    line, rest = split_empathy(reply)
    problems = []
    if line and not empathy_allowed(label, intensity):
        problems.append('empathy not allowed')
    if rest not in allowed(confirmed, groups_):
        problems.append('not an allowed template for this state')
    if re.search(r'\{\w+\}', reply):
        problems.append('unfilled slot')
    return problems
