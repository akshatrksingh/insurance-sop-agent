"""CP1 VER-02, VER-04, VER-05, MEM-01 (identity), S3: factor matching and accumulation."""
import pytest

from cp1helpers import AVA, HOLDERS, MARGARET, MATIAN, YAWEN, gates, ident, matched, play


def verified(s):
    """True once the session has left VERIFY_ID."""
    return s.view().phase != 'VERIFY_ID'


def test_ver_02_three_factors_in_one_turn_verify():
    """VER-02: name, DOB and ID last 4 of one record verify in one turn."""
    s, _, _ = play([('t', ident(full_name='Margaret Chen', dob='1985-03-15', id_last4='4472'))])
    assert verified(s) and gates(s)[0] is True


@pytest.mark.parametrize('fields', [
    {'full_name': 'Margaret Chen', 'dob': '1985-03-15'},
    {'phone': '6505212836', 'email': 'margaret@email.com'},
    {'id_last4': '4472'},
    {},
])
def test_ver_02_fewer_than_three_factors_do_not_verify(fields):
    """VER-02: two, one or zero matching factors stay in VERIFY_ID."""
    s, _, _ = play([('t', ident(**fields))])
    assert not verified(s) and not any(gates(s))


def test_ver_04_factors_accumulate_across_turns():
    """VER-04: matched factors accumulate: one per turn, verified on the third."""
    turns = [('a', ident(full_name='Margaret Chen')), ('b', ident(dob='1985-03-15')), ('c', ident(phone='650-521-2836'))]
    s, llm, _ = play(turns[:1])
    assert matched(s) == {'Full name'} and not verified(s)
    s, _, _ = play(turns[:2])
    assert matched(s) == {'Full name', 'Date of birth'} and not verified(s)
    s, _, _ = play(turns)
    assert verified(s)


def test_ver_04_matched_factor_is_kept_when_later_turn_is_unrelated():
    """VER-04: a later turn with no identity keeps earlier matches and the phase."""
    s, _, _ = play([('a', ident(full_name='Margaret Chen')), ('b', {})])
    assert matched(s) == {'Full name'} and not verified(s)


def test_ver_04_clarifying_question_and_refusal_keep_verify_id():
    """VER-04: a clarifying question and a refusal keep the caller in VERIFY_ID."""
    s, _, results = play([('why do you need that?', {}), ('no', {'refused_verification': True})])
    assert s.view().phase == 'VERIFY_ID' and all(r.reply.strip() for r in results)


@pytest.mark.parametrize('dob', ['1985-03-15', 'March 15, 1985', '03/15/1985', '15 March 1985', 'Mar 15 1985', '3/15/1985'])
def test_ver_05_dob_formats(dob):
    """VER-05: DOB is compared after date format normalization."""
    s, _, _ = play([('t', ident(dob=dob))])
    assert 'Date of birth' in matched(s)


@pytest.mark.parametrize('phone', ['(650) 521-2836', '650-521-2836', '+1 650 521 2836', '16505212836', '650.521.2836', '+44 650 521 2836'])
def test_ver_05_phone_compared_on_last_10_digits(phone):
    """VER-05 / 4.4: phone compared on the last 10 digits."""
    s, _, _ = play([('t', ident(phone=phone))])
    assert 'Phone' in matched(s)


@pytest.mark.parametrize('name', ['margaret chen', 'MARGARET CHEN', '  Margaret    Chen  '])
def test_ver_05_name_case_and_whitespace(name):
    """VER-05: names compare case-insensitively with whitespace normalized."""
    assert 'Full name' in matched(play([('t', ident(full_name=name))])[0])


def test_ver_05_email_lowercased():
    """VER-05 / 4.4: email compared lowercased."""
    assert 'Email' in matched(play([('t', ident(email='MARGARET@Email.COM'))])[0])


def test_s3_ya_wen_li_alias_name_alias_email_and_id_last4():
    """S3 / VER-05: alias name, alias email and ID last 4 verify Ya Wen Li."""
    s, _, _ = play([('t', ident(full_name='Yaven Li', email='yawen.li@example.com', id_last4='5317'))])
    assert verified(s)


