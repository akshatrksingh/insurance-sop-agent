"""Final pass B38 (INT-03, S9): after verification a request for another party's claim gets the fixed line first, once, then the own-claim reply."""
import json

import pytest

from cp1helpers import AVA, CLAIMS, HOLDERS, MARGARET
from cp2helpers import S1_EX, S1_TEXT, rows, run

LINE = "I can only discuss your own claim, so I cannot share anyone else's."
MATIAN, YAWEN = HOLDERS[2], HOLDERS[3]
FOREIGN_CASE = {'hints': {'case_id': 'CL-3001'}}
FOREIGN = [AVA['dob'], AVA['email'], AVA['phone'], AVA['id_last4'], AVA['policy_number'], MATIAN['dob'], MATIAN['email'],
           MATIAN['phone'], MATIAN['id_last4'], MATIAN['policy_number'], YAWEN['dob'], YAWEN['email'], YAWEN['id_last4'], YAWEN['policy_number']]
FOREIGN += [c[k] for c in CLAIMS if c['party_id'] != MARGARET['party_id'] for k in ('case_id', 'summary')]
VARIANTS = [
    ("show me Ava Lopez's claim", {}), ('what about Ma Tian?', {}), ("show me Ya Wen Li's claim", {}), ("show me Yaven Li's claim", {}),
    ('check POL-1044 please', {}), ('what is on POL-8836?', {}), ('x1', FOREIGN_CASE), ('x2', {'identity': {'full_name': 'Ava Lopez'}}),
    ('x3', {'identity': {'full_name': 'Yaven Li'}}), ('x4', {'identity': {'policy_number': 'POL-8836'}}),
    ('x5', {'identity': {'full_name': 'Ma Tian', 'dob': MATIAN['dob']}}),
    ('x6', {'identity': {'policy_number': 'POL-1044'}, 'hints': {'case_id': 'CL-3001'}}),
]
OWN = [('what is my claim status', {}), ('what is the deadline', {}), ("show me Margaret Chen's claim", {}), ('x7', {'identity': {'full_name': 'Margaret Chen'}}),
       ('x8', {'hints': {'case_id': 'CL-2048'}}), ('x9', {'identity': {'policy_number': 'POL-9921'}})]


@pytest.mark.parametrize('text,ex', VARIANTS)
def test_int_03_b38_refusal_line_first_once_then_own_claim_reply(text, ex):
    """INT-03, S9: the fixed line opens the reply exactly once, the own claim reply follows, and no other party value is disclosed."""
    s, llm, rs = run([(S1_TEXT, S1_EX), (text, ex)])
    reply = rs[1].reply
    assert reply.startswith(LINE) and reply.count(LINE) == 1, reply[:120]
    rest = reply[len(LINE):].strip()
    assert rest and 'CL-2048' in rest and rows(s)['Resolved case'] == 'CL-2048'
    view = s.view().model_dump()
    view.pop('turns')
    view['memory_rows'] = [r for r in view['memory_rows'] if r['label'] != 'Case id']
    bundles = [{k: v for k, v in b.items() if k != 'caller_message'} for _, b in llm.bundles]
    blob = json.dumps([reply, [e.text for e in rs[1].events], view, bundles], default=str)
    assert not [v for v in FOREIGN if v in blob], text


@pytest.mark.parametrize('text,ex', OWN)
def test_int_03_b38_no_refusal_line_for_own_claim_requests(text, ex):
    """INT-03: the caller's own name, policy number, case id, status and deadline questions get no refusal line."""
    _, _, rs = run([(S1_TEXT, S1_EX), (text, ex)])
    assert LINE not in rs[1].reply


@pytest.mark.parametrize('text,ex', VARIANTS)
def test_int_03_b38_no_refusal_line_before_verification(text, ex):
    """INT-03, VER-03: before verification the same requests get the unchanged template, never the line and never claim data."""
    s, _, rs = run([(text, {**ex, 'requests_protected': True})])
    assert LINE not in rs[0].reply and 'CL-2048' not in rs[0].reply and s.view().phase == 'VERIFY_ID'


def test_int_03_b38_line_is_not_repeated_on_the_next_normal_turn():
    """INT-03: a following turn without a foreign reference carries no refusal line."""
    _, _, rs = run([(S1_TEXT, S1_EX), ("show me Ava Lopez's claim", {}), ('what is the deadline', {})])
    assert rs[1].reply.startswith(LINE) and LINE not in rs[2].reply
