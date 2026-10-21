# Coding Guidelines

Follow these rules strictly. They are non-negotiable. If a rule blocks you, stop and ask. Do not work around it.

Behavior is defined by `SYSTEM_DESIGN.md`. UI rules are in `FRONTEND_GUIDELINES.md`. This file covers how code is written.
Starter data is in `insurance_claims/fixtures/` and is read-only.

## Strict No-Go's

- **NEVER run git add, git commit, git push, git init, or any git command.** This applies to every agent, including the main thread. The human runs all version control. At a checkpoint the agent hands over the exact commands as text (`git add`, `git commit -m '...'`, `git tag cp-N`, `git push`) and never executes them.
- **NEVER over-engineer.** No base classes, factories, plugin systems, abstract layers, or dependency injection. If a pattern does not solve a concrete problem here, skip it.
- **NEVER create unnecessary abstractions.** One implementation means no interface. The one allowed seam is the LLM client, which has two real implementations: `OpenAICompatLLM` and `FakeLLM`.
- **NEVER add dependencies not listed in SYSTEM_DESIGN.md** without logging it in that file's Changelog.
- **NEVER expose the API token.** It lives in config, is passed only to the SDK client, and never appears in logs, the UI, error messages, or `Session`.
- **NEVER log or display PII** (name, DOB, phone, email, SSN last 4, policy number) beyond what the caller typed in the current chat. Log opaque ids (`session_id`, `case_id`).
- **NEVER make raw HTTP calls.** Use the `openai` SDK. No `requests`, no `httpx`.
- **NEVER use `print()`.** Use `logging`.
- **NEVER leave a code file at or past 200 lines unsplit.** A code file that approaches or passes 200 lines must be split into smaller files by concern, for example one module per responsibility, with a thin package `__init__` or entry module that keeps the public names from SYSTEM_DESIGN section 4.5 working. Do not squeeze code to fit: no dense one-liners, no deleting docstrings or type hints. Do not split by arbitrary line ranges. A file that cannot split cleanly and goes over must be reported to the human with the reason, never left silently. This limit applies to code and test files (`app.py`, `insurance_claims/`, `tests/`). It does not apply to the contract and guideline `.md` files (including `SYSTEM_DESIGN.md`), `ASSIGNMENT.md`, or fixtures, and the NFR-05 length scan excludes them.
- **NEVER let the LLM decide a phase transition, a verification result, a gate, or consent.** Code decides, from validated structured data.
- **NEVER pass claim data to any LLM call before the session is verified.** Bundles are built per SYSTEM_DESIGN 4.3, by construction, not by prompt wording.
- **NEVER put caller text in a system prompt or a tool argument.** It goes only in the user turn, and prompts tell the model it is untrusted data.
- **NEVER auto-retry a failed email send.** Report it and let the caller decide.
- **NEVER edit fixture files** to make a test pass.
- **NEVER write session data to disk.**
- **NEVER use an em dash or en dash** in code, strings, prompts, comments, or docs.
- **NEVER put business logic in `app.py` or `ui/`.** They render `Session.view()` and call `handle_turn`.

## Code Style

- Python 3.12 features are allowed
- Synchronous code. Streamlit reruns the script on each interaction, so no `async`.
- Type hints on all function signatures
- Docstrings on all public functions (Google style)
- f-strings, never `.format()` or `%`
- Single quotes unless the string contains a single quote
- No unused imports, no commented-out code
- Pydantic models for anything crossing a boundary (extractor output, `Session`, `SessionView`, `TurnResult`). Plain functions elsewhere.
- Document every `st.session_state` key in one place: the module docstring of `app.py`

## Design Principles

1. **The LLM proposes, the code disposes.** Extract (LLM), update state (code), gate (code), respond (LLM). LLM output is data that code validates.
2. **Scoped context, not instructions.** Build each LLM call's context from only what the current phase may expose. Data not in the bundle cannot leak.
3. **Errors are context.** Failures are structured results, not exceptions shown to the caller:
   ```python
   return {
       'error': 'NO_MATCHING_CLAIM',
       'message': 'No claim matched the remembered hints.',
       'recoverable': True,
       'suggestion': 'Ask the caller to describe the claim or give a case id.',
   }
   ```
   Every error has `error`, `message`, `recoverable`, `suggestion`.
4. **Curate ruthlessly.** Pass only the fields a call needs. Never dump a whole claim record or a whole guideline file into a prompt.
5. **Fail safe on bad LLM output.** Malformed or invalid extractor output becomes an empty extraction. It never crashes a session, advances a phase, sets a gate, or counts as a factor.

## Input Validation

- Normalize phones (digits only, last 10), emails (lowercase, trimmed), dates (ISO), ID last 4 (exactly 4 digits).
- Reject empty or oversized messages (over 2000 characters) before any logic runs.
- Enforce the session turn cap and throttle (NFR-08) before calling the LLM.

## State Guards

Safety checks live in the harness, not in prompts:

```python
if not session.gates.verified:
    return {'error': 'NOT_VERIFIED', 'message': 'Identity not verified.', 'recoverable': True, 'suggestion': 'Continue verification.'}
if session.email_consent is not True:
    return {'error': 'NO_CONSENT', 'message': 'Caller has not agreed to the email.', 'recoverable': True, 'suggestion': 'Ask for a clear yes or skip.'}
```

## Fake LLM Pattern

`FakeLLM` has the same methods and return types as `OpenAICompatLLM`:

```python
class FakeLLM:
    def extract(self, text: str, view: SessionView) -> Extraction:
        """Return a scripted Extraction keyed by text."""
```

Application code does not know which one it holds. Deterministic tests use the fake and never touch the network. Live tests are marked and run only when a key is present.

## File Organization

- One module per concern, as in SYSTEM_DESIGN section 2. No `utils.py`.
- Tools are plain functions, one file each or grouped in `tools.py` if small.
- Prompts live in `insurance_claims/prompts/` as text files, not inline strings.
- Dependencies point one way: `ui` and `app.py` -> `orchestrator` -> `phases` -> `tools` and `state`.
- `__init__.py` files are empty or contain only `__all__`.

## Testing

- Every testable requirement ID has at least one test with the ID in its name or docstring.
- Tests call only the public names in SYSTEM_DESIGN 4.5.
- Never weaken, skip, or delete a failing test to get green. Report it.
- Scan tests: dashes (LANG-01), banned phrases (LANG-02), file length and dependencies (NFR-05), palette contrast (FRONTEND_GUIDELINES section 3).

## Logging

```python
import logging
logger = logging.getLogger(__name__)

logger.info('Phase change: %s -> %s (session=%s)', old, new, session_id)
logger.warning('Extractor returned invalid JSON (session=%s)', session_id)
logger.debug('Bundle keys: %s', list(bundle))  # keys only, never values
```

Never log tokens, credentials, PII, or caller text. One exception (SAFE-08): a message flagged by GR-lite is written as one stdout log line with its category, after redacting emails, phones and runs of 4 or more digits and cutting to 500 characters. A logging failure never breaks a turn.

## Changelog

Log new dependencies and any deviation from SYSTEM_DESIGN.md in that file's Changelog, with a one-line reason.
