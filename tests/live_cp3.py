"""Live CP3 canaries (not collected by pytest). Needs RUN_LIVE=1. Usage: live_cp3.py a b. Stops at the first error, no retries."""
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
os.chdir(ROOT)
OUT = Path('/private/tmp/claude-501/-Users-akshatsingh-Downloads-apps/7838112b-b5c4-44e0-aaa1-c049c716ab9c/scratchpad/live_cp3_transcripts.txt')
import live_smoke as ls  # noqa: E402

DEMO = ("I'm the policyholder. My name is Margaret Chen, policy POL-9921. I'm calling about my denied healthcare "
        'claim from January. DOB is 1985-03-15, SSN last four is 4472.')
CONVS = {
    'a': ('a timing and format follow-ups', [DEMO, 'how long after I submit?', 'what file format?']),
    'b': ('b cannot get the report then yes', [DEMO, "I can't get the pathology report", 'yes']),
}


def main():
    """Run the picked conversations once each, stop at the first error."""
    if os.environ.get('RUN_LIVE') != '1':
        sys.stdout.write('refusing to run without RUN_LIVE=1\n')
        sys.exit(2)
    from insurance_claims.orchestrator import handle_turn, new_session
    llm = ls.build_llm()
    ls.throttled(llm)
    lines = []
    for key in sys.argv[1:]:
        title, messages = CONVS[key]
        ls.emit(f'=== {title} ===', lines)
        s = new_session()
        for text in messages:
            before, t0 = ls.STATE['calls'], time.time()
            try:
                r = handle_turn(s, text, llm)
            except Exception as exc:
                ls.emit(f'STOP {type(exc).__name__}: {str(exc)[:200]}', lines)
                OUT.write_text('\n'.join(lines) + '\n')
                sys.exit(1)
            ls.emit(f'Caller: {text}', lines)
            ls.emit(f'Agent: {r.reply}', lines)
            kinds = [e.kind for e in r.events]
            phase = s.view().phase
            n_calls = ls.STATE['calls'] - before
            handoff = 'handoff' in kinds or phase == 'ESCALATED'
            ls.emit(f'  [event kinds={kinds} phase={phase} handoff={handoff} '
                    f'llm_calls={n_calls} s={time.time() - t0:.1f}]', lines)
    total = ls.STATE['calls']
    ls.emit(f'SUMMARY llm_calls={total}', lines)
    OUT.write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    main()
