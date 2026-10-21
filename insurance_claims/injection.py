"""Injection rule: deterministic match for instruction-style or protected-data requests."""

import re

from insurance_claims.allowlist import CLAIMS_WORDS, normalize

INJECTION = re.compile(
    r'\b(?:ignore|disregard|forget|override|bypass)\b.{0,30}\b(?:rules|instructions|prompt|guidelines|verification)\b'
    r'|\b(?:you are now|act as|pretend|roleplay|new role)\b'
    r'|\b(?:system prompt|your prompt|your instructions|your rules)\b'
    r'|\b(?:set|mark)\b.{0,20}\bverified\b'
    r'|\b(?:i am|i m|you are now)\b.{0,15}\b(?:verified|admin|administrator)\b'
    r'|\b(?:skip|skipping|bypass|bypassing|avoid|waive)\b.{0,20}\b(?:verification|identity|id|check|step)\b',
)


def is_injection(text: str) -> bool:
    """Return True for instruction-style or protected-data requests (SAFE-06).

    Args:
        text: The caller's message.

    Returns:
        True when it tries to change rules, claim a role or verified status, reveal the
        prompt. Asking for the caller's own claims is not injection (SAFE-09). The match is deterministic and does not touch state.
    """
    return bool(INJECTION.search(normalize(text)))


OFF_TOPIC_ASK = re.compile(
    r'\b(?:what|who|how|when|where|which|why|explain|define|translate|write|recommend|joke|recipe|poem|story)\b'
)


def has_off_topic_request(text: str) -> bool:
    """Return True when injection text also carries a question or request that is not about claims.

    The injection words are removed first, so "ignore your rules, what is RL?" counts and
    "ignore your rules" does not. Claims vocabulary in the rest of the message means it is not off topic.

    Args:
        text: The caller's message.

    Returns:
        True when the rest of the message holds a question word or request verb and no claims vocabulary.
    """
    rest = INJECTION.sub(' ', normalize(text))
    return bool(OFF_TOPIC_ASK.search(rest)) and not CLAIMS_WORDS.search(rest)
