"""Refusal line for a verified caller who asks about someone else's claim (B38).

Detection is deterministic and uses only facts already held: the fixture parties, the claims of
other parties, the extractor's identity and case_id hints, and a few request patterns. No party
data is read into any reply or bundle; the line is fixed text.
"""

import re

from insurance_claims.data import load_policyholders
from insurance_claims.extractor import Extraction
from insurance_claims.state import Session
from insurance_claims.tools import load_claims

REFUSAL = "I can only discuss your own claim, so I cannot share anyone else's."
_GENERIC = re.compile(r"\b(someone|somebody|anyone|another\s+(person|customer|policyholder)|other\s+people|a\s+(friend|neighbou?r))(\W+else)?\W*s\s+(claim|case|file)", re.I)
_POSSESSIVE = re.compile(r"\b(?:show|give|get|pull|tell|let)\s+(?:me\s+)?(?:about\s+)?([a-z][\w.-]*(?:\s+[a-z][\w.-]*)?)['\u2019]s\s+(?:claim|case|file)", re.I)
_NOT_NAMES = {'my', 'the', 'this', 'that', 'our', 'it', 'there', 'here', 'what', 'who', 'which', 'where', 'your', 'me', 'let', 'one'}
_CASE_ID = re.compile(r'\bCL-\d+\b', re.I)


def _words(name: str) -> set[str]:
    """Lower-case word set of a name."""
    return set(re.findall(r"[\w.-]+", name.casefold()))


def _own_words(session: Session) -> set[str]:
    """Words of the verified party's stored names."""
    mine = next((p for p in load_policyholders() if p.party_id == session.party_id), None)
    return set().union(*(_words(n) for n in [mine.name, *mine.name_aliases])) if mine else set()


def _others(session: Session):
    """The fixture records of every party except the verified one."""
    return [p for p in load_policyholders() if p.party_id != session.party_id]


def _names_other(text: str, session: Session) -> bool:
    """True when the text holds the full name, alias, or policy number of another party."""
    low = text.casefold()
    digits = re.sub(r'\D', '', text)
    for party in _others(session):
        names = [party.name, *party.name_aliases]
        if any(n.strip() and re.search(rf'(?<!\w){re.escape(n.casefold())}(?!\w)', low) for n in names):
            return True
        if re.sub(r'\D', '', party.policy_number) in digits.replace(' ', '') and re.search(re.escape(party.policy_number), text, re.I):
            return True
    return False


def _foreign_case(text: str, session: Session) -> bool:
    """True when the text holds a case id that belongs to another party."""
    ids = {m.upper() for m in _CASE_ID.findall(text)}
    return any(c['case_id'].upper() in ids and c['party_id'] != session.party_id for c in load_claims())


def _other_possessive(text: str, session: Session) -> bool:
    """True for `show me <Name>'s claim` where the name is not the caller's own."""
    for match in _POSSESSIVE.finditer(text):
        words = _words(match.group(1))
        if words and not words & _NOT_NAMES and not words & _own_words(session):
            return True
    return False


def asks_other_party(session: Session, ex: Extraction, message: str) -> bool:
    """True when a verified caller asks about another party's claim this turn."""
    if not session.gates.verified:
        return False
    parts = [message, ex.identity.full_name or '', ex.identity.policy_number or '', ex.hints.case_id or '']
    text = ' '.join(parts)
    return bool(_GENERIC.search(message) or _other_possessive(message, session)
                or _names_other(text, session) or _foreign_case(text, session))


def with_refusal(reply: str) -> str:
    """Put the fixed refusal line first, once."""
    return reply if reply.startswith(REFUSAL) else f'{REFUSAL} {reply}'.strip()
