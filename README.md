# Claims support SOP agent

A Streamlit chat app for insurance claims support. It follows a fixed procedure in four phases: verify the caller's ID, find out what they need, process the case, and wrap up. The caller talks in plain language. Code controls the phases, the gates, and consent. A language model reads each message and phrases the replies, but it never decides a phase change or a verification result.

Everything runs on synthetic data from `insurance_claims/fixtures/`. The email step is a mock: nothing leaves the process, and the preview card says so.

## Run locally

Create the virtual environment outside the repo folder, then install and run:

```
python3 -m venv ~/venvs/claims
source ~/venvs/claims/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## API key

The app looks for a Groq key in this order and uses the first one it finds.

1. Streamlit secrets: create `.streamlit/secrets.toml` with `LLM_API_KEY = "your key"`.
2. Environment variable: `export LLM_API_KEY="your key"`.
3. The sidebar: paste a key in the masked Groq API key field. It stays in your browser session, is never shown, and is gone after a reload or a Reset.

Setting `LLM_API_KEY` in secrets or the environment still works and suits private use.

With no key the app shows the line "Paste your Groq key in the sidebar to start." and makes no model call. Never commit `.streamlit/secrets.toml`. It is listed in `.gitignore`.

## Bring your own key (public deploy)

The public deploy does not hold a key. Each visitor pastes their own Groq key in the sidebar. A free key is available at console.groq.com. The key lives in your browser session only. It is sent to Groq to answer your messages, and this app never stores or logs it. Reset clears it.

Use a throwaway key made for this demo, and delete it in the Groq console afterward.

## Model service

The default is Groq (`https://api.groq.com/openai/v1`) with the model `openai/gpt-oss-20b`. Groq has a free tier with rate limits, so a long demo can hit a limit. When that happens the app shows a short error and keeps your message in the transcript. Try again after a moment.

## Settings

Each one can be set in Streamlit secrets or as an environment variable. Secrets win. `MAX_TURNS` and `TRY_MENU` are read on every rerun. The other settings are cached or read when the app starts, so restart the app after changing them.

| Name | Default | What it does |
|---|---|---|
| `LLM_BASE_URL` | `https://api.groq.com/openai/v1` | OpenAI compatible endpoint |
| `LLM_MODEL` | `openai/gpt-oss-20b` | Model name |
| `LLM_REASONING_EFFORT` | `low` | Reasoning effort sent to the model |
| `MAX_OFF_TOPIC` | `3` | Off topic messages before the agent offers a human |
| `MAX_VERIFY_FAILS` | `3` | Failed verification rounds before the agent offers a human |
| `MAX_TURNS` | `40` | Caller messages allowed in one chat. A value of 0 or below is ignored and the default applies |
| `TRY_MENU` | `on` | Set to `off` to remove the Try menu from the sidebar |

After `MAX_TURNS` messages the app asks for a Reset or for the visitor's own key in the sidebar field. A visitor key lifts the cap and is used for the calls only while it is in the field. If the field is empty, the cap applies again and the app makes no model call.

The Try menu lists sample messages and is labeled Demo identities. It shows synthetic names and IDs, so turn it off for a public demo with `TRY_MENU = "off"`. When it is off, no demo identity appears in the sidebar.

## Flagged messages

Messages that probe the system prompt or ask for something harmful get a fixed reply, with no model call. Each flagged message writes one line to stdout with the category and the message cut to 500 characters, after emails, phone numbers, and runs of four or more digits are redacted. The line starts with `Message flagged:`. No other caller text is logged.

## Tests

The offline tests use a scripted stand-in for the model and never touch the network:

```
pytest tests -q
```

Tests that call the live model only run when both `LLM_API_KEY` and `RUN_LIVE=1` are set.

## Deploy to Streamlit Community Cloud

1. Push the repo to GitHub. Check that `.streamlit/secrets.toml` is not in the commit.
2. Sign in at share.streamlit.io, choose Create app, and pick the repo and branch.
3. Set the main file path to `app.py`.
4. Under Advanced settings, choose Python 3.12 or newer.
5. Open Secrets and add only `TRY_MENU = "off"` so the public demo hides the Try menu. Leave `LLM_API_KEY` out, because each visitor pastes their own Groq key in the sidebar.
6. Keep the Secrets box empty apart from that one line.
7. Deploy. After any change to Secrets, choose Reboot app so the new values load.
8. Test on the hosted URL: paste a throwaway Groq key in the sidebar, send a first message, finish verification with a synthetic identity from the fixtures, ask about a claim, and check that the sidebar has no Try menu.
