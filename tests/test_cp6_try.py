"""CP6 Try menu switch (TRY_MENU) through env and Streamlit secrets."""
import pytest

from apphelpers import fake_class, make_app

OFF_VALUES = ['off', 'false', '0', 'no', 'OFF', 'False']
DEMO_TEXT = ('Margaret', 'Yaven', 'Pat Morgan', 'Chen', 'POL-9921', 'Demo identities', '4472', '1985-03-15')


@pytest.fixture(autouse=True)
def backend(monkeypatch):
    """A fake LLM and a fake token so the app renders fully."""
    import insurance_claims.llm as llm
    monkeypatch.setenv('LLM_API_KEY', 'tok_try_menu_test')
    monkeypatch.setattr(llm, 'OpenAICompatLLM', fake_class(llm))


def sidebar_text(at):
    """All text the sidebar renders, including widget labels and options."""
    out = [str(getattr(e, 'value', '')) for kind in ('markdown', 'caption', 'text', 'info', 'warning', 'error') for e in getattr(at.sidebar, kind)]
    for box in at.sidebar.selectbox:
        out += [str(box.label)] + [str(o) for o in box.options]
    out += [str(b.label) for b in at.sidebar.button] + [str(t.label) for t in at.sidebar.text_input]
    return '\n'.join(out)


def test_try_menu_default_on_shows_the_menu():
    """Try menu: with TRY_MENU unset the sidebar shows the menu with its options."""
    at = make_app().run()
    assert len(at.sidebar.selectbox) == 1 and len(at.sidebar.selectbox[0].options) >= 3
    assert 'Demo identities' in sidebar_text(at)


@pytest.mark.parametrize('value', ['on', 'true', '1', 'yes'])
def test_try_menu_on_values_keep_the_menu(monkeypatch, value):
    """Try menu: an on value keeps the menu."""
    monkeypatch.setenv('TRY_MENU', value)
    assert len(make_app().run().sidebar.selectbox) == 1


@pytest.mark.parametrize('value', OFF_VALUES)
def test_try_menu_off_via_env_hides_menu_and_demo_text(monkeypatch, value):
    """Try menu: TRY_MENU in env set to an off value removes the menu and every demo identity string from the sidebar."""
    monkeypatch.setenv('TRY_MENU', value)
    at = make_app().run()
    assert not at.exception
    assert len(at.sidebar.selectbox) == 0
    t = sidebar_text(at)
    assert [d for d in DEMO_TEXT if d in t] == []


@pytest.mark.parametrize('value', OFF_VALUES)
def test_try_menu_off_via_secret_hides_menu_and_demo_text(value):
    """Try menu: TRY_MENU in Streamlit secrets set to an off value removes the menu and every demo identity string."""
    at = make_app()
    at.secrets['TRY_MENU'] = value
    at.run()
    assert not at.exception
    assert len(at.sidebar.selectbox) == 0
    assert [d for d in DEMO_TEXT if d in sidebar_text(at)] == []


def test_try_menu_secret_wins_over_env(monkeypatch):
    """Try menu: secrets win over the env var, as the README states."""
    monkeypatch.setenv('TRY_MENU', 'on')
    at = make_app()
    at.secrets['TRY_MENU'] = 'off'
    at.run()
    assert len(at.sidebar.selectbox) == 0


def test_try_menu_off_keeps_the_rest_of_the_sidebar(monkeypatch):
    """Try menu: with the menu off the token field, memory and SOP progress still show and a turn still works."""
    monkeypatch.setenv('TRY_MENU', 'off')
    at = make_app().run()
    assert len(at.sidebar.text_input) == 1
    t = sidebar_text(at)
    assert 'Session memory' in t and 'SOP progress' in t
    at.chat_input[0].set_value('hello').run()
    assert not at.exception and at.session_state['session'].view().turns
