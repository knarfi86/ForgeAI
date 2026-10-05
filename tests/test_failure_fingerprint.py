import pytest

from forgeai.core.failure_fingerprint import FailureFingerprint


def fingerprint(output):
    return FailureFingerprint.from_output(output).signature


def test_traceback_signature_ignores_location_address_timing_and_color():
    first = ('\x1b[31mFile "C:\\Users\\Frank\\Game\\main.py", line 17, in update\x1b[0m\r\n'
             'AttributeError: object at 0xAB12 has no attribute velocity\r\n'
             '1 failed, 10 passed in 0.52s')
    second = ('File "/tmp/project/main.py", line 88, in update\n'
              'AttributeError: object at 0xFF34 has no attribute velocity\n'
              '1 failed, 10 passed in 3.98s')
    assert fingerprint(first) == fingerprint(second)


@pytest.mark.parametrize("first,second", [
    ('tests/test_move.py:12: AssertionError', 'tests/test_move.py:89: AssertionError'),
    ('Ran 1 test in 0.031s\nFAILED (failures=1)', 'Ran 1 test in 4.850s\nFAILED (failures=1)'),
    ('2026-10-05T09:00:00Z ERROR: missing file', '2026-10-06T11:30:59Z ERROR: missing file'),
    ('FAIL: C:\\Game\\tests\\test_move.py:12', 'FAIL: /tmp/game/tests/test_move.py:90'),
])
def test_volatile_metadata_does_not_change_signature(first, second):
    assert fingerprint(first) == fingerprint(second)


@pytest.mark.parametrize("first,second", [
    ('AssertionError: HP 10 != 20', 'AssertionError: HP 10 != 30'),
    ('FAILED tests/test_move.py::test_move', 'FAILED tests/test_attack.py::test_attack'),
    ('File "/tmp/game/main.py", line 1\nValueError: invalid', 'File "/tmp/game/combat.py", line 1\nValueError: invalid'),
    ('KeyError: velocity', 'KeyError: health'),
    ('ImportError: package.module_a', 'ImportError: package.module_b'),
    ('assert speed / duration == 2', 'assert speed / distance == 2'),
    ('AssertionError: flags 0x01 != 0x02', 'AssertionError: flags 0x01 != 0x03'),
    ('AssertionError: expected "a b"', 'AssertionError: expected "a  b"'),
])
def test_material_error_information_remains_distinct(first, second):
    assert fingerprint(first) != fingerprint(second)


def test_empty_output_has_explicit_fallback_and_stable_versioned_signature():
    empty = FailureFingerprint.from_output("")
    assert empty == FailureFingerprint.from_output("  \r\n")
    assert empty.normalized_output == "<NO_TEST_OUTPUT>"
    assert empty.signature.startswith("E-v1-")
    assert len(empty.signature) == len("E-v1-") + 16
