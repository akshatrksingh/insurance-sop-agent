# Claims support SOP agent

An insurance claims support chat agent that follows a fixed verification and case workflow.

## Live demo

https://insurance-sop-agent.streamlit.app/

## How to use

Paste your own free Groq API key (from console.groq.com) into the Groq API key field in the sidebar, then chat. The key stays in your browser session only.

## Local setup

Create a virtual environment outside the repo, then run:

```
pip install -r requirements.txt
streamlit run app.py
```

The app looks for the key in this order: Streamlit secrets, then the environment variable `LLM_API_KEY`, then the sidebar field.

Offline tests: `env -u LLM_API_KEY python3 -m pytest tests -q`
