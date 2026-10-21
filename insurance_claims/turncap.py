"""Session turn cap (NFR-08): counts Caller messages and picks the settings for a turn."""

from insurance_claims.config import Settings, load_settings
from insurance_claims.state import Session

CAP_NOTICE = (
    'This chat reached its message limit. Reset to start over, '
    'or paste your Groq key in the sidebar to keep going.'
)


def caller_turns(session: Session) -> int:
    """Return how many Caller messages the transcript holds, flagged and failed ones included."""
    return sum(1 for who, _ in session.turns if who == 'Caller')


def cap_reached(session: Session, limit: int) -> bool:
    """Return True when the transcript holds `limit` Caller messages and the cap was not lifted.

    A limit of 0 means no cap.
    """
    return limit > 0 and not session.cap_lifted and caller_turns(session) >= limit


def cap_banner(session: Session, own_token: str, limit: int) -> str | None:
    """Return the cap notice to show now, or None. A visitor key in the field clears it at once."""
    return CAP_NOTICE if cap_reached(session, limit) and not own_token.strip() else None


def settings_for_turn(session: Session, own_token: str) -> Settings:
    """Return the settings for the next turn, lifting the cap when a visitor token takes over.

    Once the cap is reached, a visitor token in the sidebar field lifts the cap and is the
    key for that turn. With the field empty the cap applies again and no model call is made.
    Before the cap, the normal key order applies.

    Args:
        session: The session, `cap_lifted` is set on it for this turn only.
        own_token: The sidebar token, may be empty.

    Returns:
        The settings to build the model client from.
    """
    own = own_token.strip()
    session.cap_lifted = False  # the lift holds only while a visitor token is in the field
    base = load_settings(own)
    if own and cap_reached(session, base.max_turns):
        session.cap_lifted = True
        return load_settings(own, prefer_token=True)
    return base
