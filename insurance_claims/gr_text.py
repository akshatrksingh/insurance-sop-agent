"""GR-lite fixed reply texts, kept apart so templates can tell a flagged reply from a normal one."""

from insurance_claims.state import Session

REFUSAL = 'I cannot help with that request.'
NOTICE = (
    'This message and its time were recorded for review. '
    'You can rephrase your question, or ask for a human representative.'
)
SUPPORT = (
    'I am sorry you are going through this. You deserve support right now. '
    'If you are in immediate danger, call your local emergency number. In the US you can call or text 988. '
    'Would you like me to connect you with a human representative?'
)


def replied(session: Session) -> bool:
    """True when a GR-lite reply is already in the transcript (so no greeting opener should follow).

    Args:
        session: The session, read for its `turns`.

    Returns:
        True when any agent turn is a GR-lite refusal or supportive reply.
    """
    fixed = (f'{REFUSAL} {NOTICE}', SUPPORT)
    return any(who == 'Agent' and text in fixed for who, text in session.turns)
