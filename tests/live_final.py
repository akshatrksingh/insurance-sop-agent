"""Final live conversations a to i (not collected by pytest). RUN_LIVE=1 only. Usage: live_final.py [a b ...] or --list.
Prints per turn the caller line, agent reply, event kinds, phase, llm_calls and seconds, then one PASS or FAIL line per conversation.
Stops at the first error, no retries. Output goes through live_smoke.emit, which scrubs key shapes."""
import logging
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
os.chdir(ROOT)
OUT = Path('/private/tmp/claude-501/-Users-akshatsingh-Downloads-apps/7838112b-b5c4-44e0-aaa1-c049c716ab9c/scratchpad/live_final_transcripts.txt')
import live_final_checks as chk  # noqa: E402
import live_smoke as ls  # noqa: E402
from live_final_data import CONVS  # noqa: E402


class Capture(logging.Handler):
    """Collects formatted records of the flagged logger."""

    def __init__(self):
        super().__init__(logging.DEBUG)
        self.lines = []

    def emit(self, record):
        """Keep the formatted message."""
        self.lines.append(record.getMessage())


def turn_record(session, result, text, calls, secs):
    """One record of facts about a finished turn, for printing and for the code checks."""
    v = session.view()
    rows = {r['label']: r['value'] for r in v.model_dump()['memory_rows']}
    matched = sum(1 for r in v.model_dump()['memory_rows'] if r['value'] == 'matched')
    preview = result.email_preview or v.email_preview
    return {'text': text, 'reply': result.reply, 'kinds': [e.kind for e in result.events], 'event_texts': [e.text for e in result.events],
            'phase': v.phase, 'verified': matched >= 3, 'matched': matched, 'resolved': rows.get('Resolved case'),
            'offer_open': bool(v.email_offer_open), 'preview_present': preview is not None, 'preview_to_on_file': chk.on_file(preview),
            'calls': calls, 'secs': secs}


def run_conv(key, llm, cap, lines):
    """Run one conversation. Returns the summary line. Raises SystemExit(1) at the first turn error."""
    from insurance_claims.orchestrator import handle_turn, new_session
    title, messages, check = CONVS[key]
    ls.emit(f'=== {title} ===', lines)
    session, recs = new_session(), []
    for text in messages:
        before, t0 = ls.STATE['calls'], time.time()
        try:
            result = handle_turn(session, text, llm)
        except Exception as exc:
            ls.emit(f'STOP {type(exc).__name__}: {str(exc)[:200]}', lines)
            OUT.write_text('\n'.join(lines) + '\n')
            sys.exit(1)
        rec = turn_record(session, result, text, ls.STATE['calls'] - before, time.time() - t0)
        recs.append(rec)
        ls.emit(f'Caller: {text}', lines)
        while cap.lines:
            ls.emit(f'  [flag log] {cap.lines.pop(0)}', lines)
        ls.emit('Agent: ' + rec['reply'], lines)
        kinds, phase, n, secs = rec['kinds'], rec['phase'], rec['calls'], rec['secs']
        ls.emit(f'  [event kinds={kinds} phase={phase} llm_calls={n} model_built={n >= 2} s={secs:.1f}]', lines)
    failures = chk.common(recs) + getattr(chk, check)(recs)
    extra, last = '', recs[-1]
    if key == 'e':
        extra = ' acknowledges_frustration=' + str(chk.acknowledged(last['reply'])) + ' first_sentence=' + chk.first_sentence(last['reply']) + ' CHECK BY HUMAN'
    if key in 'jk':
        extra = ' acknowledged_frustration=' + str(chk.acknowledged(last['reply'])) + ' model_path_used=' + str(last['calls'] == 2) + ' last_turn_llm_calls=' + str(last['calls']) + ' first_sentence=' + chk.first_sentence(last['reply']) + ' CHECK BY HUMAN'
    if key == 'd':
        extra = ' sent_to_email_on_file_only=' + str(last['preview_to_on_file'])
    verdict = 'PASS' if not failures else 'FAIL'
    calls = sum(r['calls'] for r in recs)
    return f'RESULT {key} {verdict} turns={len(recs)} llm_calls={calls}{extra} failures={failures}'


def main():
    """List, or run the picked conversations (all when none is named) once each."""
    args = sys.argv[1:]
    if args == ['--list']:
        for k, (title, messages, _) in CONVS.items():
            sys.stdout.write(f'{title} ({len(messages)} turns)\n')
        return
    if os.environ.get('RUN_LIVE') != '1':
        sys.stdout.write('refusing to run without RUN_LIVE=1\n')
        sys.exit(2)
    keys = args or list(CONVS)
    if [k for k in keys if k not in CONVS]:
        sys.stdout.write('unknown conversation letter\n')
        sys.exit(2)
    llm = ls.build_llm()
    ls.throttled(llm)
    lines, cap = [], Capture()
    flagged = logging.getLogger('insurance_claims.flagged')
    flagged.addHandler(cap)
    flagged.setLevel(logging.DEBUG)
    results = [run_conv(k, llm, cap, lines) for k in keys]
    for line in results:
        ls.emit(line, lines)
    passed, total = sum(' PASS ' in r for r in results), ls.STATE['calls']
    ls.emit(f'SUMMARY conversations={len(results)} passed={passed} llm_calls={total}', lines)
    OUT.write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    main()
