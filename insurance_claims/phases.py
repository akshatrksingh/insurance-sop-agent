"""Per-phase context bundle builder."""

from insurance_claims.state import Session


def build_bundle(session: Session, caller_message: str) -> tuple[str, dict]:
    """Build the scoped context for the current phase.

    CP0 serves only VERIFY_ID. The bundle holds no stored values and no claim data.

    Args:
        session: The current session.
        caller_message: The caller's text, passed on for the user turn only.

    Returns:
        The prompt name and the bundle.
    """
    bundle = {
        'phase': session.phase,
        'phase_goal': 'Collect three identity details from the caller.',
        'matched_count': len(session.matched_factors),
        'caller_message': caller_message,
    }
    return 'verify_id', bundle
