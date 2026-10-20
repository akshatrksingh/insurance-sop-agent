"""Reply output filters. Filters run in code, not in prompts."""

import re

_DASHES = re.compile('\\s*[\u2013\u2014]\\s*')


def clean_reply(text: str) -> str:
    """Replace em and en dashes with a comma (LANG-01) and trim whitespace."""
    return _DASHES.sub(', ', text).strip()
