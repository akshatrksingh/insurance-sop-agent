"""Check that an identity value the extractor returned really is the caller's answer in the message.

The extractor can return an identity value for any text. Scope reconciliation trusts one only when
each value is found in the message with word boundaries and what remains is only identity filler or
allowlisted phrases, so an off-topic question that happens to hold a name or a date stays off topic
(SCOPE-02).
"""

import re

from insurance_claims.allowlist import rest_is_filler
from insurance_claims.extractor import Identity
from insurance_claims.identity_values import BARE_DIGITS, cut, date_spans, phone_spans

MIN_TOKEN = 5  # shortest email or policy number taken as a match
_EDGE = '.,;:!?()[]"\''


def _digits(text: str) -> str:
    """Digits of the text, in order."""
    return re.sub(r'\D', '', text)


def _name_spans(value: str, text: str) -> list[tuple[int, int]]:
    """Spans of every word of the name, or [] unless all words appear with word boundaries."""
    words = re.findall(r"[\w'.-]+", value.casefold())
    if len(value.strip()) < 3 or not words:
        return []
    spans = []
    for word in words:
        found = re.search(rf'(?<!\w){re.escape(word)}(?!\w)', text, re.I)
        if not found:
            return []
        spans.append(found.span())
    return spans


def _token_spans(value: str, text: str) -> list[tuple[int, int]]:
    """Span of the whitespace token equal to the value (email, policy number), length 5 or more."""
    wanted = value.strip().casefold()
    if len(wanted) < MIN_TOKEN:
        return []
    for found in re.finditer(r'\S+', text):
        if found.group().strip(_EDGE).casefold() == wanted:
            return [found.span()]
    return []


def _phone_spans(value: str, text: str) -> list[tuple[int, int]]:
    """Span of the phone-like run whose last 10 digits equal the value's."""
    wanted = _digits(value)[-10:]
    spans = [s for s in phone_spans(text) if _digits(text[s[0]:s[1]])[-10:] == wanted]
    return spans if len(wanted) == 10 else []


def _dob_spans(value: str, text: str) -> list[tuple[int, int]]:
    """Spans of a date in the text that holds the value's year and day as numbers."""
    parts = re.findall(r'\d+', value)
    if len(parts) < 3:
        return []
    year, day = int(parts[0]), int(parts[2])
    return [
        s for s in date_spans(text)
        if {year, day} <= {int(n) for n in re.findall(r'\d+', text[s[0]:s[1]])}
    ]


def _last4_spans(value: str, text: str) -> list[tuple[int, int]]:
    """Span of the bare 4-digit token equal to the value."""
    return [m.span() for m in BARE_DIGITS.finditer(text) if m.group() == value.strip()][:1]


FINDERS = {
    'full_name': _name_spans, 'email': _token_spans, 'policy_number': _token_spans,
    'phone': _phone_spans, 'dob': _dob_spans, 'id_last4': _last4_spans,
}


def identity_in_message(identity: Identity, text: str) -> bool:
    """True when the extracted identity values are in the message and nothing else is.

    Args:
        identity: The extractor's identity fields.
        text: The caller's message.

    Returns:
        True when at least one non-empty value is found in the text with word boundaries (email and
        policy number as an exact token of 5 or more characters) and, with every found value removed,
        only identity filler or allowlisted phrases remain.
    """
    spans: list[tuple[int, int]] = []
    for name, value in identity.model_dump().items():
        if value:
            spans += FINDERS[name](str(value), text)
    return bool(spans) and rest_is_filler(cut(text, spans))
