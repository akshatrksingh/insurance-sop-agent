"""CP0 part of UI-03: Session memory shows no stored values and no claim data before verification."""
import json

import pytest

from apphelpers import make_app
from conftest import ROOT

FX = ROOT / 'insurance_claims' / 'fixtures'
MARGARET = ('Hi, I am Margaret Chen, policy POL-9921, my denied healthcare claim from January, '
            'DOB 1985-03-15, last four 4472')


def stored_values():
    """Policyholder and claim values from the fixtures that must not appear in the sidebar."""
    vals = set()
    for row in json.loads((FX / 'policyholders.json').read_text()):
        vals |= {str(v) for k, v in row.items() if k != 'party_id' and len(str(v)) > 3}
    for row in json.loads((FX / 'claims.json').read_text()):
        for k in ('case_id', 'summary', 'denial_reason', 'appeal_deadline', 'allowed_max_amount'):
            if len(str(row.get(k, ''))) > 3:
                vals.add(str(row[k]))
    return vals


def sidebar_text(at):
    """Join the sidebar markdown values."""
    return '\n'.join(m.value for m in at.sidebar.markdown)


def test_ui_03_empty_memory_has_no_stored_values_or_claim_data(no_key):
    """UI-03: before any message the sidebar shows no policyholder value and no claim data."""
    side = sidebar_text(make_app().run())
    leaks = [v for v in stored_values() if v in side]
    assert not leaks, len(leaks)


def test_ui_03_view_before_verification_has_no_stored_values_or_claim_data(fake_backend):
    """UI-03: after the caller states identity details unverified, the sidebar and Session.view() hold no stored value or claim data."""
    at = make_app().run()
    at.chat_input[0].set_value(MARGARET).run()
    view = json.dumps(at.session_state['session'].view().model_dump(mode='json'))
    side = sidebar_text(at)
    gates = at.session_state['session'].view().phases
    assert not any(g.done for p in gates for g in p.gates), 'FakeLLM verified the caller; premise of the test fails'
    for v in stored_values():
        assert v not in side, 'sidebar leak'
        if v in MARGARET:
            continue
        assert v not in view, 'view leak'


@pytest.mark.parametrize('text', ['hello', MARGARET])
def test_ui_03_memory_section_labels_present(fake_backend, text):
    """UI-03: Session memory section stays present with its helper line after a turn."""
    at = make_app().run()
    at.chat_input[0].set_value(text).run()
    side = sidebar_text(at)
    assert 'Session memory' in side and 'Remembered from this chat. Cleared on reset.' in side
