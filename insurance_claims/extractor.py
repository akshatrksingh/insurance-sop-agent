"""Extractor output models, the strict JSON schema, and fail-safe parsing (SYSTEM_DESIGN 4.2)."""

import logging
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

logger = logging.getLogger(__name__)

INTENTS = (
    'status_inquiry',
    'denial_question',
    'document_submission',
    'next_steps',
    'general_claim_question',
)
EMOTION_LABELS = ('neutral', 'frustration', 'anxiety', 'anger', 'confusion', 'refusal')


class Identity(BaseModel):
    """Identity details the caller stated this turn."""

    full_name: str | None = None
    dob: str | None = None
    phone: str | None = None
    email: str | None = None
    id_last4: str | None = None
    policy_number: str | None = None


class Hints(BaseModel):
    """Case and intent hints the caller stated this turn."""

    case_type: str | None = None
    status: str | None = None
    month: str | None = None
    case_id: str | None = None
    intent: str | None = None

    @field_validator('intent')
    @classmethod
    def _known_intent(cls, value: str | None) -> str | None:
        """Keep only one of the five known intents."""
        return value if value in INTENTS else None


class Emotion(BaseModel):
    """Emotion label and intensity from 0 to 3."""

    label: Literal['neutral', 'frustration', 'anxiety', 'anger', 'confusion', 'refusal'] = 'neutral'
    intensity: int = Field(default=0, ge=0, le=3)


class Extraction(BaseModel):
    """Structured reading of one caller message. An empty Extraction is the safe default."""

    identity: Identity = Identity()
    hints: Hints = Hints()
    emotion: Emotion = Emotion()
    in_scope: bool = True
    wants_human: bool = False
    refused_verification: bool = False
    wants_to_end: bool = False
    consent: Literal['yes', 'no'] | None = None
    asked_about_factor: Literal['full_name', 'dob', 'phone', 'email', 'id_last4'] | None = None
    requests_protected: bool = False


def _object(props: dict) -> dict:
    """Strict-mode object: every property required, no extras."""
    return {
        'type': 'object',
        'properties': props,
        'required': list(props),
        'additionalProperties': False,
    }


_TEXT = {'type': ['string', 'null']}
EXTRACTION_SCHEMA = _object({
    'identity': _object({
        k: _TEXT for k in ('full_name', 'dob', 'phone', 'email', 'id_last4', 'policy_number')
    }),
    'hints': _object({k: _TEXT for k in ('case_type', 'status', 'month', 'case_id', 'intent')}),
    'emotion': _object({
        'label': {'type': 'string', 'enum': list(EMOTION_LABELS)},
        'intensity': {'type': 'integer', 'enum': [0, 1, 2, 3]},
    }),
    'in_scope': {'type': 'boolean'},
    'wants_human': {'type': 'boolean'},
    'refused_verification': {'type': 'boolean'},
    'wants_to_end': {'type': 'boolean'},
    'consent': {'type': ['string', 'null'], 'enum': ['yes', 'no', None]},
    'asked_about_factor': {
        'type': ['string', 'null'],
        'enum': ['full_name', 'dob', 'phone', 'email', 'id_last4', None],
    },
    'requests_protected': {'type': 'boolean'},
})


def parse_extraction(raw: str | None) -> Extraction:
    """Validate model output. Anything malformed becomes an empty Extraction (SAFE-03)."""
    try:
        return Extraction.model_validate_json(raw or '')
    except ValidationError:
        logger.warning('Extractor returned invalid output')
        return Extraction()
