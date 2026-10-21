"""Typed email consent (POST-02): the whole message must be a plain affirmative.

The extractor's `consent` field alone never sends an email. For a typed message the whole text must
also match a short list of plain yes phrases, so an unrelated or injected message that the model
read as consent cannot send. This list is for the email question only, never for the human offer.
"""

import re

CONFIRM_ASK = 'Please say yes to send it, or skip.'  # human approved wording, Tier 2 waiver of the no-please rule

_HEADS = ('', 'yes', 'yeah', 'yep', 'yup', 'sure', 'ok', 'okay', 'yes please', 'sure thing', 'of course', 'absolutely')
_TAILS = (
    '', 'please', 'send it', 'send it please', 'please send it', 'go ahead', 'please go ahead',
    'send the summary', 'send summary', 'do it', 'please do', 'send the email', 'send it over',
)
_STANDALONE = (
    'sounds good', 'that works', 'that works for me', 'that sounds good', 'lets do it', 'email it to me',
    'please email it', 'email it', 'yes that works', 'yes sounds good', 'ok sounds good', 'sure sounds good',
)
AFFIRMATIVES = frozenset(
    {f'{head} {tail}'.strip() for head in _HEADS for tail in _TAILS} - {'', 'please'} | set(_STANDALONE)
)


def plain(message: str) -> str:
    """Lowercase the message, drop apostrophes and punctuation, and collapse spaces."""
    text = message.lower().replace('’', "'").replace('‘', "'").replace("'", '')
    return ' '.join(re.sub(r'[^\w\s]', ' ', text).split())


def is_email_affirmative(message: str) -> bool:
    """True when the whole message is a plain yes such as "yes send it" or "go ahead"."""
    return plain(message) in AFFIRMATIVES
