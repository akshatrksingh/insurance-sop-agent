# Frontend Guidelines

The UI is a thin layer over the harness. It renders `Session.view()` and calls `handle_turn`. It holds no business logic. Contract IDs are in `SYSTEM_DESIGN.md` (UI-01 to UI-09, LANG-01, LANG-02).

## 1. Stack and rules

- Streamlit only. No custom JavaScript, no extra UI libraries.
- Styling goes through `.streamlit/config.toml` (theme) and one function, `inject_css()` in `insurance_claims/ui/theme.py`. All selectors live there. If a selector breaks after a Streamlit upgrade, the UI must still work unstyled.
- Use the native sidebar (it collapses with its built-in control). Use `st.chat_input` for input, `st.spinner` for waiting.
- UI files stay at most 200 lines each: `app.py`, `ui/theme.py`, `ui/transcript.py`, `ui/sidebar.py`.
- The UI only reads `Session.view()`. It never touches stored policyholder values, claim records, or the email address.

## 2. Direction

Apple-like restraint with glass kept to three surfaces. A calm transcript, a collapsible sidebar that shows what the agent remembers and where it is in the SOP. Dense where it helps (sidebar rows), quiet everywhere else.

```
+----------------------------------------------------+-----------------------+
| Claims support    Phase: Verification    [Reset]   | Session memory        |
|----------------------------------------------------| Name          matched |
| Agent   Thanks. I have your name and date of       | DOB           matched |
|         birth. One more item: phone, email, or     | Phone         pending |
|         SSN last four.                             | status        denied  |
| ---------------------------------------------------| month         January |
| Caller  650 521 2836                               |                       |
| ---------------------------------------------------| SOP progress          |
| | Verification complete, 3 of 3                    |  Verify ID    done    |
| ---------------------------------------------------|  Resolve      current |
| Agent   You're verified. I found a denied claim... |  Process      pending |
|                                                    |  Wrap up      pending |
| [ Type a message                             ]     | [x] Show details      |
+----------------------------------------------------+-----------------------+
```

## 3. Tokens (palette: Fog)

Defined once in `insurance_claims/ui/theme.py` as `TOKENS` and `GLASS_ALPHA = 0.70`. Everything else references them.

| Token | Value | Use |
|---|---|---|
| `backdrop` | `#E8EAEF` | page background |
| `glow_warm` | `#FFD9BF` | soft color field, top left |
| `glow_cool` | `#C9D7F2` | soft color field, bottom right |
| `glass` | `#FFFFFF` at `GLASS_ALPHA` | header, sidebar, input |
| `ink` | `#1D1D1F` | primary text |
| `ink_secondary` | `#68686D` | labels, timestamps |
| `action` | `#0066CC` | buttons, links, focus |
| `verified` | `#1B7437` | matched, done |
| `caution` | `#A64B00` | pending, needs attention |
| `hairline` | `#1D1D1F` at 14% | rules and borders |

Contrast rule: every text and background pair below is at least 4.5:1, measured by a test (effective glass is `glass` at 70% over `backdrop`). Pairs: `ink`, `ink_secondary`, `verified`, `caution` on effective glass and on `backdrop`; white on `action`.

Streamlit theme in `.streamlit/config.toml`:

```toml
[theme]
base = "light"
primaryColor = "#0066CC"
backgroundColor = "#E8EAEF"
secondaryBackgroundColor = "#F6F7F9"
textColor = "#1D1D1F"
font = "sans serif"
```

## 4. Type, shape, motion

- Font stack: `-apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI Variable", "Segoe UI", system-ui, sans-serif`. No webfont download (SF cannot be redistributed).
- Sizes: body 15px, labels and events 13px, header 18px. Weights 400 and 600. Sentence case. Tabular numbers for counts and ids.
- Shape: 12px radius on glass surfaces, 6px on controls and chips, 1px hairlines. No shadows.
- Gradients: only the backdrop color field (two soft radial shapes). None on text, buttons, rows, or cards.
- Motion: none, except Streamlit's spinner while a reply is generating.

