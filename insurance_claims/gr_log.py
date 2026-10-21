"""GR-lite flag log (SAFE-08): one redacted stdout line per flagged message.

The stdout handler for this logger is configured here and nowhere else.
"""

import logging
import re
import sys
from datetime import datetime, timezone

LOGGER_NAME = 'insurance_claims.flagged'
MAX_CHARS = 500
_EMAIL = re.compile(r'[\w.+-]+@[\w-]+(?:\.[\w-]+)+')
_PHONE = re.compile(r'\+?\d[\d\s().-]{7,}\d')
_DIGITS = re.compile(r'\d{4,}')


class _StdoutHandler(logging.StreamHandler):
    """Stream handler that looks up `sys.stdout` at emit time."""

    def __init__(self) -> None:
        super().__init__(sys.stdout)

    @property
    def stream(self):  # type: ignore[override]
        """The current `sys.stdout`."""
        return sys.stdout

    @stream.setter
    def stream(self, value) -> None:
        """Ignore assignment, the stream is always `sys.stdout`."""


def _logger() -> logging.Logger:
    """Return the flag logger, with its single stdout handler attached once."""
    log = logging.getLogger(LOGGER_NAME)
    if not any(isinstance(h, _StdoutHandler) for h in log.handlers):
        handler = _StdoutHandler()
        handler.setFormatter(logging.Formatter('%(message)s'))
        log.addHandler(handler)
    log.setLevel(logging.INFO)
    return log


def redact(text: str) -> str:
    """Return the text on one line, with emails, phones and runs of 4 or more digits replaced, cut to 500 characters."""
    flat = ' '.join(text.split())
    flat = _DIGITS.sub('[digits]', _PHONE.sub('[phone]', _EMAIL.sub('[email]', flat)))
    return flat[:MAX_CHARS]


def log_flag(session_id: str, turn: int, phase: str, category: str, message: str) -> None:
    """Write one log line for a flagged message. A logging failure is swallowed, never raised."""
    try:
        stamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        _logger().info(
            'Message flagged: time=%s session=%s turn=%d phase=%s category=%s message=%s',
            stamp, session_id, turn, phase, category, redact(message),
        )
    except Exception:
        return
