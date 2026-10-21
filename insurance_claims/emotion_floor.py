"""Deterministic emotion floor (EMO-01, EMO-02): explicit anger phrases never score below intensity 2."""

import re

from insurance_claims.extractor import Extraction

PHRASES = (
    'ridiculous',
    'useless',
    'unacceptable',
    'outrageous',
    'unbelievable',
    'i already told you',
    'this is a joke',
    'fed up',
    'sick of this',
    'waste of time',
)
NEGATIVE_LABELS = ('frustration', 'anger', 'anxiety')
FLOOR_INTENSITY = 2
_PATTERN = re.compile(r'\b(?:' + '|'.join(re.escape(p) for p in PHRASES) + r')\b')


def _normalize(text: str) -> str:
    """Lowercase, straighten apostrophes, and collapse whitespace."""
    straight = text.replace('’', "'").replace('‘', "'").replace('`', "'")
    return ' '.join(straight.lower().split())


def has_floor_phrase(message: str) -> bool:
    """Return True when the message holds a whole word or phrase from `PHRASES`."""
    return _PATTERN.search(_normalize(message)) is not None


def apply_floor(extraction: Extraction, message: str) -> Extraction:
    """Raise the emotion of an extraction when the message holds an explicit anger phrase.

    Intensity below 2 becomes 2, never lowered and never set to 3. A label that is not
    frustration, anger or anxiety becomes frustration. Nothing else changes.

    Args:
        extraction: The validated extractor output.
        message: The caller's message.

    Returns:
        The same extraction when no phrase matches, else a copy with the floor applied.
    """
    if not has_floor_phrase(message):
        return extraction
    emotion = extraction.emotion
    label = emotion.label if emotion.label in NEGATIVE_LABELS else 'frustration'
    intensity = max(emotion.intensity, FLOOR_INTENSITY)
    if label == emotion.label and intensity == emotion.intensity:
        return extraction
    return extraction.model_copy(update={'emotion': emotion.model_copy(update={'label': label, 'intensity': intensity})})
