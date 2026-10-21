"""Injection rule: deterministic match for instruction-style or protected-data requests."""

import re

from insurance_claims.allowlist import normalize

INJECTION = re.compile(
    r'\b(?:ignore|disregard|forget|override|bypass)\b.{0,30}\b(?:rules|instructions|prompt|guidelines|verification)\b'
    r'|\b(?:you are now|act as|pretend|roleplay|new role)\b'
    r'|\b(?:system prompt|your prompt|your instructions|your rules)\b'
    r'|\b(?:set|mark)\b.{0,20}\bverified\b'
    r'|\b(?:i am|i m|am i|you are now)\b.{0,15}\b(?:verified|admin|administrator)\b'
    r'|\b(?:show|list|give|print)\b.{0,15}\b(?:all|every)\b.{0,10}\bclaims?\b'
    r'|\b(?:skip|skipping|bypass|bypassing|avoid|waive)\b.{0,20}\b(?:verification|identity|id|check|step)\b',
)


def is_injection(text: str) -> bool:
    """Return True for instruction-style or protected-data requests (SAFE-06).

    Args:
        text: The caller's message.

    Returns:
        True when it tries to change rules, claim a role or verified status, reveal the
        prompt, or list every claim. The match is deterministic and does not touch state.
    """
    return bool(INJECTION.search(normalize(text)))
