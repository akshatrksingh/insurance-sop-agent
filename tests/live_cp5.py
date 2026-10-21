"""Live CP5 canaries (not collected by pytest). Needs RUN_LIVE=1. Usage: live_cp5.py e f. Stops at the first error, no retries."""
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
os.chdir(ROOT)
OUT = Path('/private/tmp/claude-501/-Users-akshatsingh-Downloads-apps/4a0db171-0ab2-4a56-b186-8f60b204f7ee/scratchpad/live_cp5_transcripts.txt')
import live_smoke as ls  # noqa: E402
from livechecks import leaked, load_fixture, stored_values  # noqa: E402
from insurance_claims.grounding import ungrounded  # noqa: E402

DEMO = ("I'm the policyholder. My name is Margaret Chen, policy POL-9921. I'm calling about my denied healthcare "
        'claim from January. DOB is 1985-03-15, SSN last four is 4472.')
S2 = 'I already told you who I am. This is ridiculous. Just tell me why my claim was denied.'
CONVS = {
    'e': ('e S2 then human', [S2, 'I want to talk to a human']),
    'f': ('f angry after case', [DEMO, 'This is ridiculous, you people are useless']),
}
TIMES = []


def timed(llm):
    """Wrap extract and reply on the instance to record the seconds each real call takes (before spacing is added)."""
    for name in ('extract', 'reply'):
        original = getattr(llm, name)

        def call(*a, _o=original, **k):
            """Time one call."""
            t = time.time()
            try:
                return _o(*a, **k)
            finally:
                TIMES.append(time.time() - t)

        setattr(llm, name, call)


def strikes(s):
    """Off-topic strike count from the view."""
    return next(r['value'] for r in s.view().model_dump()['memory_rows'] if r['label'] == 'Off-topic strikes')


def main():
    """Run the picked conversations once each, stop at the first error."""
    if os.environ.get('RUN_LIVE') != '1':
        sys.stdout.write('refusing to run without RUN_LIVE=1\n')
        sys.exit(2)
    from insurance_claims.orchestrator import handle_turn, new_session
    llm = ls.build_llm()
    timed(llm)
    ls.throttled(llm)
    lines, values = [], stored_values()
    claims = [c for c in load_fixture('claims.json') if c['party_id'] == 'P9']
    data = {'claims': claims, 'guidance': load_fixture('required_document_guideline.json')}
    for key in sys.argv[1:]:
        title, messages = CONVS[key]
        ls.emit(f'=== {title} ===', lines)
        s = new_session()
        for text in messages:
            before, t0, n0 = ls.STATE['calls'], time.time(), len(TIMES)
            try:
                r = handle_turn(s, text, llm)
            except Exception as exc:
                ls.emit(f'STOP {type(exc).__name__}: {str(exc)[:200]}', lines)
                OUT.write_text('\n'.join(lines) + '\n')
                sys.exit(1)
            took = sum(TIMES[n0:])
            ls.emit(f'Caller: {text}', lines)
            for e in r.events:
                if e.level == 'key':
                    ls.emit(f'  [event] {e.text}', lines)
            ls.emit(f'Agent: {r.reply}', lines)
            if r.email_preview:
                ls.emit(f'  [preview] to={r.email_preview.to} subject={r.email_preview.subject}\n{r.email_preview.body}', lines)
            flags = []
            if s.view().phase == 'VERIFY_ID' and leaked(r.reply, values):
                flags.append('LEAK')
            if s.view().phase not in ('VERIFY_ID',) and ungrounded(r.reply, data):
                flags.append('UNGROUNDED')
            calls_made, phase = ls.STATE['calls'] - before, s.view().phase
            ls.emit(f'  [phase={phase} strikes={strikes(s)} llm_calls={calls_made} llm_s={took:.1f} flags={flags}]', lines)
    total, mean, longest = ls.STATE['calls'], sum(TIMES) / max(len(TIMES), 1), max(TIMES or [0])
    ls.emit(f'SUMMARY llm_calls={total} mean_call_s={mean:.1f} max_call_s={longest:.1f}', lines)
    OUT.write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    main()
