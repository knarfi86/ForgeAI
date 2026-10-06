from types import SimpleNamespace

import pytest

from forgeai.core.stagnation_detector import StagnationDetector


def verification(signature, *, success=False):
    return SimpleNamespace(success=success, failure_fingerprint=signature)


def repair(attempt, *paths):
    return SimpleNamespace(repair_attempt=attempt, planned_paths=tuple(sorted(paths)))


def test_detector_marks_repeated_failure_and_target_as_stagnating():
    detector = StagnationDetector()
    status = detector.evaluate(
        [verification("E-v1-a"), verification("E-v1-a"), verification("E-v1-a")],
        [repair(1, "main.py"), repair(2, "main.py")],
    )

    assert status.active is True
    assert status.error_signature == "E-v1-a"
    assert status.same_error_count == 3
    assert status.repeated_paths == ("main.py",)
    assert status.same_target_count == 2
    assert status.reason_codes == ("repeated_failure", "repeated_target")
    assert status.detected_after_repair_attempt == 2


def test_changed_failure_prevents_stagnation_even_on_same_target():
    status = StagnationDetector().evaluate(
        [verification("E-v1-a"), verification("E-v1-b")],
        [repair(1, "main.py"), repair(2, "main.py")],
    )

    assert status.active is False
    assert status.same_error_count == 1
    assert status.same_target_count == 2
    assert status.reason_codes == ("repeated_target",)


def test_changed_target_prevents_stagnation_even_on_same_error():
    status = StagnationDetector().evaluate(
        [verification("E-v1-a"), verification("E-v1-a"), verification("E-v1-a")],
        [repair(1, "main.py"), repair(2, "combat.py")],
    )

    assert status.active is False
    assert status.same_error_count == 3
    assert status.same_target_count == 1
    assert status.reason_codes == ("repeated_failure",)


def test_success_resets_failure_side_without_deleting_history():
    verifications = [verification("E-v1-a"), verification("E-v1-a"), verification(None, success=True)]
    repairs = [repair(1, "main.py"), repair(2, "main.py")]
    status = StagnationDetector().evaluate(verifications, repairs)

    assert status.active is False
    assert status.error_signature is None
    assert status.same_error_count == 0
    assert status.same_target_count == 2


def test_multi_file_target_set_is_order_independent():
    status = StagnationDetector().evaluate(
        [verification("E-v1-a"), verification("E-v1-a")],
        [repair(1, "b.py", "a.py"), repair(2, "a.py", "b.py")],
    )

    assert status.active is True
    assert status.repeated_paths == ("a.py", "b.py")


def test_thresholds_must_require_repetition():
    with pytest.raises(ValueError):
        StagnationDetector(same_error_threshold=1)
    with pytest.raises(ValueError):
        StagnationDetector(same_target_threshold=1)
