from unittest.mock import patch

from openfix.diagnostics import storage_health
from openfix.diagnostics.collector import storage_coverage
from openfix.doctors.storage import doctor_storage

GB = 1024 ** 3


def logical_drive():
    return {
        "device": "C:\\",
        "free": 50 * GB,
        "total": 200 * GB,
        "used": 150 * GB,
        "percent": 75,
        "is_system": True,
        "scored": True,
        "drive_type": "fixed",
    }


def physical(health="Healthy", operational=None):
    return {
        "name": "Example SSD",
        "health_status": health,
        "operational_status": operational or ["OK"],
        "media_type": "SSD",
        "bus_type": "NVMe",
        "size": 500 * GB,
        "temperature": 41,
        "wear": None,
        "read_errors_total": None,
        "write_errors_total": None,
    }


def test_physical_disk_state_healthy():
    assert storage_health.physical_disk_state(physical()) == "healthy"


def test_physical_disk_state_warning():
    assert storage_health.physical_disk_state(physical("Warning")) == "warning"


def test_physical_disk_state_unhealthy():
    assert storage_health.physical_disk_state(physical("Unhealthy")) == "unhealthy"


def test_physical_disk_state_degraded_operational_status():
    assert storage_health.physical_disk_state(physical("Healthy", ["Degraded"])) == "warning"


def test_storage_doctor_penalizes_explicit_unhealthy_status():
    result = doctor_storage(
        {
            "disks": [logical_drive()],
            "system_drive": logical_drive(),
            "physical_storage": {"tested": True, "available": True, "disks": [physical("Unhealthy")]},
        }
    )
    assert result["score"] < 90
    assert any("unhealthy" in issue.lower() for issue in result["issues"])
    assert any("back up" in action.lower() for action in result["actions"])


def test_storage_doctor_does_not_invent_fault_when_physical_health_unavailable():
    result = doctor_storage(
        {
            "disks": [logical_drive()],
            "system_drive": logical_drive(),
            "physical_storage": {"tested": True, "available": False, "disks": []},
        }
    )
    assert result["score"] == 100
    assert not result["issues"]


def test_storage_coverage_is_partial_without_physical_health():
    data = {"disks": [logical_drive()], "physical_storage": {"tested": True, "available": False, "disks": []}}
    assert storage_coverage(data) == 80


def test_scan_physical_disks_does_not_collect_serial_number():
    fake = {
        "ok": True,
        "stdout": '{"Success":true,"Disks":[{"FriendlyName":"SSD","HealthStatus":"Healthy","OperationalStatus":["OK"],"MediaType":"SSD","BusType":"NVMe","Size":1000}]}',
        "stderr": "",
    }
    with patch.object(storage_health, "run_powershell", return_value=fake):
        result = storage_health.scan_physical_disks()
    assert result["available"] is True
    assert "serial" not in result["disks"][0]
    assert "unique_id" not in result["disks"][0]
