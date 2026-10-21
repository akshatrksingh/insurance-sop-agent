"""Last live conversations a to d (not collected by pytest). RUN_LIVE=1 only. Usage: live_last.py [a b ...] or --list.
Same gating, output scrubbing and per turn printing as live_final.py. Stops at the first error, no retries."""
import logging
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
os.chdir(ROOT)
OUT = Path('/private/tmp/claude-501/-Users-akshatsingh-Downloads-apps/7838112b-b5c4-44e0-aaa1-c049c716ab9c/scratchpad/live_last_transcripts.txt')
import live_final as lf  # noqa: E402
import live_final_checks as common  # noqa: E402
import live_last_checks as chk  # noqa: E402
import live_smoke as ls  # noqa: E402
from live_last_data import CONVS  # noqa: E402


def strike_count(session):
    """Off-topic strikes shown in the memory rows."""
    rows = {r['label']: r['value'] for r in session.view().model_dump()['memory_rows']}
    return int(rows.get('Off-topic strikes', 0))


def run_conv(key, llm, cap, lines):
    """Run one conversation and return its RESULT line. Raises SystemExit(1) at the first turn error."""
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
        rec = lf.turn_record(session, result, text, ls.STATE['calls'] - before, time.time() - t0)
        rec['strikes'] = strike_count(session)
        recs.append(rec)
        ls.emit(f'Caller: {text}', lines)
        while cap.lines:
            ls.emit(f'  [flag log] {cap.lines.pop(0)}', lines)
        ls.emit('Agent: ' + rec['reply'], lines)
        kinds, phase, n, secs, st, pv = rec['kinds'], rec['phase'], rec['calls'], rec['secs'], rec['strikes'], rec['preview_present']
        ls.emit(f'  [event kinds={kinds} phase={phase} llm_calls={n} strikes={st} preview_present={pv} s={secs:.1f}]', lines)
    failures = common.common(recs) + getattr(chk, check)(recs)
    verdict = 'PASS' if not failures else 'FAIL'
    calls = sum(r['calls'] for r in recs)
    return f'RESULT {key} {verdict} turns={len(recs)} llm_calls={calls} failures={failures}'


def main():
    """List, or run the picked conversations (all when none is named) once each."""
    args = sys.argv[1:]
    if args == ['--list']:
        for title, messages, _ in CONVS.values():
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
    lines, cap = [], lf.Capture()
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
