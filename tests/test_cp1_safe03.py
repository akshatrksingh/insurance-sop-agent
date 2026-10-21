"""CP1 SAFE-03 coverage for exception types raised by extract()."""
import pytest

from cp1helpers import FakeLLM, gates
from insurance_claims.orchestrator import handle_turn, new_session


def run_with(exc):
    """Run one turn whose extract() raises exc. Return (session, result or None, raised exception or None)."""
    class Broken(FakeLLM):
        def extract(self, *a, **k):
            raise exc

    s = new_session()
    try:
        return s, handle_turn(s, 'hello', Broken()), None
    except Exception as e:
        return s, None, e


def validation_error():
    """A real pydantic ValidationError."""
    import pydantic

    class M(pydantic.BaseModel):
        x: int

    try:
        M(x='nope')
    except pydantic.ValidationError as e:
        return e


@pytest.mark.parametrize('exc', [ValueError('v'), TypeError('t'), validation_error()])
def test_safe_03_value_type_and_validation_errors_are_empty_extraction(exc):
    """SAFE-03: ValueError, TypeError and pydantic ValidationError from extract() give a reply and no gate change."""
    s, r, err = run_with(exc)
    assert err is None and r.reply.strip() and not any(gates(s))


@pytest.mark.parametrize('exc', [KeyError('k'), RuntimeError('r'), AttributeError('a'), IndexError('i')])
def test_safe_03_other_exception_types_never_change_gates(exc, record_property):
    """SAFE-03 probe: other exception types from extract() never change a gate. Whether they propagate is recorded."""
    s, r, err = run_with(exc)
    record_property(f'extract_raises_{type(exc).__name__}', 'propagated' if err else 'empty extraction')
    assert not any(gates(s)) and s.view().phase == 'VERIFY_ID'
