"""Settings: Streamlit secrets first, then environment variables, then defaults."""

import os
from functools import lru_cache

import streamlit as st
from pydantic import BaseModel, SecretStr

DEFAULT_BASE_URL = 'https://api.groq.com/openai/v1'
DEFAULT_MODEL = 'openai/gpt-oss-20b'


class Settings(BaseModel):
    """Runtime settings. The API key is held as a secret and never printed."""

    api_key: SecretStr | None = None
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    reasoning_effort: str = 'low'
    max_off_topic: int = 3
    max_verify_fails: int = 3
    max_turns: int = 40


def _lookup(name: str) -> str | None:
    """Return a setting from Streamlit secrets, then the environment, else None."""
    try:
        value = st.secrets.get(name)
    except Exception:
        value = None
    if value is None:
        value = os.environ.get(name)
    text = str(value).strip() if value is not None else ''
    return text or None


def load_settings(sidebar_token: str = '') -> Settings:
    """Build settings. The API key order is secrets, env var, then the sidebar field.

    Args:
        sidebar_token: Token typed by the visitor in the sidebar, may be empty.

    Returns:
        The resolved settings. `api_key` is None when no key is available.
    """
    key = _lookup('LLM_API_KEY') or sidebar_token.strip() or None
    values: dict[str, object] = {'api_key': SecretStr(key) if key else None}
    for field, name in (
        ('base_url', 'LLM_BASE_URL'),
        ('model', 'LLM_MODEL'),
        ('reasoning_effort', 'LLM_REASONING_EFFORT'),
    ):
        found = _lookup(name)
        if found:
            values[field] = found
    for field, name in (
        ('max_off_topic', 'MAX_OFF_TOPIC'),
        ('max_verify_fails', 'MAX_VERIFY_FAILS'),
        ('max_turns', 'MAX_TURNS'),
    ):
        found = _lookup(name)
        if found and found.isdigit():
            values[field] = int(found)
    return Settings(**values)


@lru_cache(maxsize=1)
def off_topic_limit() -> int:
    """Return MAX_OFF_TOPIC (default 3), resolved once per process."""
    return load_settings().max_off_topic


@lru_cache(maxsize=1)
def verify_fail_limit() -> int:
    """Return MAX_VERIFY_FAILS (default 3), resolved once per process."""
    return load_settings().max_verify_fails
