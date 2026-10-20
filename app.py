"""Streamlit entry point for the claims support SOP agent. UI only, no business logic.

st.session_state keys:
    session:   the `Session` for this visitor, created by `new_session()`.
    api_token: optional token typed in the sidebar, kept in this browser session only.
    notice:    a plain error message to show under the header, or None.
    unsent:    the caller text of a turn that failed, shown in the transcript, or None.
"""

import html
import logging

import streamlit as st

from insurance_claims.config import load_settings
from insurance_claims.llm import LLMError, OpenAICompatLLM
from insurance_claims.orchestrator import handle_turn, new_session
from insurance_claims.ui.sidebar import render_sidebar
from insurance_claims.ui.theme import inject_css
from insurance_claims.ui.transcript import render_transcript

logging.basicConfig(level=logging.INFO)
for noisy in ('httpx', 'httpcore', 'openai'):
    logging.getLogger(noisy).setLevel(logging.WARNING)
MISSING_KEY = 'No API token is set, so add LLM_API_KEY to the secrets or paste a token under Settings.'

st.set_page_config(page_title='Claims support', layout='wide')
inject_css()

if 'session' not in st.session_state:
    st.session_state.session = new_session()
    st.session_state.notice = None
    st.session_state.unsent = None


def reset() -> None:
    """Clear the conversation and any notice."""
    st.session_state.session = new_session()
    st.session_state.notice = None
    st.session_state.unsent = None


def send(text: str) -> None:
    """Run one turn, or set a plain notice when the token is missing or the call fails."""
    st.session_state.unsent = text
    try:
        settings = load_settings(st.session_state.get('api_token', ''))
        if settings.api_key is None:
            st.session_state.notice = MISSING_KEY
            return
        llm = OpenAICompatLLM(
            settings.api_key.get_secret_value(),
            settings.base_url,
            settings.model,
            settings.reasoning_effort,
        )
        with st.spinner('Waiting for a reply'):
            handle_turn(st.session_state.session, text, llm)
        st.session_state.notice = None
        st.session_state.unsent = None
    except LLMError as exc:
        st.session_state.notice = str(exc)
    except Exception as exc:
        logging.getLogger(__name__).warning('Turn failed: %s', type(exc).__name__)
        st.session_state.notice = 'The reply failed, so try again.'


prompt = st.chat_input('Type a message')
if prompt:
    send(prompt)

view = st.session_state.session.view()
render_sidebar(view)

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


notice = st.session_state.notice or (MISSING_KEY if key_missing() else None)
if notice:
    st.error(notice)
render_transcript(view, st.session_state.unsent)
