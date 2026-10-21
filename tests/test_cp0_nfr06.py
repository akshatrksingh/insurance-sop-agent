"""NFR-06: a key alone never triggers a network call. Live tests need LLM_API_KEY and RUN_LIVE=1."""
import os
import subprocess
import sys

from conftest import ROOT


def run_live_test(env_extra):
    """Run the live test in a subprocess pytest with the given extra environment."""
    env = {k: v for k, v in os.environ.items() if k not in ('LLM_API_KEY', 'RUN_LIVE')}
    env.update(env_extra)
    return subprocess.run(
        [sys.executable, '-m', 'pytest', 'tests/test_cp0_delivery.py::test_live_round_trip',
         '-q', '-rs', '-p', 'no:cacheprovider'],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)


def test_nfr_06_key_without_run_live_skips_live_test_and_goes_offline():
    """NFR-06: LLM_API_KEY set, RUN_LIVE unset: the live test is skipped, no connection is made."""
    r = run_live_test({'LLM_API_KEY': 'dummy_not_a_real_key_0000'})
    assert r.returncode == 0, r.stdout[-400:]
    assert '1 skipped' in r.stdout and 'passed' not in r.stdout and 'failed' not in r.stdout
    assert 'RUN_LIVE=1' in r.stdout


def test_nfr_06_run_live_without_key_also_skips():
    """NFR-06: RUN_LIVE=1 alone (no key) also skips the live test, so nothing goes out."""
    r = run_live_test({'RUN_LIVE': '1'})
    assert r.returncode == 0 and '1 skipped' in r.stdout


def test_nfr_06_isolation_clears_key_for_non_live_tests():
    """NFR-06: a key in the parent environment is cleared for ordinary tests by the autouse fixture."""
    assert not os.environ.get('LLM_API_KEY')
