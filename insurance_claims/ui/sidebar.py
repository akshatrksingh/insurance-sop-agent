"""Sidebar rendering from `SessionView`: Session memory, SOP progress, Settings."""

import html

import streamlit as st

from insurance_claims.ui.trymenu import render_try_menu
from insurance_claims.views import SessionView

ICONS = {'done': '&#10003;', 'current': '&#9679;', 'pending': '&#9675;'}
STATUS_TEXT = {'done': 'done', 'current': 'current', 'pending': 'pending'}


def _memory_section(view: SessionView) -> None:
    """Render the Session memory section."""
    st.markdown('<div class="cs-side-title">Session memory</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="cs-note">Remembered from this chat. Cleared on reset.</div>',
        unsafe_allow_html=True,
    )
    for row in view.memory_rows:
        icon = {'good': ICONS['done'] + ' ', 'warn': ICONS['pending'] + ' '}.get(row.tone, '')
        st.markdown(
            f'<div class="cs-side-row"><span>{html.escape(row.label)}</span>'
            f'<span class="cs-tone-{row.tone}">{icon}{html.escape(row.value)}</span></div>',
            unsafe_allow_html=True,
        )


def _progress_section(view: SessionView) -> None:
    """Render SOP progress: four phases, gates under current and done phases."""
    st.markdown('<div class="cs-side-title">SOP progress</div>', unsafe_allow_html=True)
    parts = []
    for phase in view.phases:
        parts.append(
            f'<div class="cs-phase-row {phase.status}">{ICONS[phase.status]} '
            f'{phase.label}, {STATUS_TEXT[phase.status]}</div>'
        )
        if phase.status != 'pending':
            for gate in phase.gates:
                on = 'on' if gate.done else ''
                mark = ICONS['done'] if gate.done else ICONS['pending']
                parts.append(f'<div class="cs-gate {on}">{mark} {gate.label}</div>')
    st.markdown(''.join(parts), unsafe_allow_html=True)


def _details_section(view: SessionView) -> None:
    """Render the Show details toggle and, when on, the extractor field names of the last turn."""
    st.toggle('Show details', key='show_details')
    if st.session_state.get('show_details'):
        st.markdown('<div class="cs-side-title">Extractor fields, last turn</div>', unsafe_allow_html=True)
        names = ', '.join(view.extracted_fields) or 'none'
        st.markdown(f'<div class="cs-note">{html.escape(names)}</div>', unsafe_allow_html=True)
        st.markdown('<div class="cs-side-title">Emotion, last turn</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="cs-note">{html.escape(view.emotion)}</div>', unsafe_allow_html=True)


def render_sidebar(view: SessionView) -> None:
    """Render the native sidebar. The token field is stored under `st.session_state.api_token`."""
    with st.sidebar:
        _memory_section(view)
        _progress_section(view)
        _details_section(view)
        render_try_menu()
        st.markdown('<div class="cs-side-title">Settings</div>', unsafe_allow_html=True)
        st.text_input(
            'API token (optional)',
            type='password',
            key='api_token',
            help='Used only in this session. A token set in secrets or the environment takes priority.',
        )
