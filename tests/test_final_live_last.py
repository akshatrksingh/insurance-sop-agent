"""Final fix batch: tests/live_last.py is gated (NFR-06), lists a to d, and its files respect the size and style rules. No model call."""
import os
import subprocess
import sys

from conftest import ROOT

SCRIPT = ROOT / 'tests' / 'live_last.py'
PARTS = ['live_last.py', 'live_last_data.py', 'live_last_checks.py']


def run(*args, **env):
    """Run the script in a subprocess with no key and RUN_LIVE only as given."""
    base = {k: v for k, v in os.environ.items() if k not in ('LLM_API_KEY', 'RUN_LIVE')}
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, env={**base, **env}, timeout=60, cwd=str(ROOT))


def test_nfr_06_live_last_refuses_without_run_live_with_exit_code_2():
    """NFR-06: no RUN_LIVE means exit 2, even with a key and with a named conversation."""
    for args, env in (((), {}), (('a',), {}), ((), {'LLM_API_KEY': 'gsk_SENTINELTOKEN123456'})):
        r = run(*args, **env)
        assert r.returncode == 2 and 'RUN_LIVE=1' in r.stdout and 'gsk_SENTINEL' not in r.stdout + r.stderr


def test_nfr_06_live_last_lists_four_conversations():
    """NFR-06: --list names a to d without RUN_LIVE."""
    r = run('--list')
    assert r.returncode == 0 and [x.split()[0] for x in r.stdout.splitlines() if x.strip()] == list('abcd')


def test_nfr_05_live_last_files_are_short_dashless_and_print_free():
    """NFR-05, LANG-01: each live_last file is at most 200 lines with no dash and no print call."""
    for name in PARTS:
        text = (ROOT / 'tests' / name).read_text()
        assert len(text.splitlines()) <= 200 and '\u2014' not in text and '\u2013' not in text and 'print(' not in text, name
