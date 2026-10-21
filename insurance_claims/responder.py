"""Reply output filters and reply composition. Filters run in code, not in prompts."""

import logging
import re

from insurance_claims.grounded import fallback_reply
from insurance_claims.llm import FakeLLM, OpenAICompatLLM
from insurance_claims.grounding import misses_deadline, ungrounded

logger = logging.getLogger(__name__)

_DASHES = re.compile('\\s*[\u2013\u2014]\\s*')
_PLEASE = re.compile(r'\bplease\b', re.I)
_TIME_GREETING = re.compile(r'\bgood\s+(morning|afternoon|evening|night|day)\b', re.I)
_OPENER = re.compile(r'^\W*(hello|hi|hey|greetings|welcome)\b', re.I)
_VERIFIED = re.compile(r'\bverified\b', re.I)
_EMOTION = re.compile(r'\b(frustrat\w*|anxious|anxiety|angry|anger|confus\w*|upset)\b', re.I)


def clean_reply(text: str) -> str:
    """Replace em and en dashes with a comma (LANG-01) and trim whitespace."""
    return _DASHES.sub(', ', text).strip()


def banned_reason(text: str, bundle: dict) -> str | None:
    """Return a reason code when the text breaks an output rule, else None.

    Args:
        text: The candidate model text.
        bundle: The bundle it was generated from (`first_agent_turn`, `verified_this_turn`, `emotion`).

    Returns:
        One of `please`, `time_greeting`, `opener`, `repeat_verified`, `emotion`, `ungrounded`,
        `deadline`, or None.
    """
    if _PLEASE.search(text):
        return 'please'
    if _TIME_GREETING.search(text):
        return 'time_greeting'
    if not bundle.get('first_agent_turn') and _OPENER.search(text):
        return 'opener'
    if not bundle.get('verified_this_turn') and _VERIFIED.search(text):
        return 'repeat_verified'
    if 'emotion' not in bundle and _EMOTION.search(text):
        return 'emotion'
    if ungrounded(text, bundle):
        return 'ungrounded'
    if misses_deadline(text, bundle):
        return 'deadline'
    return None


def compose_reply(llm: OpenAICompatLLM | FakeLLM, prompt_name: str, bundle: dict) -> str:
    """Generate a post-verification reply, check it, regenerate once, then fall back.

    Args:
        llm: An `OpenAICompatLLM` or `FakeLLM`.
        prompt_name: The responder prompt name.
        bundle: The scoped context.

    Returns:
        The final reply. At most two reply calls are made, the second only when the
        output check flags the first.
    """
    for attempt in (1, 2):
        candidate = clean_reply(llm.reply(prompt_name, bundle))
        reason = banned_reason(candidate, bundle)
        if reason is None:
            return candidate
        logger.info('Reply rejected: attempt=%d reason=%s', attempt, reason)
    logger.info('Reply fell back to the fixed template')
    return fallback_reply(bundle)
