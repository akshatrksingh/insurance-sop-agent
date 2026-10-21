"""Email offer buttons and the preview card. Renders from `SessionView`, holds no logic."""

import html
from collections.abc import Callable

import streamlit as st

from insurance_claims.views import EmailPreview, SessionView


def _card(preview: EmailPreview) -> str:
    """Return the HTML for the mock email: recipient, subject in 600 weight, body."""
    body = html.escape(preview.body).replace('\n', '<br>')
    return (
        '<div class="cs-card">'
        f'<div class="cs-card-meta">Mock email to {html.escape(preview.to)}. Nothing was delivered.</div>'
        f'<div class="cs-card-subject">{html.escape(preview.subject)}</div>'
        f'<div class="cs-card-body">{body}</div></div>'
    )


def render_email(view: SessionView, on_send: Callable[[], None], on_skip: Callable[[], None]) -> None:
    """Show Send summary and Skip while the offer is open, and the preview card once sent.

    Args:
        view: The session view.
        on_send: Called when Send summary is clicked.
        on_skip: Called when Skip is clicked.
    """
    if view.email_offer_open:
        send, skip, _ = st.columns([1, 1, 4])
        send.button('Send summary', on_click=on_send, key='email_send')
        skip.button('Skip', on_click=on_skip, key='email_skip')
    if view.email_preview:
        st.markdown(_card(view.email_preview), unsafe_allow_html=True)
