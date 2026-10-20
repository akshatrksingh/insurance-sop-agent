"""Shared helpers for black-box tests. Only public names from SYSTEM_DESIGN 4.5 are used."""
import logging
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SENTINEL = 'gsk_SENTINELTOKEN123456'

# Live tests need BOTH a key and RUN_LIVE=1. A key alone never allows a network call.
LIVE_ENABLED = bool(os.environ.get('LLM_API_KEY')) and os.environ.get('RUN_LIVE') == '1'


def live_active(request):
    return LIVE_ENABLED and request.node.get_closest_marker('live') is not None


def pytest_configure(config):
    config.addinivalue_line('markers', 'live: needs LLM_API_KEY and RUN_LIVE=1, and network')
    config.addinivalue_line('markers', 'local_server: may connect to loopback only')


def text_files():
    """Yield repo text files for scans, excluding venvs, caches, tests, fixtures."""
    skip = {'goaly-venv', '__pycache__', '.git', 'tests', 'fixtures', '.claude', '.pytest_cache'}
    exts = {'.py', '.md', '.txt', '.toml', '.json', '.css', '.yaml', '.yml'}
    for p in ROOT.rglob('*'):
        if p.is_file() and not (set(p.relative_to(ROOT).parts) & skip) and p.suffix in exts:
            yield p


@pytest.fixture
def no_key(monkeypatch):
    monkeypatch.delenv('LLM_API_KEY', raising=False)


@pytest.fixture
def fake_backend(monkeypatch):
    """Route the app's LLM to FakeLLM through the public name OpenAICompatLLM."""
    import insurance_claims.llm as llm
    from apphelpers import fake_class
    monkeypatch.setenv('LLM_API_KEY', SENTINEL)
    monkeypatch.setattr(llm, 'OpenAICompatLLM', fake_class(llm))


@pytest.fixture
def log_capture():
    import logging
    recs = []

    class H(logging.Handler):
        def emit(self, r):
            recs.append(self.format(r) + ' ' + repr(getattr(r, 'args', '')))

    h = H()
    h.setLevel(logging.DEBUG)
    root = logging.getLogger()
    old = root.level
    root.setLevel(logging.DEBUG)
    root.addHandler(h)
    yield recs
    root.removeHandler(h)
    root.setLevel(old)


@pytest.fixture
def logs():
    recs = []

    class H(logging.Handler):
        def emit(self, r):
            try:
                recs.append(self.format(r) + ' ' + repr(r.args) + ' ' + repr(r.exc_info) + ' ' + str(r.getMessage()))
                if r.exc_info:
                    import traceback
                    recs.append(''.join(traceback.format_exception(*r.exc_info)))
            except Exception:
                pass

    h = H()
    root = logging.getLogger()
    old = root.level
    root.setLevel(logging.DEBUG)
    root.addHandler(h)
    yield recs
    root.removeHandler(h)
    root.setLevel(old)



@pytest.fixture(autouse=True)
def offline_guard(request, monkeypatch):
    """Fail any test that opens a network connection. Tests marked local_server may reach loopback only.
    Live tests are exempt only when LLM_API_KEY is set and RUN_LIVE=1."""
    import socket
    attempts = []
    real_connect, real_connect_ex = socket.socket.connect, socket.socket.connect_ex
    live = live_active(request)
    local_ok = request.node.get_closest_marker('local_server') is not None

    def allowed(addr):
        host = addr[0] if isinstance(addr, tuple) else str(addr)
        return live or (local_ok and host in ('127.0.0.1', 'localhost', '::1')) or not isinstance(addr, tuple)

    def connect(self, addr):
        if not allowed(addr):
            attempts.append(repr(addr))
            raise OSError('offline guard: connection blocked')
        return real_connect(self, addr)

    def connect_ex(self, addr):
        if not allowed(addr):
            attempts.append(repr(addr))
            return 111
        return real_connect_ex(self, addr)

    monkeypatch.setattr(socket.socket, 'connect', connect)
    monkeypatch.setattr(socket.socket, 'connect_ex', connect_ex)
    yield
    assert not attempts, f'network connection attempted: {attempts}'


@pytest.fixture(autouse=True)
def isolated_config(request, monkeypatch):
    """Make every test independent of the developer's secrets file and environment.
    Streamlit secrets files are disabled, LLM_* and limit env vars are cleared (except for live tests when RUN_LIVE=1)."""
    from streamlit import config
    from streamlit.runtime.secrets import secrets_singleton
    old = config.get_option('secrets.files')
    config.set_option('secrets.files', [])
    secrets_singleton._reset()
    names = ['LLM_BASE_URL', 'LLM_MODEL', 'LLM_REASONING_EFFORT', 'MAX_OFF_TOPIC', 'MAX_VERIFY_FAILS', 'MAX_TURNS']
    if not live_active(request):
        names.append('LLM_API_KEY')
    for n in names:
        monkeypatch.delenv(n, raising=False)
    yield
    secrets_singleton._reset()
    config.set_option('secrets.files', old)
