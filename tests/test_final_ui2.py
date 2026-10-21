"""Final fix batch: UI-03 sidebar caption, NFR-08 notice wording and banner (B34), INT-03 foreign case id hint not kept (B37)."""
import json

import pytest

from apphelpers import all_text, make_app
from cp1helpers import CLAIMS, MARGARET
from cp2helpers import S1_EX, S1_TEXT, rows, run

CAPTION = 'Test view. Not shown to callers in production.'
NOTICE = 'This chat reached its message limit. Reset to start over, or paste your Groq key in the sidebar to keep going.'
FOREIGN_IDS = [c['case_id'] for c in CLAIMS if c['party_id'] != MARGARET['party_id']]


def sidebar_text(at):
    """Sidebar markdown, captions and text joined."""
    parts = [str(m.value) for m in at.sidebar.markdown] + [str(c.value) for c in at.sidebar.caption]
    return '\n'.join(parts)


def capped(monkeypatch, fake_backend, n=2):
    """AppTest past a cap of n messages, capped once."""
    monkeypatch.setenv('MAX_TURNS', str(n))
    at = make_app().run()
    for i in range(n):
        at.chat_input[0].set_value(f'hello {i}').run()
    at.chat_input[0].set_value('over the cap').run()
    return at


def test_ui_03_sidebar_caption_under_session_memory(fake_backend):
    """UI-03: the sidebar shows the test view caption after the Session memory heading, from the first page load."""
    at = make_app().run()
    text = sidebar_text(at)
    assert CAPTION in text and text.index('Session memory') < text.index(CAPTION)
    assert CAPTION not in '\n'.join(str(m.value) for m in at.main.markdown)


def test_nfr_08_b34_cap_notice_has_the_exact_wording(monkeypatch, fake_backend):
    """NFR-08: at the cap the page shows the exact notice naming the Groq key."""
    at = capped(monkeypatch, fake_backend)
    assert NOTICE in all_text(at) and not at.exception and 'token' not in NOTICE


def test_nfr_08_b34_banner_clears_as_soon_as_a_key_is_in_the_field(monkeypatch, fake_backend):
    """NFR-08: typing a key in the sidebar field clears the notice on that rerun, before another message is sent."""
    at = capped(monkeypatch, fake_backend)
    assert NOTICE in all_text(at)
    at.sidebar.text_input[0].set_value('visitor_key_xyz').run()
    assert NOTICE not in all_text(at) and not at.exception


def test_nfr_08_b34_banner_returns_when_the_field_is_emptied(monkeypatch, fake_backend):
    """NFR-08: emptying the field and sending a message brings the notice back."""
    at = capped(monkeypatch, fake_backend)
    at.sidebar.text_input[0].set_value('visitor_key_xyz').run()
    at.sidebar.text_input[0].set_value('').run()
    at.chat_input[0].set_value('over the cap again').run()
    assert NOTICE in all_text(at)


@pytest.mark.parametrize('foreign', FOREIGN_IDS)
def test_int_03_b37_foreign_case_id_hint_after_resolution_is_not_kept(foreign):
    """INT-03, MEM-04: a foreign case id typed after the case is resolved is absent from memory and the Case id row, the resolved case stays."""
    s, llm, rs = run([(S1_TEXT, S1_EX), ('x', {'hints': {'case_id': foreign}})])
    view = json.dumps(s.view().model_dump()['memory_rows'])
    assert 'Case id' not in rows(s) and foreign not in view and rows(s)['Resolved case'] == 'CL-2048'
    assert foreign not in rs[1].reply and 'CL-2048' in rs[1].reply
    follow = run([(S1_TEXT, S1_EX), ('x', {'hints': {'case_id': foreign}}), ('y', {})])
    assert 'Case id' not in rows(follow[0])
