from openfix.doctors.smart import doctor_smart

GB = 1024 ** 3


def base_data(health="Healthy"):
    return {
        "cpu": 10,
        "memory": {"available": True, "percent": 30, "total": 16 * GB},
        "disks": [
            {
                "device": "C:\\",
                "free": 100 * GB,
                "total": 500 * GB,
                "used": 400 * GB,
                "percent": 80,
                "is_system": True,
                "scored": True,
                "drive_type": "fixed",
            }
        ],
        "system_drive": {"device": "C:\\"},
        "physical_storage": {
            "tested": True,
            "available": True,
            "disks": [
                {
                    "name": "Example SSD",
                    "health_status": health,
                    "operational_status": ["OK"],
                    "media_type": "SSD",
                    "bus_type": "NVMe",
                    "size": 500 * GB,
                }
            ],
        },
        "processes": [{"name": "app.exe", "memory": 100 * 1024 * 1024}],
        "gpu": {"available": True, "temperature": 55},
        "network": {
            "adapter": {"available": True},
            "connectivity_tested": True,
            "online": True,
            "ping_tested": True,
            "icmp_reachable": True,
            "ping": 20,
            "packet_loss": 0,
            "dns_tested": True,
        },
    }


def event_analysis():
    return {
        "available": True,
        "hardware_errors": 0,
        "hardware_warnings": 0,
        "storage_errors": 0,
        "shutdown_errors": 0,
        "gpu_errors": 0,
        "app_crashes": 0,
        "correlations": [],
    }


def test_smart_doctor_healthy_physical_disk_does_not_create_issue():
    result = doctor_smart(base_data("Healthy"), event_analysis())
    assert result["score"] == 100
    assert not any("physical" in issue.lower() and "warning" in issue.lower() for issue in result["issues"])


def test_smart_doctor_unhealthy_physical_disk_gets_priority():
    result = doctor_smart(base_data("Unhealthy"), event_analysis())
    assert result["score"] < 90
    assert result["target_doctor"] == "storage"
    assert "physical storage" in result["primary_issue"].lower()
    assert any("back up" in action.lower() for action in result["actions"])
