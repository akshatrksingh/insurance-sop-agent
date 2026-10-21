"""Shared AppTest helpers for black-box tests (public names only)."""
import re

from streamlit.testing.v1 import AppTest

from conftest import ROOT

DASHES = ('\u2014', '\u2013')
EMOJI = re.compile('[\U0001F300-\U0001FAFF\u2600-\u27BF]')


def make_app(**kw):
    """Build an AppTest for app.py."""
    return AppTest.from_file(str(ROOT / 'app.py'), default_timeout=60)


def fake_class(llm):
    """Return a FakeLLM subclass that accepts and ignores client constructor arguments."""
    class _F(llm.FakeLLM):
        def __init__(self, *a, **k):
            super().__init__()
    return _F


def state_of(at):
    """Return the AppTest session_state as a plain dict."""
    return {k: at.session_state[k] for k in at.session_state}


def all_text(at):
    """Join the rendered text of every element kind plus button labels."""
    out = []
    for kind in ('markdown', 'text', 'error', 'warning', 'info', 'success', 'caption', 'exception', 'code', 'title', 'header', 'subheader'):
        out += [str(getattr(e, 'value', '')) for e in getattr(at, kind)]
    out += [str(b.label) for b in at.button]
    return '\n'.join(out)



REPLY_MARK = '0 of 3 confirmed. Any of these still work'
