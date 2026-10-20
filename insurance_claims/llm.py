"""LLM client: an OpenAI-compatible implementation and a scripted fake."""

import json
import logging
from pathlib import Path

import openai
from openai import OpenAI

from insurance_claims.extractor import Extraction
from insurance_claims.state import SessionView

logger = logging.getLogger(__name__)
PROMPT_DIR = Path(__file__).parent / 'prompts'


class LLMError(Exception):
    """A model call failed. The message is safe to show to the caller."""


def load_prompt(prompt_name: str) -> str:
    """Return the text of `prompts/responder_<prompt_name>.txt`."""
    path = PROMPT_DIR / f'responder_{prompt_name}.txt'
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

    def extract(self, text: str, view: SessionView) -> Extraction:
        """Return an empty Extraction. The extraction call is built in CP1."""
        return Extraction()

    def reply(self, prompt_name: str, bundle: dict) -> str:
        """Generate the agent reply.

        Args:
            prompt_name: Name of the responder prompt, for example `verify_id`.
            bundle: Scoped context. Caller text is sent in the user turn only.

        Returns:
            The raw reply text.

        Raises:
            LLMError: With a message that is safe to show. Never contains the token.
        """
        messages = [
            {'role': 'system', 'content': load_prompt(prompt_name)},
            {'role': 'user', 'content': json.dumps(bundle)},
        ]
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                extra_body={'reasoning_effort': self._effort},
            )
        except openai.AuthenticationError as exc:
            raise LLMError('The model service rejected the token, so check the key and try again.') from exc
        except openai.RateLimitError as exc:
            raise LLMError('The model service is rate limited, so wait a moment and try again.') from exc
        except openai.APIConnectionError as exc:
            raise LLMError('The model service could not be reached, so check the connection and try again.') from exc
        except openai.OpenAIError as exc:
            logger.warning('Model call failed: %s', type(exc).__name__)
            raise LLMError('The model call failed, so try again.') from exc
        content = response.choices[0].message.content if response.choices else None
        if not content or not content.strip():
            raise LLMError('The model returned an empty reply, so try again.')
        return content.strip()


class FakeLLM:
    """Scripted stand-in with the same methods as `OpenAICompatLLM`. Never uses the network."""

    def __init__(
        self,
        replies: dict[str, str] | None = None,
        extractions: dict[str, Extraction] | None = None,
        default: str = 'Hello. This is a scripted reply.',
    ) -> None:
        """Script replies and extractions by caller text. Unscripted text gets the defaults."""
        self.replies = replies or {}
        self.extractions = extractions or {}
        self.default = default
        self.calls: list[tuple[str, dict]] = []

    def extract(self, text: str, view: SessionView) -> Extraction:
        """Return the scripted Extraction for this text, or an empty one."""
        return self.extractions.get(text, Extraction())

    def reply(self, prompt_name: str, bundle: dict) -> str:
        """Return the scripted reply keyed by `bundle['caller_message']`."""
        self.calls.append((prompt_name, bundle))
        return self.replies.get(str(bundle.get('caller_message', '')), self.default)
