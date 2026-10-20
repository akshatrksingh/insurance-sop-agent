"""Helpers for failure-path tests."""

from types import SimpleNamespace

import openai
from streamlit.testing.v1 import AppTest

from conftest import ROOT, SENTINEL

T = SENTINEL


def fake_request():
    """Stand-in for an HTTP request object. No HTTP library is used by the tests."""
    return SimpleNamespace(method='POST', url='http://x/v1/chat/completions', headers={})


def _resp(code):
    """Stand-in for an HTTP response object with the attributes the openai exceptions read."""
    return SimpleNamespace(status_code=code, headers={}, request=fake_request(),
                           json=lambda: {'error': {'message': f'bad key {T}'}}, text=T)


class ConnectError(Exception):
    """Generic transport error type, standing in for a low level connect failure."""


class CustomErr(Exception):
    pass


class TokenInRepr(Exception):
    def __repr__(self):
        return f'TokenInRepr({T})'

    def __str__(self):
        return T


def _chained():
    try:
        raise ValueError(f'inner {T}')
    except ValueError as inner:
        e = RuntimeError('outer')
        e.__cause__ = inner
        return e


EXC_FACTORIES = {
    'RuntimeError': lambda: RuntimeError(f'failure with {T}'),
    'ValueError': lambda: ValueError(f'bad {T}'),
    'KeyError': lambda: KeyError(T),
    'TypeError': lambda: TypeError(T),
    'TimeoutError': lambda: TimeoutError(f'timed out {T}'),
    'ConnectionError': lambda: ConnectionError(f'refused {T}'),
    'OSError': lambda: OSError(T),
    'CustomErr': lambda: CustomErr(f'custom {T}'),
    'TokenInRepr': lambda: TokenInRepr(),
    'args_only': lambda: Exception(T, {'Authorization': f'Bearer {T}'}),
    'chained_cause': _chained,
    'openai.AuthenticationError': lambda: openai.AuthenticationError(f'Incorrect API key {T}', response=_resp(401), body=None),
    'openai.RateLimitError': lambda: openai.RateLimitError(f'rate {T}', response=_resp(429), body=None),
    'openai.APIStatusError500': lambda: openai.InternalServerError(f'oops {T}', response=_resp(500), body=None),
    'openai.BadRequestError': lambda: openai.BadRequestError(f'bad {T}', response=_resp(400), body=None),
    'openai.APIConnectionError': lambda: openai.APIConnectionError(message=f'conn {T}', request=fake_request()),
    'openai.APITimeoutError': lambda: openai.APITimeoutError(request=fake_request()),
    'ConnectError': lambda: ConnectError(f'down {T}'),
}


def boom_backend(monkeypatch, make_exc, where):
    import insurance_claims.llm as llm
    calls = {'n': 0}

    class Boom(llm.FakeLLM):
        def __init__(self, *a, **k):
            super().__init__()
            if where == 'init':
                raise make_exc()

        def extract(self, *a, **k):
            if where in ('extract', 'both'):
                calls['n'] += 1
                raise make_exc()
            return super().extract(*a, **k)

        def reply(self, *a, **k):
            if where in ('reply', 'both'):
                calls['n'] += 1
                raise make_exc()
            return super().reply(*a, **k)

    monkeypatch.setenv('LLM_API_KEY', T)
    monkeypatch.setattr(llm, 'OpenAICompatLLM', Boom)
    return calls


def app():
    return AppTest.from_file(str(ROOT / 'app.py'), default_timeout=60)


def visible(at):
    out = []
    for kind in ('markdown', 'text', 'error', 'warning', 'info', 'success', 'caption', 'exception', 'code', 'title', 'header', 'subheader'):
        out += [str(getattr(e, 'value', '')) for e in getattr(at, kind)]
    for m in at.chat_message:
        out += [str(getattr(c, 'value', '')) for c in m]
    out += [str(b.label) for b in at.button]
    return '\n'.join(out)


