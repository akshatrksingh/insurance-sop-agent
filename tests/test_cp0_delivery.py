"""CP0 DEL-01 delivery tests: local run, README, secrets, live."""
import os
import re
import socket
import subprocess
import sys
import time
import urllib.request

import pytest

from apphelpers import all_text, make_app
from conftest import LIVE_ENABLED, ROOT, SENTINEL
from failhelpers import EXC_FACTORIES, boom_backend

def _free_port():
    """Return a free local TCP port."""
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


@pytest.mark.local_server
def test_del_01_streamlit_run_serves_app_locally(no_key, record_property):
    """DEL-01: `streamlit run app.py` starts and serves health OK."""
    port = _free_port()
    env = {k: v for k, v in os.environ.items() if k != 'LLM_API_KEY'}
    p = subprocess.Popen(
        [sys.executable, '-m', 'streamlit', 'run', 'app.py', '--server.headless', 'true',
         '--server.port', str(port), '--browser.gatherUsageStats', 'false'],
        cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    start = time.time()
    ok = None
    try:
        while time.time() - start < 30:
            try:
                ok = urllib.request.urlopen(f'http://127.0.0.1:{port}/_stcore/health', timeout=2).read()
                break
            except Exception:
                time.sleep(0.5)
        record_property('streamlit_run_health', f'{ok!r} after {time.time() - start:.1f}s')
        assert ok == b'ok'
    finally:
        p.terminate()
        try:
            out = p.communicate(timeout=10)[0]
        except Exception:
            p.kill()
            out = ''
    assert 'Traceback' not in out


def test_del_01_readme_and_requirements_exist():
    """DEL-01: repo has requirements.txt and README with run command."""
    assert (ROOT / 'requirements.txt').is_file()
    r = (ROOT / 'README.md').read_text()
    assert 'streamlit run app.py' in r
    assert 'pip install -r requirements.txt' in r
    assert 'LLM_API_KEY' in r


def test_del_01_secrets_not_committed_files():
    """DEL-01: .gitignore covers secrets.toml; no key-shaped string in any other text file.
    The gitignored secrets file itself is never opened, and no matched value is reported."""
    gi = (ROOT / '.gitignore').read_text()
    assert 'secrets.toml' in gi
    ignored = ROOT / '.streamlit' / 'secrets.toml'
    hits = []
    for p in ROOT.rglob('*'):
        if p == ignored or not p.is_file() or {'goaly-venv', '__pycache__', '.git'} & set(p.parts):
            continue
        if p.suffix in {'.py', '.md', '.toml', '.txt', '.json'}:
            if re.search(r'(gsk_|sk-)[A-Za-z0-9]{20,}', p.read_text(errors='replace')):
                hits.append(str(p.relative_to(ROOT)))
    assert not hits, hits


@pytest.mark.live
@pytest.mark.skipif(not LIVE_ENABLED, reason='needs LLM_API_KEY and RUN_LIVE=1')
def test_live_round_trip():
    """DEL-01 live: real model replies to hello."""
    from insurance_claims.llm import OpenAICompatLLM
    from insurance_claims.orchestrator import handle_turn, new_session
    r = handle_turn(new_session(), 'hello', OpenAICompatLLM(
        api_key=os.environ['LLM_API_KEY'],
        base_url=os.environ.get('LLM_BASE_URL', 'https://api.groq.com/openai/v1'),
        model=os.environ.get('LLM_MODEL', 'openai/gpt-oss-20b'),
        reasoning_effort=os.environ.get('LLM_REASONING_EFFORT', 'low')))
    assert r.reply


def test_del_01_unreachable_service_plain_error(monkeypatch):
    """DEL-01 / SAFE-04: connection failure shows a plain error, no traceback, no token."""
    boom_backend(monkeypatch, EXC_FACTORIES['openai.APIConnectionError'], 'both')
    at = make_app().run()
    at.chat_input[0].set_value('hello').run()
    t = all_text(at)
    assert not at.exception and at.error
    assert SENTINEL not in t and 'Traceback' not in t


def test_safe_04_sidebar_token_location_in_session_state(no_key, record_property):
    """SAFE-04 / SYSTEM_DESIGN 5: report which session_state keys hold the sidebar token."""
    at = make_app().run()
    at.sidebar.text_input[0].set_value(SENTINEL).run()
    keys = [k for k in at.session_state if SENTINEL in repr(at.session_state[k])]
    record_property('keys_holding_sidebar_token', keys)
    assert keys == ['api_token']
    assert SENTINEL not in repr(at.session_state['session'])
