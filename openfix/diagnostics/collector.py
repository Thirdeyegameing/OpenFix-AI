from openfix.diagnostics.system import get_cpu_model, get_windows_info, get_uptime, scan_cpu, scan_memory, scan_disks, find_system_drive, scan_top_processes
from openfix.diagnostics.gpu import scan_gpu
from openfix.diagnostics.network import scan_network

def collect_system_data():
    disks = scan_disks()
    return {
        "cpu": scan_cpu(),
        "cpu_model": get_cpu_model(),
        "memory": scan_memory(),
        "disks": disks,
        "system_drive": find_system_drive(disks),
        "processes": scan_top_processes(5),
        "gpu": scan_gpu(),
        "network": scan_network(),
        "windows": get_windows_info(),
        "uptime": get_uptime(),
    }

def coverage_percent(checks):
    if not checks:
        return 0
    return round(sum(1 for value in checks if value) / len(checks) * 100)

def internet_coverage(data):
    network = data["network"]
    return coverage_percent(
        [
            network["adapter"]["available"],
            network["ping_tested"],
            network["ping"] is not None,
            network["packet_loss"] is not None,
            network["dns_tested"],
        ]
    )

def gaming_coverage(data):
    network = data["network"]
    return coverage_percent(
        [
            data["cpu"] is not None,
            data["memory"]["available"],
            data["gpu"]["available"],
            network["ping_tested"],
        ]
    )

def slow_pc_coverage(data):
    return coverage_percent(
        [
            data["cpu"] is not None,
            data["memory"]["available"],
            bool(data["processes"]),
            data["system_drive"] is not None,
        ]
    )

def storage_coverage(data):
    return 100 if data["disks"] else 0

def smart_coverage(data, event_analysis):
    network = data["network"]
    return coverage_percent(
        [
            data["cpu"] is not None,
            data["memory"]["available"],
            data["system_drive"] is not None,
            network["ping_tested"],
            data["gpu"]["available"],
            bool(data["processes"]),
            event_analysis["available"],
        ]
    )

