"""CP0 failure paths: SAFE-04 (any LLM client exception never reaches the UI), failed turn visibility."""

import pytest

from failhelpers import app, visible, boom_backend, EXC_FACTORIES, T

@pytest.mark.parametrize('where', ['reply', 'extract', 'both', 'init'])
@pytest.mark.parametrize('name', list(EXC_FACTORIES))
def test_safe_04_any_llm_exception_never_reaches_ui(monkeypatch, logs, name, where):
    """SAFE-04: any exception type from the LLM client, with the token in its text, repr, args or cause,
    never reaches the UI as traceback, exception element, or token text; and never reaches logs."""
    boom_backend(monkeypatch, EXC_FACTORIES[name], where)
    at = app().run()
    at.chat_input[0].set_value('hello').run()
    t = visible(at)
    assert not at.exception, [e.value for e in at.exception]
    assert T not in t
    assert 'Traceback' not in t and 'File "' not in t
    assert all(T not in repr(at.session_state[k]) for k in at.session_state)
    assert T not in '\n'.join(logs)
    for e in at.error:
        assert T not in e.value and 'Error(' not in e.value and name.split('.')[-1] not in e.value


@pytest.mark.parametrize('name', ['RuntimeError', 'openai.AuthenticationError', 'TokenInRepr', 'chained_cause'])
def test_safe_04_session_state_has_no_token_after_failure(monkeypatch, name):
    """SAFE-04: after a failed turn the session object (and its view) hold no token."""
    boom_backend(monkeypatch, EXC_FACTORIES[name], 'both')
    at = app().run()
    at.chat_input[0].set_value('hello').run()
    sess = at.session_state['session']
    assert T not in repr(sess)
    assert T not in sess.view().model_dump_json()
    for k in at.session_state:
        if k != 'api_token':
            assert T not in repr(at.session_state[k]), k


@pytest.mark.parametrize('name', ['RuntimeError', 'openai.RateLimitError', 'openai.APITimeoutError', 'openai.AuthenticationError'])
def test_llm_failure_shows_one_plain_error(monkeypatch, name):
    """DEL-01 / FRONTEND 6: an LLM failure shows exactly one plain error, one sentence, no dash, no apology."""
    boom_backend(monkeypatch, EXC_FACTORIES[name], 'both')
    at = app().run()
    at.chat_input[0].set_value('hello').run()
    assert not at.exception
    assert len(at.error) == 1, [e.value for e in at.error]
    msg = at.error[0].value
    assert msg.strip() and '\u2014' not in msg and '\u2013' not in msg
    assert 'sorry' not in msg.lower() and 'apolog' not in msg.lower()
    assert '\n' not in msg.strip()


@pytest.mark.parametrize('name', ['RuntimeError', 'openai.AuthenticationError', 'openai.APIConnectionError'])
def test_failed_turn_caller_message_stays_visible(monkeypatch, name):
    """UI-01 (failed turn): the caller's message stays visible in the transcript when the turn fails."""
    boom_backend(monkeypatch, EXC_FACTORIES[name], 'both')
    at = app().run()
    at.chat_input[0].set_value('my unique message zq').run()
    assert 'my unique message zq' in visible(at)


def test_failed_turn_no_agent_reply_invented(monkeypatch):
    """UI-01 (failed turn): no Agent reply bubble is shown for a failed turn."""
    boom_backend(monkeypatch, EXC_FACTORIES['RuntimeError'], 'both')
    at = app().run()
    at.chat_input[0].set_value('hello').run()
    t = visible(at)
    assert 'This is a scripted reply.' not in t
    sess = at.session_state['session']
    assert not any(role == 'Agent' for role, _ in sess.view().turns)


def test_failed_turn_then_recovery_after_backend_fixed(monkeypatch):
    """DEL-01: after a failed turn, the next turn with a working backend succeeds and the error clears."""
    import insurance_claims.llm as llm
    state = {'fail': True}

    class Flaky(llm.FakeLLM):
        def __init__(self, *a, **k):
            super().__init__()

        def extract(self, *a, **k):
            if state['fail']:
                raise RuntimeError(T)
            return super().extract(*a, **k)

        def reply(self, *a, **k):
            if state['fail']:
                raise RuntimeError(T)
            return super().reply(*a, **k)

    monkeypatch.setenv('LLM_API_KEY', T)
    monkeypatch.setattr(llm, 'OpenAICompatLLM', Flaky)
    at = app().run()
    at.chat_input[0].set_value('first').run()
    assert at.error and not at.exception
    state['fail'] = False
    at.chat_input[0].set_value('second').run()
    assert not at.exception and not at.error
    assert 'This is a scripted reply.' in visible(at)


def test_failed_turn_reset_clears_error(monkeypatch):
    """UI-06: Reset after a failed turn clears the error and the transcript."""
    boom_backend(monkeypatch, EXC_FACTORIES['RuntimeError'], 'both')
    at = app().run()
    at.chat_input[0].set_value('hello').run()
    assert at.error
    next(b for b in at.button if b.label == 'Reset').click().run()
    assert not at.error and not at.exception
    assert 'Type a message to start the conversation.' in visible(at)


def test_failed_turn_does_not_count_toward_turn_state(monkeypatch):
    """A failed turn leaves phase VERIFY_ID and no gate done."""
    boom_backend(monkeypatch, EXC_FACTORIES['ValueError'], 'both')
    at = app().run()
    at.chat_input[0].set_value('hello').run()
    v = at.session_state['session'].view()
    assert v.phase == 'VERIFY_ID' and not any(g.done for p in v.phases for g in p.gates)


def test_handle_turn_direct_exception_contract(monkeypatch, record_property):
    """CODING 44: report whether handle_turn itself raises when the client raises (public API)."""
    from insurance_claims.orchestrator import handle_turn, new_session
    import insurance_claims.llm as llm

    class Boom(llm.FakeLLM):
        def reply(self, *a, **k):
            raise RuntimeError(T)

        def extract(self, *a, **k):
            raise RuntimeError(T)

    s = new_session()
    try:
        r = handle_turn(s, 'hello', Boom())
        outcome = f'returned reply={r.reply!r}'
        assert T not in r.reply and T not in s.view().model_dump_json()
    except Exception as e:
        outcome = f'raised {type(e).__name__}'
    record_property('handle_turn_with_failing_client', outcome)

