"""Output checks that keep claim replies grounded in the bundle (CASE-01)."""

import json
import re

from insurance_claims.claims import ACTION_CLAIMS

_NUMBER = re.compile(r'\d+(?:,\d{3})*(?:\.\d+)?')

# Vocabulary for the ungrounded-detail check (CASE-01). Everything here must appear in the bundle to be said.
_NUM_WORDS = (
    r'(?:a|an|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty|thirty|forty|'
    r'sixty|ninety|hundred|thousand|million|couple of|few|several|\d+)'
)
_TIME_UNITS = r'(?:business |working |calendar )?(?:hours?|days?|weeks?|months?|years?)'
_MONTH = r'(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?'
TIME_FRAME = re.compile(
    rf'\b{_NUM_WORDS}(?:[ -]{_NUM_WORDS})?[ -]{_TIME_UNITS}\b|\b(?:next|this|last) (?:week|month|year)\b|\btomorrow\b'
    rf'|\b{_MONTH} \d{{1,2}}(?:st|nd|rd|th)?(?:, \d{{4}})?|\b\d{{4}}-\d{{2}}-\d{{2}}\b|\b\d{{1,2}}/\d{{1,2}}/\d{{2,4}}\b',
    re.I,
)
FILE_FORMAT = re.compile(
    r'\b(?:pdf|jpe?g|png|gif|tiff?|bmp|docx?|xlsx?|csv|zip|heic|fax|facsimile|email attachment|attachment|scan)\b', re.I
)
AMOUNT_WORDS = re.compile(
    rf'(?:\b{_NUM_WORDS}(?:[ -]{_NUM_WORDS})*|\b\d[\d,]*(?:\.\d+)?)[ -](?:dollars?|usd|euros?|cents)\b', re.I
)
DOCUMENT_NAME = re.compile(
    r"\b(?:[a-z']+ )?(?:report|note|estimate|records?|statement|certificate|invoice|receipt|form|letter|photos?|bill)s?\b"
    r'|\bproof of \w+',
    re.I,
)
_NOT_A_DOCUMENT_PREFIX = {
    'the', 'a', 'an', 'your', 'this', 'that', 'its', 'my', 'our', 'each', 'same', 'any', 'these', 'those', 'one',
    'and', 'or', 'of', 'to', 'for', 'in', 'on', 'with', 'is', 'are', 'be', 'it', 'as', 'at', 'by', 'if',
}


def _numbers(text: str) -> set[str]:
    """Return the numeric tokens of a text, with thousands commas removed and trailing zeros trimmed."""
    out = set()
    for token in _NUMBER.findall(text):
        value = token.replace(',', '')
        if '.' in value:
            value = value.rstrip('0').rstrip('.')
        out.add(value.lstrip('0') or '0')
    return out


def _counts(value: object) -> set[str]:
    """Return list lengths found in the bundle, so counts such as 'two documents' are allowed."""
    if isinstance(value, list):
        found = {str(len(value))}
        for item in value:
            found |= _counts(item)
        return found
    if isinstance(value, dict):
        found = set()
        for item in value.values():
            found |= _counts(item)
        return found
    return set()


def _iso_dates(text: str) -> set[tuple[int, int, int]]:
    """Return the (year, month, day) of every ISO date in a text."""
    return {tuple(int(x) for x in m.groups()) for m in re.finditer(r'(\d{4})-(\d{2})-(\d{2})', text)}


def _date_in_source(phrase: str, source: str, dates: set[tuple[int, int, int]]) -> bool:
    """True when a month-name date such as 'March 18, 2026' matches an ISO date of the source."""
    m = re.match(rf'({_MONTH}) (\d{{1,2}})(?:st|nd|rd|th)?(?:, (\d{{4}}))?', phrase, re.I)
    if not m:
        return False
    month = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'].index(m.group(1)[:3].lower()) + 1
    return any((d[1], d[2]) == (month, int(m.group(2))) and (not m.group(3) or d[0] == int(m.group(3))) for d in dates)


def _phrase_in(phrase: str, source: str, dates: set[tuple[int, int, int]]) -> bool:
    """True when a flagged phrase is found in the source text, allowing plurals and date reformatting."""
    low = phrase.casefold().strip()
    return low.rstrip('s') in source or _date_in_source(low, source, dates)


def _details(text: str) -> list[str]:
    """Return the time frames, file formats, word amounts and named documents the text states."""
    found = [m.group(0) for pattern in (TIME_FRAME, FILE_FORMAT) for m in pattern.finditer(text)]
    # Digit amounts are compared by value in `_numbers` (1,450 dollars, $1,450 and 1450.00 are the same).
    found += [m.group(0) for m in AMOUNT_WORDS.finditer(text) if not re.search(r'\d', m.group(0))]
    for m in DOCUMENT_NAME.finditer(text):
        words = m.group(0).split()
        if len(words) > 1 and words[0].casefold() in _NOT_A_DOCUMENT_PREFIX:
            words = words[1:]
        if len(words) > 1 or words[0].casefold().startswith('proof'):
            found.append(' '.join(words))
    return found


def _ungrounded_actions(text: str, dumped: str) -> bool:
    """True when the text promises an outcome or an action that the bundle text does not state."""
    flat = re.sub(r'\s+', ' ', dumped)
    for pattern in ACTION_CLAIMS:
        for m in pattern.finditer(text):
            phrase = re.sub(r'\s+', ' ', m.group(0).casefold())
            words = phrase.split()
            if phrase in flat or (words[0] in ('is', 'are', 'was', 'were') and len(words) == 2 and words[1] in flat):
                continue  # a plain recorded state such as "is approved" when the claim status says approved
            return True
    return False


def ungrounded(text: str, bundle: dict) -> bool:
    """Return True when the reply states a number, time frame, file format, amount, document, outcome or action not in the bundle.

    The caller's own message does not count as a source. Matched guidance text is part of the bundle.
    """
    source = {k: v for k, v in bundle.items() if k != 'caller_message'}
    dumped = json.dumps(source).casefold()
    if not _numbers(text) <= (_numbers(dumped) | _counts(source)):
        return True
    if _ungrounded_actions(text, dumped):
        return True
    dates = _iso_dates(dumped)
    return any(not _phrase_in(d, dumped, dates) for d in _details(text))


def misses_deadline(text: str, bundle: dict) -> bool:
    """Return True when a first claim answer skips the recorded deadline decision.

    A passed deadline must be stated as the recorded date and as passed.
    """
    claim = bundle.get('claim')
    if not claim or not bundle.get('first_answer') or not bundle.get('deadline_passed'):
        return False
    return claim.get('appeal_deadline', '') not in text or 'passed' not in text.casefold()