## 5. Glass rules

1. Glass on three surfaces only: header, sidebar, input. Messages and event rows are solid. No glass on glass.
2. The backdrop is the fixed color field above. No photos, no patterns.
3. Text on glass is dark ink at the contrast above.
4. If `backdrop-filter` is unsupported, or the user prefers reduced transparency, the surfaces fall back to opaque `#F6F7F9`.
5. Blur about 20px, 1px light edge, no glow.
6. Glass is Tier 2 (UI-09). It ships in CP6 and is the first thing cut if it fights Streamlit.

## 6. Components

- **Transcript row**: speaker label in a 72px left column (Agent, Caller), message text beside it, a hairline between turns. No bubbles.
- **Key event row** (always shown): full-width row, 3px left tick, 13px text. Kinds: phase done ("Verification complete, 3 of 3"), case found, email sent, email skipped, handoff. Tick is `verified` for completion, `action` for information, `caution` for handoff.
- **Detail event row** (only with Show details): same row, muted text. Kinds: memory stored, tool called, emotion, strike.
- **Session memory (sidebar)**: label and value rows. Factors show names only with matched or pending. Then hints, intent, resolved case id (after verification), consent, strikes, resistance. A one-line note at the top: "Remembered from this chat. Cleared on reset."
- **SOP progress (sidebar)**: four phases. Each shows status as text plus an icon: done (check, `verified`), current (filled dot, `action`, 600 weight), pending (hollow circle, `ink_secondary`). Under the current and done phases, list the gates as ticked or unticked lines.
- **Header**: product name, current phase name, Reset button. Neutral name "Claims support".
- **Email offer**: two buttons (Send summary, Skip), secondary style. After sending, a preview card: solid, 1px hairline border, 6px radius, subject in 600 weight.
- **Try menu**: a select box in the sidebar listing scripted messages for the current stage. Choosing one pastes it into the input.
- **Token field**: password input in the sidebar under Settings, optional.
- Icons: Streamlit Material icon syntax or plain words. No emoji. Status is never color alone.

## 7. Accessibility baseline

Contrast as above, visible keyboard focus (use native widgets), status as text plus icon, new messages appended in order so screen readers read them in sequence, labels on every control.

## 8. Language rules

Applies to every string a person reads: UI, agent replies, errors, README, docs.

- No em dashes or en dashes. Use a period, comma, colon, or parentheses. Replies are also filtered in code (LANG-01).
- Sentence case. Verb-first buttons ("Send summary", not "Submit"). Contractions are fine. Plain words.
- The same action keeps the same name everywhere: a button that says "Skip" produces an event that says "Skipped".
- No "please", "successfully", "simply", "just", exclamation marks, or emoji in system copy.
- Errors say what happened and what to do, in one sentence, with no apology. Empty states invite the next action.
- Agent replies: short and concrete, one question at a time, no filler openers ("Great question", "Certainly"), no closing recap. Empathy is specific to what the caller said, not a stock line like "I understand your frustration".
- Never invent numbers, dates, or claim facts. Everything comes from tool data.
- Banned patterns: "not X but Y" constructions, trailing "-ing" clauses ("ensuring", "highlighting"), "it's important to note", "moreover", "furthermore", inflated words (seamless, robust, pivotal, leverage, delve, tapestry), bulleted lines that start with a bolded label, arrow glyphs on buttons or links.

## 9. Reviewer checklist (design tells)

Fail the checkpoint item if any is present:

- gradient anywhere except the backdrop field, or gradient text
- accenting one word in a heading by color, italic, or bold
- all-caps labels or tracked-out eyebrow labels
- meta strings joined with middle dots
- numbered markers on content that is not a sequence
- identical rounded card grids, or one radius and one shadow on everything
- glass on more than the three allowed surfaces
- motion that is not a response to an action
- placeholder or filler copy, invented metrics
- any em dash or en dash
