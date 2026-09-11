from openfix.diagnostics.gpu import scan_gpu
from openfix.diagnostics.network import scan_network
from openfix.diagnostics.system import (
    find_system_drive,
    get_cpu_model,
    get_installed_ram_bytes,
    get_uptime,
    get_windows_info,
    scan_cpu,
    scan_disks,
    scan_memory,
    scan_top_processes,
)


def weighted_coverage(checks):
    """checks: iterable of (available_bool, weight)."""
    checks = list(checks)
    total = sum(weight for _, weight in checks)
    if total <= 0:
        return 0
    available = sum(weight for ok, weight in checks if ok)
    return round(available / total * 100)


def collect_internet_data():
    return {"network": scan_network()}


def collect_gaming_data():
    return {
        "cpu": scan_cpu(),
        "memory": scan_memory(),
        "gpu": scan_gpu(),
        "network": scan_network(),
    }


def collect_slow_pc_data():
    disks = scan_disks()
    return {
        "cpu": scan_cpu(),
        "memory": scan_memory(),
        "disks": disks,
        "system_drive": find_system_drive(disks),
        "processes": scan_top_processes(12),
    }


def collect_storage_data():
    disks = scan_disks()
    return {"disks": disks, "system_drive": find_system_drive(disks)}


def collect_system_data():
    disks = scan_disks()
    memory = scan_memory()
    return {
        "cpu": scan_cpu(),
        "cpu_model": get_cpu_model(),
        "memory": memory,
        "installed_ram": get_installed_ram_bytes(),
        "disks": disks,
        "system_drive": find_system_drive(disks),
        "processes": scan_top_processes(12),
        "gpu": scan_gpu(),
        "network": scan_network(),
        "windows": get_windows_info(),
        "uptime": get_uptime(),
    }


def internet_coverage(data):
    network = data["network"]
    return weighted_coverage(
        [
            (network["adapter"]["available"], 20),
            (network.get("connectivity_tested", bool(network.get("ping_tested") or network.get("dns_tested"))), 30),
            (network["dns_tested"], 20),
            (network["ping_tested"], 30),
        ]
    )


def gaming_coverage(data):
    network = data["network"]
    gpu = data["gpu"]
    return weighted_coverage(
        [
            (data["cpu"] is not None, 20),
            (data["memory"]["available"], 20),
            (gpu["available"], 15),
            (gpu.get("temperature") is not None, 20),
            (network.get("connectivity_tested", bool(network.get("ping_tested") or network.get("dns_tested"))), 15),
            (network["ping_tested"], 10),
        ]
    )


def slow_pc_coverage(data):
    return weighted_coverage(
        [
            (data["cpu"] is not None, 30),
            (data["memory"]["available"], 30),
            (bool(data["processes"]), 20),
            (data["system_drive"] is not None, 20),
        ]
    )


def storage_coverage(data):
    return 100 if data.get("disks") else 0


def smart_coverage(data, event_analysis):
    network = data["network"]
    gpu = data["gpu"]
    return weighted_coverage(
        [
            (data["cpu"] is not None, 15),
            (data["memory"]["available"], 15),
            (data["system_drive"] is not None, 15),
            (network.get("connectivity_tested", bool(network.get("ping_tested") or network.get("dns_tested"))), 15),
            (network["ping_tested"], 10),
            (gpu["available"], 10),
            (gpu.get("temperature") is not None, 5),
            (bool(data["processes"]), 5),
            (event_analysis["available"], 10),
        ]
    )
