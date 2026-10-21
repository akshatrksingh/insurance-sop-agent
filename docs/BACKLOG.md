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
