from unittest.mock import patch

from openfix.doctors.full_scan import doctor_full


def fake_result(score, coverage, title="X"):
    return {
        "title": title,
        "score": score,
        "coverage": coverage,
        "facts": [],
        "issues": [],
        "actions": [],
        "primary_issue": None,
        "why_it_matters": None,
        "target_doctor": None,
    }


def test_full_scan_no_available_areas_is_not_100():
    unavailable = fake_result(None, 0)
    event = {**unavailable, "event_analysis": {"available": False}}
    with patch("openfix.doctors.full_scan.create_event_result", return_value=event), \
         patch("openfix.doctors.full_scan.doctor_internet", return_value=unavailable), \
         patch("openfix.doctors.full_scan.doctor_gaming", return_value=unavailable), \
         patch("openfix.doctors.full_scan.doctor_slow_pc", return_value=unavailable), \
         patch("openfix.doctors.full_scan.doctor_storage", return_value=unavailable), \
         patch("openfix.doctors.full_scan.doctor_smart", return_value=unavailable), \
         patch("openfix.doctors.full_scan.smart_coverage", return_value=0):
        result = doctor_full({}, {})
    assert result["score"] is None
    assert result["unavailable_areas"] == 5


def test_full_scan_excludes_unavailable_area_from_weighted_score():
    good = fake_result(100, 100)
    unavailable = fake_result(None, 0)
    event = {**good, "event_analysis": {"available": True}}
    with patch("openfix.doctors.full_scan.create_event_result", return_value=event), \
         patch("openfix.doctors.full_scan.doctor_internet", return_value=good), \
         patch("openfix.doctors.full_scan.doctor_gaming", return_value=unavailable), \
         patch("openfix.doctors.full_scan.doctor_slow_pc", return_value=good), \
         patch("openfix.doctors.full_scan.doctor_storage", return_value=good), \
         patch("openfix.doctors.full_scan.doctor_smart", return_value=good), \
         patch("openfix.doctors.full_scan.smart_coverage", return_value=90):
        result = doctor_full({}, {})
    assert result["score"] == 100
    assert result["healthy_areas"] == 4
    assert result["unavailable_areas"] == 1
