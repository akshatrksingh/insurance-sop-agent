"""Patterns that find identity values (email, phone, date, bare last 4, claim reference) in a message.

Dates need a full month word with boundaries and a day. A phone needs 10 to 15 digits and is never a
pair of years. Whether a value counts as an answer (and not a number inside an off-topic question)
is decided by the callers, from the words around it.
"""

import re

_MONTH = (
    r'january|february|march|april|may|june|july|august|september|october|november|december|'
    r'jan|feb|mar|apr|jun|jul|aug|sept|sep|oct|nov|dec'
)
_DAY = r'\d{1,2}(?:st|nd|rd|th)?'
EMAIL = re.compile(r'[\w.+-]+@[\w-]+\.[\w.]+')
CLAIM_REF = re.compile(r'\b(?:pol|cl)[-\s]?\d+\b', re.I)
ALWAYS_VALUE = re.compile(rf'{EMAIL.pattern}|{CLAIM_REF.pattern}', re.I)
NUMERIC_DATE = re.compile(r'\b\d{1,4}[-/]\d{1,2}[-/]\d{1,4}\b')
MONTH_DAY = re.compile(rf'\b(?:{_MONTH})\b\.?\s+{_DAY}\b(?:,?\s+\d{{4}}\b)?', re.I)
DAY_MONTH = re.compile(rf'\b{_DAY}\s+(?:of\s+)?(?:{_MONTH})\b\.?,?\s+\d{{4}}\b', re.I)
PHONE_RUN = re.compile(r'\d[\d\s().-]{8,}\d')
YEAR_PAIR = re.compile(r'\d{4}\D+\d{4}')
BARE_DIGITS = re.compile(r'\b\d{4}\b')
LAST_FOUR_WORDS = re.compile(r'\blast\s*(?:four|4)\b|\bssn\b|\bid\b', re.I)
FILLER = frozenset(
    'my name is its it s the a an i m am hi hello hey dob date of birth born on phone number email address '
    'ssn last four 4 digits digit id policy and yes no thanks thank you please calling about me at reach can '
    'are that this was'.split()
)


def phone_spans(text: str) -> list[tuple[int, int]]:
    """Spans of digit runs that look like a phone number: 10 to 15 digits, not two years."""
    spans = []
    for match in PHONE_RUN.finditer(text):
        digits = len(re.sub(r'\D', '', match.group()))
        if 10 <= digits <= 15 and not YEAR_PAIR.fullmatch(match.group().strip()):
            spans.append(match.span())
    return spans


def date_spans(text: str) -> list[tuple[int, int]]:
    """Spans of numeric dates (1985-03-15), month then day (March 15, 1985), and day month year."""
    return [m.span() for rx in (NUMERIC_DATE, MONTH_DAY, DAY_MONTH) for m in rx.finditer(text)]


def number_spans(text: str) -> list[tuple[int, int]]:
    """Spans of every phone, date, and bare 4-digit number in the text."""
    return phone_spans(text) + date_spans(text) + [m.span() for m in BARE_DIGITS.finditer(text)]


def cut(text: str, spans: list[tuple[int, int]]) -> str:
    """The text with the given spans replaced by spaces."""
    chars = list(text)
    for start, end in spans:
        chars[start:end] = ' ' * (end - start)
    return ''.join(chars)
