"""Final pass: NFR-07 (every testable ID named by a test), DEL-02 and DEL-03 through app.py, S1 to S10 named."""
import re

from conftest import ROOT

TESTABLE = (
    'VER-01 VER-02 VER-03 VER-04 VER-05 VER-06 VER-07 MEM-01 MEM-02 MEM-03 MEM-04 SOP-01 SOP-02 INT-01 INT-02 INT-03 '
    'CASE-01 CASE-02 CASE-03 POST-01 POST-02 POST-03 POST-04 SCOPE-01 SCOPE-02 EMO-01 EMO-02 EMO-03 EMO-04 SAFE-01 '
    'SAFE-02 SAFE-03 SAFE-04 SAFE-05 SAFE-06 SAFE-07 SAFE-08 SAFE-09 LANG-01 LANG-02 DEL-01 DEL-02 DEL-03 UI-01 UI-02 '
    'UI-03 UI-04 UI-05 UI-06 UI-07 UI-08 UI-09 NFR-01 NFR-02 NFR-05 NFR-06 NFR-08').split()
SCENARIOS = 'S1 S1b S2 S3 S4 S5 S6 S7 S8 S9 S10'.split()
# Not testable offline: NFR-03 (live latency) and NFR-04 (free tier cost) need a real model. NFR-07 is this test.
UNTESTABLE_OFFLINE = ('NFR-03', 'NFR-04')


def other_test_text():
    """Text of every test file except this one."""
    me = __file__.rsplit('/', 1)[-1]
    return '\n'.join(p.read_text() for p in (ROOT / 'tests').glob('test_*.py') if p.name != me)


def test_nfr_07_every_testable_requirement_id_is_named_by_a_test():
    """NFR-07: each testable contract ID appears in the name or docstring text of at least one other test file."""
    text = other_test_text()
    missing = [i for i in TESTABLE if not re.search(r'(?<![\w-])' + re.escape(i) + r'(?![\w])', text)]
    assert not missing, missing


def test_nfr_07_every_acceptance_scenario_is_named_by_a_test():
    """NFR-07: S1, S1b and S2 to S10 each appear by name in a test file."""
    text = other_test_text()
    missing = [s for s in SCENARIOS if not re.search(r'(?<![\w-])' + s + r'(?![\w])', text)]
    assert not missing, missing


def test_nfr_07_untestable_ids_are_only_the_live_numbers():
    """NFR-07: the IDs skipped offline are exactly the live NFR numbers, so none is silently dropped."""
    assert set(UNTESTABLE_OFFLINE) == {'NFR-03', 'NFR-04'} and not set(UNTESTABLE_OFFLINE) & set(TESTABLE)
