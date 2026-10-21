"""Dash filter for every reply (LANG-01). Source holds only escapes, never the dash characters."""

import re

_COMMA_DASHES = re.compile('\\s*[\u2013\u2014\u2015\u2012\uFE58]\\s*')  # en, em, bar, figure, small em: comma
_HYPHENS = re.compile('[\u2010\u2011\u2212\uFE63\uFF0D]')  # hyphen-like: plain ASCII hyphen, dates stay valid


def clean_reply(text: str) -> str:
    """Replace dash-like characters (LANG-01) and trim whitespace.

    Args:
        text: A reply.

    Returns:
        Em, en, horizontal bar, figure dash and small em dash become a comma; the hyphen,
        non-breaking hyphen, minus sign, small hyphen and fullwidth hyphen become `-`.
    """
    return _COMMA_DASHES.sub(', ', _HYPHENS.sub('-', text)).strip()
