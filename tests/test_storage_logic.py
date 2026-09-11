from openfix.core.scoring import disk_space_state
from openfix.doctors.storage import doctor_storage

GB = 1024 ** 3


def drive(free_gb, total_gb=100, percent_used=None, *, system=False, scored=True, drive_type="fixed"):
    if percent_used is None:
        percent_used = 100 - (free_gb / total_gb * 100)
    return {
        "device": "C:\\" if system else "D:\\",
        "free": free_gb * GB,
        "total": total_gb * GB,
        "used": (total_gb - free_gb) * GB,
        "percent": percent_used,
        "is_system": system,
        "scored": scored,
        "drive_type": drive_type,
    }


def test_large_data_drive_low_percent_but_many_gb_is_good():
    state, _, _ = disk_space_state(drive(200, total_gb=4000, percent_used=95, system=False))
    assert state == "good"


def test_system_drive_critical_under_5gb():
    state, _, _ = disk_space_state(drive(4, total_gb=100, system=True))
    assert state == "critical"


def test_removable_drive_is_ignored():
    state, _, _ = disk_space_state(drive(1, total_gb=64, scored=False, drive_type="removable"))
    assert state == "ignored"


def test_storage_doctor_unavailable_has_no_score():
    result = doctor_storage({"disks": [], "system_drive": None})
    assert result["score"] is None
    assert result["coverage"] == 0


def test_ignored_drive_does_not_reduce_score():
    d = drive(1, total_gb=64, scored=False, drive_type="removable")
    result = doctor_storage({"disks": [d], "system_drive": None})
    assert result["score"] == 100
    assert not result["issues"]
