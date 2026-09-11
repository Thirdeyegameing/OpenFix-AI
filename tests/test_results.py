from openfix.core.helpers import make_result


def test_unavailable_result_keeps_score_none():
    result = make_result("X", None, coverage=0)
    assert result["score"] is None
    assert result["availability"] == "unavailable"


def test_partial_result_is_marked_partial():
    result = make_result("X", 95, coverage=80)
    assert result["score"] == 95
    assert result["availability"] == "partial"


def test_score_is_clamped():
    assert make_result("X", 150, coverage=100)["score"] == 100
    assert make_result("X", -10, coverage=100)["score"] == 0
