"""Scope entry point: reconciles the extractor's scope flag with the allowlist and injection rules.

The allowlist lives in `allowlist.py` and the injection rule in `injection.py`; their public
names are re-exported here so importers use `insurance_claims.scope` only.
"""

import re

from insurance_claims.allowlist import (  # noqa: F401
    ACKNOWLEDGEMENTS,
    CLAIMS_WORDS,
    CLOSINGS,
    GREETINGS,
    IDENTITY_VALUE,
    PLEASANTRY_PHRASES,
    PROCESS_QUESTIONS,
    WAITING,
    is_allowlisted,
    kind,
    normalize,
)
from insurance_claims.extractor import Extraction
from insurance_claims.identity_text import identity_in_message
from insurance_claims.injection import INJECTION, has_off_topic_request, is_injection  # noqa: F401


def reconcile(extraction: Extraction, text: str) -> Extraction:
    """Apply the allowlist: when it matches, or the extractor's identity value appears in the message,
    the message is in scope whatever the extractor said.

    Args:
        extraction: The validated extractor output.
        text: The caller's message.

    Returns:
        The extraction, with `in_scope` forced true for allowlisted messages and any turn
        that carries an identity value (a name has no lexical pattern).
    """
    carries_identity = identity_in_message(extraction.identity, text)  # SCOPE-02: the value must be in the message
    injected = is_injection(text) and not has_off_topic_request(text)  # SAFE-09: a real off-topic ask still strikes
    if extraction.in_scope or not (carries_identity or is_allowlisted(text) or injected):
        return extraction
    return extraction.model_copy(update={'in_scope': True})


NEGATIVE_EMOTIONS = ('frustration', 'anger', 'anxiety', 'refusal', 'confusion')
REQUEST_MARKERS = re.compile(
    r'\?|\b(?:what|who|whom|whose|how|when|where|which|why|tell|write|give|show|explain|define|translate|'
    r'recommend|suggest|can you|could you|would you|do you|is there|are there|joke|recipe|poem|story)\b',
    re.I,
)


def emotional_only(extraction: Extraction, text: str) -> bool:
    """True when a message the extractor called out of scope is only a feeling about the service.

    Negative emotion at intensity 1 or more and no question or request wording. Such a message never
    earns an off-topic strike (EMO-02). "This is ridiculous, what is RL?" has a request, so it is not
    emotional only and still earns the strike.

    Args:
        extraction: The validated extraction (before `reconcile`).
        text: The caller's message.

    Returns:
        True for a complaint with no request in it.
    """
    emotion = extraction.emotion
    feeling = emotion.label in NEGATIVE_EMOTIONS and emotion.intensity >= 1
    return feeling and not extraction.in_scope and not REQUEST_MARKERS.search(text)
