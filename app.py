"""Streamlit entry point for the claims support SOP agent. UI only, no business logic.

st.session_state keys:
    session:   the `Session` for this visitor, created by `new_session()`.
    api_token: the Groq key pasted in the sidebar (bring your own key), kept in this browser session only.
    notice:    a plain error message to show under the header, or None.
    try_choice: the message picked in the Try menu, or None.
    chat_text: the chat input's text, set by the Try menu to paste a message.
    show_details: the Show details toggle in the sidebar (detail events and extractor field names).
    email_send, email_skip: the email offer buttons (Send summary, Skip), shown while an offer is open.
"""

import html
import logging

import streamlit as st

from insurance_claims.config import load_settings
from insurance_claims.llm import LLMError, OpenAICompatLLM
from insurance_claims.orchestrator import handle_choice, handle_turn, new_session, record_failed
from insurance_claims.ui.emailcard import render_email
from insurance_claims.ui.sidebar import render_sidebar
from insurance_claims.ui.theme import inject_css
from insurance_claims.ui.trymenu import CHAT_KEY
from insurance_claims.ui.transcript import render_transcript
from insurance_claims.turncap import CAP_NOTICE, cap_reached, settings_for_turn

logging.basicConfig(level=logging.INFO)
for noisy in ('httpx', 'httpcore', 'openai'):
    logging.getLogger(noisy).setLevel(logging.WARNING)
MISSING_KEY = 'Paste your Groq key in the sidebar to start.'

st.set_page_config(page_title='Claims support', layout='wide')
inject_css()

if 'session' not in st.session_state:
    st.session_state.session = new_session()
    st.session_state.notice = None


def reset() -> None:
    """Clear the conversation, any notice, and the pasted key (the cap lift lives on the new session)."""
    st.session_state.session = new_session()
    st.session_state.api_token = ''
    st.session_state.notice = None


def send(text: str) -> None:
    """Run one turn. A failed turn keeps the caller message in the transcript and sets a plain notice."""
    session = st.session_state.session
    try:
        settings = settings_for_turn(session, st.session_state.get('api_token', ''))
        if settings.api_key is None:
            record_failed(session, text)
            st.session_state.notice = MISSING_KEY
            return
        llm = OpenAICompatLLM(
            settings.api_key.get_secret_value(),
            settings.base_url,
            settings.model,
            settings.reasoning_effort,
        )
        with st.spinner('Waiting for a reply'):
            result = handle_turn(session, text, llm)
        st.session_state.notice = CAP_NOTICE if result.capped else None
    except LLMError as exc:
        record_failed(session, text)
        st.session_state.notice = str(exc)
    except Exception as exc:
        logging.getLogger(__name__).warning('Turn failed: %s', type(exc).__name__)
        record_failed(session, text)
        st.session_state.notice = 'The reply failed, so try again.'


def choose(choice: str) -> None:
    """Apply an email button (`yes` or `no`) through the same code path as typed consent."""
    handle_choice(st.session_state.session, choice)


prompt = st.chat_input('Type a message', key=CHAT_KEY)
if prompt:
    send(prompt)

view = st.session_state.session.view()
settings = load_settings(st.session_state.get('api_token', ''))
render_sidebar(view, settings.try_menu)

title, phase, action = st.columns([3, 3, 1], vertical_alignment='center')
title.markdown('<span class="cs-title">Claims support</span>', unsafe_allow_html=True)
phase.markdown(f'<span class="cs-phase">Phase: {html.escape(view.phase_label)}</span>', unsafe_allow_html=True)
action.button('Reset', on_click=reset)

def key_missing() -> bool:
    """Return True when no API token is available from any source."""
    try:
        return load_settings(st.session_state.get('api_token', '')).api_key is None
    except Exception:
        return False


capped = cap_reached(st.session_state.session, settings.max_turns)
notice = st.session_state.notice or (CAP_NOTICE if capped else None) or (MISSING_KEY if key_missing() else None)
if notice:
    st.error(notice)
render_transcript(view, bool(st.session_state.get('show_details')))
render_email(view, lambda: choose('yes'), lambda: choose('no'))
