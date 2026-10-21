"""Transcript rendering from `SessionView`. Text is HTML-escaped before display."""

import html

import streamlit as st

from insurance_claims.views import Event, SessionView

EVENT_CLASS = {'phase_done': 'done', 'email_sent': 'done', 'handoff': 'handoff'}


def _escape(text: str) -> str:
    """Escape text for HTML and keep line breaks."""
    return html.escape(text).replace('\n', '<br>')


def _event_row(event: Event) -> str:
    """Return the HTML for one event row."""
    kind = 'detail' if event.level == 'detail' else EVENT_CLASS.get(event.kind, '')
    return f'<div class="cs-event {kind}">{_escape(event.text)}</div>'


def render_transcript(view: SessionView, unsent: str | None = None) -> None:
    """Render the speaker rows and key events in order, then any unsent caller text.

    Args:
        view: The session view.
        unsent: Caller text of a failed turn, shown after the turns, or None.
    """
    if not view.turns and not unsent:
        st.markdown(
            '<div class="cs-empty">Type a message to start the conversation.</div>',
            unsafe_allow_html=True,
        )
        return
    key_events = [e for e in view.events if e.level == 'key']
    rows = []
    for index, (who, text) in enumerate(view.turns):
        rows += [_event_row(e) for e in key_events if e.at == index]
        rows.append(
            f'<div class="cs-row"><div class="cs-who">{_escape(who)}</div>'
            f'<div class="cs-msg">{_escape(text)}</div></div>'
        )
    rows += [_event_row(e) for e in key_events if e.at is None or e.at >= len(view.turns)]
    if unsent:
        rows.append(
            f'<div class="cs-row"><div class="cs-who">Caller</div>'
            f'<div class="cs-msg">{_escape(unsent)}</div></div>'
        )
    st.markdown(''.join(rows), unsafe_allow_html=True)
