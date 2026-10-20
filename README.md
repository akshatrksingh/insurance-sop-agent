# Claims support SOP agent

A Streamlit chat app for insurance claims support. It follows a fixed four-phase procedure (verify ID, resolve intent, process case, wrap up) and converses in natural language. Code controls the phases and gates. A language model phrases the replies.

This is the CP0 skeleton: the chat, the sidebar, the model client, and the reset. Verification and later phases come in later stages.

## Run locally

```
pip install -r requirements.txt
streamlit run app.py
```

Set an API token in one of three places. The first one found is used.

1. Streamlit secrets: create `.streamlit/secrets.toml` with `LLM_API_KEY = "your token"`.
2. Environment variable: `export LLM_API_KEY="your token"`.
3. The sidebar: paste a token under Settings. It stays in your browser session only.

If no token is found, the app shows a message under the header and makes no model call.

The default model service is Groq (`https://api.groq.com/openai/v1`) with the model `openai/gpt-oss-20b`. Optional overrides: `LLM_BASE_URL`, `LLM_MODEL`, `LLM_REASONING_EFFORT`.

## Deploy to Streamlit Community Cloud

1. Push the repo to GitHub.
2. Create the app on Streamlit Community Cloud with `app.py` as the entry file.
3. In the app settings, open Secrets and add `LLM_API_KEY = "your token"`.

Never commit `.streamlit/secrets.toml`.
