"""Live smoke run (not collected by pytest). Needs RUN_LIVE=1. Replays scripted conversations against the real model."""
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
os.chdir(ROOT)

OUT = Path('/private/tmp/claude-501/-Users-akshatsingh-Downloads-apps/4ca5606b-2da2-48e5-9bc9-b5cf821b6588/scratchpad/live_transcripts.txt')
from livechecks import is_off_topic, judge, stored_values  # noqa: E402
from liveconvs import conversations  # noqa: E402
KEY_SHAPE = re.compile(r'gsk_[A-Za-z0-9_\-]*')
GAP, RETRIES, WAIT = 4.0, 2, 20
STATE = {'last': 0.0, 'calls': 0, 'retries': 0, 'cut': False}


def emit(text, lines):
    """The only output path: scrub key shapes, print and keep the line for the transcript file."""
    clean = KEY_SHAPE.sub('[scrubbed]', str(text))
    lines.append(clean)
    sys.stdout.write(clean + '\n')


def build_llm():
    """Build the real client from load_settings(). Never reads the secrets file directly."""
    from insurance_claims.config import load_settings
    from insurance_claims.llm import OpenAICompatLLM
    s = load_settings()
    key = s.api_key.get_secret_value() if hasattr(s.api_key, 'get_secret_value') else s.api_key
    if not key:
        sys.stdout.write('no key found\n')
        sys.exit(1)
    return OpenAICompatLLM(key, s.base_url, s.model, s.reasoning_effort)


def throttled(llm):
    """Wrap extract and reply on the instance: 4 s spacing, call counting, emotion intensity capture."""
    from replyrecorder import _emotion
    box = {'intensity': 0, 'label': 'neutral', 'in_scope': None}
    for name in ('extract', 'reply'):
        original = getattr(llm, name)

        def call(*a, _o=original, _n=name, **k):
            """Space the call, count it, and note intensity for extract results."""
            wait = GAP - (time.time() - STATE['last'])
            if wait > 0:
                time.sleep(wait)
            try:
                out = _o(*a, **k)
            finally:
                STATE['last'] = time.time()
                STATE['calls'] += 1
            if _n == 'extract':
                box['label'], box['intensity'] = _emotion(out)
                box['in_scope'] = out['in_scope'] if isinstance(out, dict) else getattr(out, 'in_scope', None)
            return out

        setattr(llm, name, call)
    return box


def is_rate_limit(exc):
    """True for rate limit failures (by type name or message)."""
    text = (type(exc).__name__ + ' ' + str(exc)).lower()
    return 'ratelimit' in text or 'rate limit' in text or '429' in text


def run_turn(session, text, llm, lines):
    """Run one turn with at most RETRIES retries on rate limits. Returns the result or None when cut or failed."""
    from insurance_claims.orchestrator import handle_turn
    for attempt in range(RETRIES + 1):
        try:
            return handle_turn(session, text, llm)
        except Exception as exc:
            if not is_rate_limit(exc):
                emit(f'ERROR {type(exc).__name__} on this turn (not a rate limit)', lines)
                return None
            if attempt == RETRIES:
                STATE['cut'] = True
                emit('RATE LIMIT: retries exhausted, cutting the remaining conversations', lines)
                return None
            STATE['retries'] += 1
            emit(f'RATE LIMIT: waiting {WAIT} s before retry {attempt + 1}', lines)
            time.sleep(WAIT)
    return None


def main():
    """Run all conversations, write the transcript file and print the totals."""
    if os.environ.get('RUN_LIVE') != '1':
        sys.stdout.write('refusing to run without RUN_LIVE=1\n')
        sys.exit(2)
    from insurance_claims.orchestrator import new_session
    from test_zz_reply_scan import hits_for
    llm = build_llm()
    box = throttled(llm)
    values, lines, totals = stored_values(), [], {'turns': 0, 'hits': 0, 'convs': 0, 'cut': [], 'fails': [], 'member': 0, 'member_bad': 0, 'dist': {}, 'off': []}
    for title, messages, expected, kind in conversations():
        if STATE['cut']:
            totals['cut'].append(title)
            continue
        emit(f'=== {title} ===', lines)
        s, ok = new_session(), True
        for i, text in enumerate(messages):
            before, prior = STATE['calls'], sum(1 for r, _ in s.view().turns if r == 'Agent')
            was_verified = s.view().phase != 'VERIFY_ID'
            result = run_turn(s, text, llm, lines)
            if result is None:
                ok = False
                break
            rows = s.view().model_dump()['memory_rows']
            labels = {r['label'] for r in rows if r['value'] == 'matched'}
            verified = s.view().phase != 'VERIFY_ID'
            made, level, emo = STATE['calls'] - before, box['intensity'], box['label']
            rec = {'reply': result.reply, 'prior_agent': prior, 'intensity': level, 'confirmed': len(labels),
                   'was_verified': was_verified}
            verdict, problems = hits_for(rec), judge(result.reply, labels, verified, was_verified, made, emo, level, values, expected[i])
            strikes = int(next(r['value'] for r in rows if r['label'] == 'Off-topic strikes'))
            if kind == 'benign' and strikes:
                problems.append('strike on a benign message')
            if kind == 'benign' and is_off_topic(result.reply, labels):
                problems.append('off-topic template on a benign message')
            if kind == 'off':
                totals['off'].append((title, strikes, box['in_scope']))
            if not verified:
                totals['member'] += 1
                totals['member_bad'] += any('template' in p or 'empathy' in p for p in problems)
            totals['dist'][made] = totals['dist'].get(made, 0) + 1
            emit(f'Caller: {text}', lines)
            emit(f'Agent: {result.reply}', lines)
            scope = box['in_scope']
            scan_text, check_text = verdict or 'clean', problems or 'ok'
            emit(f'  [phase={s.view().phase} confirmed={len(labels)} llm_calls={made} intensity={level} label={emo} '
                 f'in_scope={scope} strikes={strikes} scan={scan_text} checks={check_text}]', lines)
            totals['turns'] += 1
            totals['hits'] += len(verdict)
            totals['fails'] += [f'{title} turn {i + 1}: {p}' for p in problems]
        totals['convs'] += ok
    parts = [('conversations_run', totals['convs']), ('cut', totals['cut']), ('turns', totals['turns']),
             ('membership_checked', totals['member']), ('membership_failures', totals['member_bad']),
             ('calls_per_turn', totals['dist']), ('off_topic_results', totals['off']), ('scan_hits', totals['hits']), ('check_failures', totals['fails']),
             ('retries', STATE['retries']), ('llm_calls', STATE['calls'])]
    summary = 'SUMMARY ' + ' '.join(f'{k}={v}' for k, v in parts)
    emit(summary, lines)
    OUT.write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    main()
