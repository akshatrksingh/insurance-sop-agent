"""LLM client: an OpenAI-compatible implementation and a scripted fake."""

import json
import logging
from pathlib import Path

import openai
from openai import OpenAI

from insurance_claims.extractor import EXTRACTION_SCHEMA, Extraction, parse_extraction
from insurance_claims.views import SessionView

logger = logging.getLogger(__name__)
PROMPT_DIR = Path(__file__).parent / 'prompts'


class LLMError(Exception):
    """A model call failed. The message is safe to show to the caller."""


class BadRequest(LLMError):
    """The provider rejected the request itself, for example the schema."""


def load_prompt(stem: str) -> str:
    """Return the text of `prompts/<stem>.txt`."""
    path = PROMPT_DIR / f'{stem}.txt'
    try:
        return path.read_text(encoding='utf-8')
    except OSError as exc:
        raise LLMError('A prompt file is missing, so check the app install.') from exc


class OpenAICompatLLM:
    """Synchronous client for any OpenAI-compatible chat endpoint (default Groq)."""

    def __init__(self, api_key: str, base_url: str, model: str, reasoning_effort: str) -> None:
        """Create the client. The key goes only to the SDK and is not stored here."""
        self._client = OpenAI(api_key=api_key, base_url=base_url, timeout=30.0)
        self._model = model
        self._effort = reasoning_effort

    def _complete(self, messages: list[dict], **extra: object) -> str:
        """Run one chat call and return the stripped text, or an empty string.

        Raises:
            LLMError: With a message that is safe to show. Never contains the token.
        """
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                extra_body={'reasoning_effort': self._effort},
                **extra,
            )
        except openai.AuthenticationError as exc:
            raise LLMError('The model service rejected the token, so check the key and try again.') from exc
        except openai.BadRequestError as exc:
            logger.warning('Model rejected the request')
            raise BadRequest('The model call failed, so try again.') from exc
        except openai.RateLimitError as exc:
            raise LLMError('The model service is rate limited, so wait a moment and try again.') from exc
        except openai.APIConnectionError as exc:
            raise LLMError('The model service could not be reached, so check the connection and try again.') from exc
        except openai.OpenAIError as exc:
            logger.warning('Model call failed: %s', type(exc).__name__)
            raise LLMError('The model call failed, so try again.') from exc
        content = response.choices[0].message.content if response.choices else None
        return (content or '').strip()

    def extract(self, text: str, view: SessionView) -> Extraction:
        """Read one caller message into a validated Extraction (strict JSON schema).

        Caller text goes only in the user turn. Malformed output, or a provider that
        rejects the schema, gives an empty Extraction (SAFE-03).

        Args:
            text: The caller's message.
            view: The session view, used only for the phase name.

        Returns:
            The validated Extraction.

        Raises:
            LLMError: On token, rate limit, or connection failures.
        """
        messages = [
            {'role': 'system', 'content': load_prompt('extractor')},
            {'role': 'user', 'content': json.dumps({'phase': view.phase, 'caller_text': text})},
        ]
        schema = {'name': 'extraction', 'strict': True, 'schema': EXTRACTION_SCHEMA}
        try:
            raw = self._complete(messages, response_format={'type': 'json_schema', 'json_schema': schema})
        except BadRequest:
            raw = ''
        return parse_extraction(raw)

    def reply(self, prompt_name: str, bundle: dict) -> str:
        """Generate the agent reply.

        Args:
            prompt_name: Name of the responder prompt, for example `resolve_intent`.
            bundle: Scoped context. Caller text is sent in the user turn only.

        Returns:
            The raw reply text.

        Raises:
            LLMError: With a message that is safe to show. Never contains the token.
        """
        messages = [
            {'role': 'system', 'content': load_prompt(f'responder_{prompt_name}')},
            {'role': 'user', 'content': json.dumps(bundle)},
        ]
        content = self._complete(messages)
        if not content:
            raise LLMError('The model returned an empty reply, so try again.')
        return content


class FakeLLM:
    """Scripted stand-in with the same methods as `OpenAICompatLLM`. Never uses the network."""

    def __init__(
        self,
        replies: dict[str, str] | None = None,
        extractions: dict[str, Extraction | dict] | None = None,
        default: str = 'Hello. This is a scripted reply.',
    ) -> None:
        """Script replies and extractions by caller text. Unscripted text gets the defaults."""
        self.replies = replies or {}
        self.extractions = extractions or {}
        self.default = default
        self.calls: list[tuple[str, dict]] = []

    def extract(self, text: str, view: SessionView) -> Extraction:
        """Return the scripted Extraction for this text, or an empty one.

        Args:
            text: The caller's message.
            view: The session view, unused by the fake.

        Returns:
            The scripted Extraction, or an empty one when none is scripted.
        """
        scripted = self.extractions.get(text)
        if scripted is None:
            return Extraction()
        return Extraction.model_validate(scripted)

    def reply(self, prompt_name: str, bundle: dict) -> str:
        """Return the scripted reply keyed by `bundle['caller_message']`.

        Args:
            prompt_name: Name of the responder prompt, recorded in `calls`.
            bundle: The scoped context, recorded in `calls`.

        Returns:
            The scripted reply, or the default text.
        """
        self.calls.append((prompt_name, bundle))
        return self.replies.get(str(bundle.get('caller_message', '')), self.default)
