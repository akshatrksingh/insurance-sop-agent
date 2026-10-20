"""Extractor output schema (SYSTEM_DESIGN 4.2). The extraction call arrives in CP1."""

from typing import Literal

from pydantic import BaseModel, Field


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


class Emotion(BaseModel):
    """Emotion label and intensity from 0 to 3."""

    label: Literal[
        'neutral', 'frustration', 'anxiety', 'anger', 'confusion', 'refusal'
    ] = 'neutral'
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