def test_ver_05_alias_phone_and_primary_forms_both_match():
    """VER-05: Ya Wen Li's primary and alias emails, and her name, all match."""
    for fields in ({'email': 'yawen.li@gmail.com'}, {'email': 'yawen.li@example.com'}, {'full_name': 'Ya Wen Li'}, {'full_name': 'Yaven Li'}):
        assert matched(play([('t', ident(**fields))])[0]), fields


@pytest.mark.parametrize('holder', HOLDERS)
def test_ver_05_id_last4_matches_whatever_id_type(holder):
    """4.4: id_last4 matches the record's value whether id_type is ssn_last4 or national_id_last4."""
    assert 'ID last 4' in matched(play([('t', ident(id_last4=holder['id_last4']))])[0])


def test_ver_02_id_last4_of_another_record_does_not_match():
    """VER-02: another person's ID last 4 does not match a record already chosen by name."""
    s, _, _ = play([('t', ident(full_name='Margaret Chen', id_last4=AVA['id_last4']))])
    assert matched(s) == {'Full name'}


def test_ver_02_factors_from_two_records_never_combine():
    """VER-02: three correct factors split over two records never verify."""
    s, _, _ = play([('t', ident(full_name=MARGARET['name'], dob=AVA['dob'], id_last4=MATIAN['id_last4']))])
    assert not verified(s) and len(matched(s)) <= 1


def test_ver_02_two_from_one_record_one_from_another_does_not_verify():
    """VER-02: two Margaret factors plus one Ava factor stay unverified with 2 matched."""
    s, _, _ = play([('t', ident(full_name='Margaret Chen', dob='1985-03-15', phone=AVA['phone']))])
    assert not verified(s) and matched(s) == {'Full name', 'Date of birth'}


def test_ver_02_mixed_records_across_turns_never_combine():
    """VER-02: factors from different records supplied on different turns do not add up."""
    s, _, _ = play([('a', ident(full_name='Margaret Chen')), ('b', ident(dob=AVA['dob'])), ('c', ident(id_last4=MATIAN['id_last4']))])
    assert not verified(s)


def test_ver_02_policy_number_is_not_a_factor():
    """VER-02: policy number plus two real factors is only 2 factors; with three real ones it verifies."""
    s, _, _ = play([('t', ident(policy_number='POL-9921', full_name='Margaret Chen', dob='1985-03-15'))])
    assert not verified(s) and matched(s) == {'Full name', 'Date of birth'}
    s, _, _ = play([('t', ident(policy_number='POL-9921'))])
    assert matched(s) == set() and not verified(s)


def test_ver_02_wrong_policy_number_does_not_block_three_real_factors():
    """VER-02: a policy number is a lookup key only, three matching factors still verify one record."""
    s, _, _ = play([('t', ident(policy_number='POL-9921', full_name='Margaret Chen', dob='1985-03-15', id_last4='4472'))])
    assert verified(s)


@pytest.mark.parametrize('fields', [
    {'dob': 'sometime last year'}, {'phone': '555'}, {'email': 'not-an-email'}, {'id_last4': '12'},
    {'full_name': ''}, {'full_name': '   '}, {'dob': '1985-13-45'}, {'id_last4': 'abcd'}, {'phone': 'call me'},
])
def test_ver_05_unusable_values_match_nothing_and_do_not_crash(fields):
    """VER-05: unusable values match nothing and the turn still replies."""
    s, _, results = play([('t', ident(**fields))])
    assert matched(s) == set() and results[0].reply.strip() and not verified(s)


def test_mem_01_extractor_runs_every_turn_and_sees_the_view():
    """MEM-01: the extractor is called on every turn with the session view."""
    s, llm, _ = play([('a', {}), ('b', {}), ('c', {})])
    assert len(llm.extract_views) == 3
    assert all(hasattr(v, 'phase') for v in llm.extract_views)


def test_mem_01_identity_stored_when_stated_in_any_turn_order():
    """MEM-01 (identity): identity stated before and after other talk is stored."""
    s, _, _ = play([('a', ident(phone='6505212836')), ('b', {}), ('c', ident(email='margaret@email.com', id_last4='4472'))])
    assert verified(s)


def test_yawen_phone_alias_is_distinct_from_margaret():
    """VER-02: Margaret's phone and Ya Wen Li's phone differ in the last digit and stay separate records."""
    s, _, _ = play([('t', ident(phone=MARGARET['phone'], full_name=YAWEN['name'], email=YAWEN['email']))])
    assert not verified(s)
