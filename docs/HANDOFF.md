# Handoff

Main thread = coordinator. It never implements and never runs git. Subagents (`.claude/agents/`): coder, tester, reviewer. Read order: `ASSIGNMENT.md`, `SYSTEM_DESIGN.md`, `CODING_GUIDELINES.md`, `FRONTEND_GUIDELINES.md`, `DEV_STAGES.md`, `CLAUDE.md` (all in `docs/`), then this file.

## State
- CP0 Skeleton: approved, committed, tag `cp-0`, pushed to https://github.com/akshatrksingh/insurance-sop-agent.
- Human decision (CP2): no per-stage Try scripts; stage report only (facts, canary transcripts, verifiers and tokens, labeled view). One full Try script and the hosted deploy come after the last stage.
- CP1 Verification: approved by the human. Commit commands were printed. Ask the human whether tag `cp-1` was pushed before doing anything else.
- Next: finish CP2 (round 3 tests, canaries, then approval and git commands), then continue under the MVP fast-track rule.
- Stage order (changed by the human, 2026-10-20): CP2, CP4, CP5, CP3, GR-lite, CP6 (`DEV_STAGES.md` section 3 rows are in this order). The guard-model guardrail stage is cut (Tier 1 downgrade by the human, logged in SYSTEM_DESIGN section 8); GR-lite is code-only after CP3 (SAFE-07..09).
- Process: reviewer on CP4 and once on the full tree before deploy; tester full suite once per stage; at most 4 live canaries per stage; fast track: after a stage passes, print git commands, wait for the human to confirm, start the next stage.
  - CP2 hints memory, intent, case resolution, grounded answer, Show details toggle, "Case found" event.
  - CP4 scope guard (3 strikes then human offer), email offer, consent, summary, mock send, SAFE-05.
  - CP5 emotion handling, resistance, handoff rules, VER-07, S2, S4, S8.
  - CP3 guidance matching, fallback, human recommendation, other-party refusal (INT-03, CASE-02, CASE-03, S9).
  - CP6 polish: glass CSS, README, turn cap and throttle, live NFR runs, full demo on the hosted URL.

## Human decisions (SYSTEM_DESIGN section 8 decision log, rows in this order)
Stack and LLM (Groq `openai/gpt-oss-20b`, email mocked); UI palette; Tier 2 waivable, Tier 1 never; CL-2048 appeal deadline rule; palette values changed to meet the 4.5:1 rule (Tier 1); NFR-06 subprocess note (not a waiver); CP0 bad-token Try step skipped by the human; UI-03 covers Session memory only and the Try menu is demo scaffolding labeled "Demo identities"; off-topic rule (code allowlist, whole-message match, strike needs extractor out of scope); VER-06 reading (count and outstanding options allowed, multi-item message states only the total count); NFR-01 regeneration accepted (worst case 3 calls); fixed empathy lines override the "specific empathy" wording for pre-verification templates only. Section 8 Changelog lines list contract deviations from CP1 (views.py, trymenu.py, new extractor fields, no model text before verification, full stored name once at verification).
Other rules set by the human: "No length gate" on the guard; CODING_GUIDELINES first no-go reworded (split by concern, docs and fixtures excluded from the length scan); a fix round counts only when reviewer findings send work to the coder; CP4 and CP6 carry-overs in `DEV_STAGES.md`.

## Open items
- Hosted deploy to Streamlit Community Cloud waits for the final step (human does it: share.streamlit.io, repo above, main file `app.py`, paste `LLM_API_KEY` in the app Secrets box by hand).
- Guard-model guardrail and its design note: cancelled. See GR-lite in DEV_STAGES.
- CP2 carry-overs: post-verification replies must use stored hints and resolve the case, not ask "how can I help"; the resolve prompt must not use "please" or invent content; procedural questions after verification answer only from tool data.
- CP4: rejected-message turns must not feed the email summary; wire `MAX_OFF_TOPIC` (strikes are counted already, nothing acts on them). CP6: key events inline in order, consecutive failed turns show every caller message, Try menu switchable off for a deployed demo.
- Reviewer has not seen the last CP1 change (injection routing in `scope.py`, `templates.py`). Include it in the CP2 review.
- Weak or stock items accepted for now: LANG-02 and NFR-07 coverage is partial for later IDs.

## GR-lite (replaces the guardrail request)
Code-only, no extra model calls: system-probe and harmful pattern list with fixed refusal, no state change and fixed notice; one redacted stdout log line per flagged message; supportive fixed self-harm reply with human offer; F8 fix. IDs SAFE-07..09. About 30 labeled phrases including 15 benign controls, zero false positives on controls. Details in DEV_STAGES and SYSTEM_DESIGN.

## Workflow rules
- No agent runs git, ever. At an approved checkpoint print the commands (`git status`, `git add -A`, `git commit -m "CP-N: title"`, `git tag cp-N`, `git push && git push --tags`) and wait for the human to confirm. Check that `.streamlit/secrets.toml` is not staged.
- Only the human approves, runs Try scripts and git. Never act as the human.
- Order per stage: coder builds, tester writes and runs tests (stage tests and fast scans while iterating, full suite once at the end), reviewer only after the full suite passes, on changed files only, independent of the tester. Never relay one worker's opinion to the other. Tier 1 never waived. Max 2 fix rounds unless the human authorizes more.
- Cost plan (approved): keep standing regression suites; about 8 live canary conversations per round, the full set once per stage; coder never runs the full suite; short reports; reuse agent contexts via SendMessage; give agents requirement IDs and file paths, not pasted files. After each stage tell the human in two lines what was saved and what it cost.
- Never open, print or quote `.streamlit/secrets.toml` or any key. Live runs need `RUN_LIVE=1` plus a configured key, set on one command only, never exported.
- No em or en dashes anywhere. Report results as facts per requirement ID, then the main thread's own view, labeled.

## Where things live
- App `app.py`; package `insurance_claims/` (config, data, llm, state, views, verify, extractor, phases, templates, scope, responder, orchestrator, `ui/`); prompts and templates in `insurance_claims/prompts/` (`extractor.txt`, `responder_resolve_intent.txt`, `verify_templates.json`); fixtures `insurance_claims/fixtures/` (read-only); theme `.streamlit/config.toml`; tests in `tests/` (`test_cp0_*`, `test_cp1_*`, `test_hygiene.py`, `test_lang02.py`, `test_zz_reply_scan.py`; helpers `templatecheck.py`, `replyrecorder.py`); live script `tests/live_smoke.py` (not collected by pytest).

## Run
- Create a venv outside the repo, `pip install -r requirements.txt` (streamlit, pydantic, openai, pytest), then `streamlit run app.py`. Key order: Streamlit secrets, env `LLM_API_KEY`, sidebar field.
- Offline suite: `LLM_API_KEY` unset, `pytest tests -q` (last result: 1138 passed, 1 skipped, about 17 s).
- Live smoke (human-authorized only): `RUN_LIVE=1 python tests/live_smoke.py`, transcripts to the scratchpad; never print the key.

## First message to paste in the new session
Read docs/HANDOFF.md, then the docs in the order CLAUDE.md gives. Confirm coder, tester and reviewer subagents are available. I am the human; I run git and the Try scripts. CP0 and CP1 are approved. Ask me whether tag cp-1 was pushed, then write the guardrail design note (max 25 lines) and wait for my yes before building anything. CP2 starts only after that.
