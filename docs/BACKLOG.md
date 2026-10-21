# Backlog

Deferred until all MVP stages are done. Format: stage, id, description, source.

- CP2, R1: reword the SYSTEM_DESIGN section 3.3 NFR-01 table row (says 2 calls) to match the accepted deviation (worst case 3 calls after verification). CP2 reviewer finding 1.
- CP2, R3: `ACTION_CLAIMS` pattern 4 falsely rejects the honest offer "a human representative who can review it" (costs a regeneration). CP2 reviewer finding 3.
- CP2, R5: "how can I help" or "what would you like" after resolve is only forbidden in code-built text, not in model replies; no check that the name appears once on a model-built verification turn. CP2 reviewer finding 5.
- CP2, T3-6: `grounding._phrase_in` uses `rstrip('s')` substring matching, so "form" or "note" can count as grounded inside other words. CP2 reviewer Tier 3.
- CP2, T3-7: numbers in a reply are allowed if they appear anywhere in the bundle (date fragments, list lengths), possibly in the wrong context. CP2 reviewer Tier 3.
- CP2, T3-8: `grounded.py` module docstring is out of date (code-built replies are now primary, not only a fallback). CP2 reviewer Tier 3.
- CP2, T3-9: `orchestrator.py` import order is ungrouped and `EmailPreview` is unused until CP4. CP2 reviewer Tier 3.
- CP2, T3-10: test hygiene in `tests/test_cp2_firstreply.py` and `test_cp2_fields.py` (import inside a function, `BUNDLE` imported from another test module, weak `>= 2` openers assertion, a phrasing-seed-dependent assertion at test_cp2_fields.py:111, requirement IDs INT-02 and SAFE-01/02/03/06 not named in tests). CP2 reviewer Tier 3.
- CP6, F10: the RESOLVE_INTENT bundle `summary` for CL-2048 states the denial cause. Accepted, allowed by section 4.3. Earlier deferred item.
- Later IDs, NFR-07: LANG-02 and NFR-07 coverage is partial, some assertions are weak or stock. Earlier deferred item.
- CP2, UI: the Status memory row shows the raw stored hint ("rejected", not "denied"). Accepted by the human, no action.
- Filler purpose phrases ("to support your claim") cannot be rejected in code on the model path (multi-field and open-ended follow-ups). Accepted, tester finding in CP2 round 4.
- CP2, GLASS_ALPHA: constant stays in the section 4.5 public names although glass CSS is cut. Accepted, no action.
- CP4, B1: key event "Email not sent" uses done (success) styling; BAD_ADDRESS is non-recoverable but the reply says "Say yes to try again". CP4 coder and reviewer T3-6.
- CP4, B2: "Send summary" produces the event "Email sent" while "Skip" produces "Skipped email summary"; FRONTEND_GUIDELINES section 6 wants one name per action. Reviewer T3-5.
- CP4, B3: SEND_FAILED reply is two sentences (guideline says one). Reviewer T3-6.
- CP4, B4: `.format()` in grounded.py (lines about 74 to 151) and double-quoted strings in claims.py against the code style rules. Reviewer T3-3, T3-4.
- CP4, B5: the Send summary button sends while a human-representative question is outstanding. Accepted by main thread as explicit consent (button label names the action); revisit if the human disagrees. Tester issue 1.
- CP4, B6: MAX_OFF_TOPIC is cached at first read; an env change mid-process is not picked up. Tester issue 3.
- CP4, B7: "no thanks" mid-case (no offer open) moves the session to POST_PROCESS and opens the email offer. Tester fact.
- CP4, B8: a cold `wants_human` before any human offer gets the greeting template. Belongs to CP5 (handoff rules).
- CP4, B9: tests/test_cp4_carryover.py imports BUNDLE from another test module (same hygiene as the CP2 T3-10 item). Reviewer T3-7.
- CP5, B10: the `human_answer == 'no'` and decline branches in flow.py skip `safe_reply` in VERIFY_ID (fixed templates, no leak found). Reviewer Tier 2.
- CP5, B11: after a no to the human offer, `off_topic_strikes` stays at the limit, so the next out-of-scope turn re-offers a human at once. Reviewer Tier 2.
- CP5, B12: `scope.py` is at 182 lines, close to the 200 limit; split before CP3 or GR-lite adds to it.
- CP5, B13: the emotion-only rule relies on a request-word list; an emotional message with an off-topic request that has no question word earns no strike. Accepted, low risk.
- CP5, B14: before CP3 starts, split `scope.py` (182 of 200 lines) by concern, no behavior change. Carried to the next session as the first task.
- CP4, B15: show the email skip path live ("no thanks") in the final tester pass; offline only so far.
- CP3, B16: a bare "how long does it take?" (no document word) under a denial_question session takes the model path, not the processing-time topic. CP3 coder observation.
- CP3, B17: guided replies are fixture text and skip the LANG-01 and LANG-02 filter; fixture line has a trailing "-ing" clause. Reviewer T3-5.
- CP3, B18: no test names CASE-02 or CASE-03 in the docstring of the guidance tests beyond tests/test_cp3_*.py; check NFR-07 in the final pass. Reviewer T3-8.
- CP3, B19: DOC_WORDS in guidance.py is broad (send, mail, confirm, files), widening topic matches; the processing-time template says "reconsidering the denial" without checking status is denied. Reviewer T3-3, T3-4.
- CP3, B20: a topic phrase plus a field word ("how do I submit the documents?") still matches its topic; "can you file it" gets the weak fallback. Coder observations.
