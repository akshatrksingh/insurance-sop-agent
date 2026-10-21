"""Final pass: tests/live_final.py is gated (NFR-06, SAFE-04), lists a to k, and is not collected. Nothing here calls a model."""
import os
import subprocess
import sys

from conftest import ROOT

SCRIPT = ROOT / 'tests' / 'live_final.py'
PARTS = ['live_final.py', 'live_final_data.py', 'live_final_checks.py']


def run(*args, **env):
    """Run the script in a subprocess with no key and RUN_LIVE only as given."""
    base = {k: v for k, v in os.environ.items() if k not in ('LLM_API_KEY', 'RUN_LIVE')}
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, env={**base, **env}, timeout=60, cwd=str(ROOT))


def test_nfr_06_live_final_refuses_without_run_live_with_exit_code_2():
    """NFR-06: no RUN_LIVE means exit code 2 and the refusal text, for all conversations and for a named one."""
    for args in ((), ('a',)):
        r = run(*args)
        assert r.returncode == 2 and 'RUN_LIVE=1' in r.stdout


def test_nfr_06_live_final_refuses_with_a_key_but_without_run_live():
    """NFR-06: a key alone never starts a live run."""
    r = run(LLM_API_KEY='gsk_SENTINELTOKEN123456')
    assert r.returncode == 2 and 'gsk_SENTINEL' not in r.stdout + r.stderr


def test_nfr_06_live_final_lists_the_nine_conversations():
    """NFR-06: --list names conversations a to k without needing RUN_LIVE."""
    r = run('--list')
    assert r.returncode == 0
    letters = [line.split()[0] for line in r.stdout.splitlines() if line.strip()]
    assert letters == list('abcdefghijk'), letters


def test_nfr_05_live_final_files_are_short_dashless_and_print_free():
    """NFR-05, LANG-01: each live_final file is at most 200 lines, holds no dash and no print call."""
    for name in PARTS:
        text = (ROOT / 'tests' / name).read_text()
        assert len(text.splitlines()) <= 200 and '\u2014' not in text and '\u2013' not in text and 'print(' not in text, name
