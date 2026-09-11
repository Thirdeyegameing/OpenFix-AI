import sys
import os
import re
import json
import socket
import subprocess
from datetime import datetime

import psutil

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QProgressBar,
    QScrollArea,
    QMessageBox,
    QStackedWidget,
)


APP_VERSION = "0.5.2-dev4"


# =========================================================
# HELPERS
# =========================================================

def clamp(value, minimum=0, maximum=100):
    return max(minimum, min(maximum, value))


def safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def safe_float(value, default=None):
    try:
        return float(value)
    except Exception:
        return default


def format_bytes(value):
    if value is None:
        return "Not available"

    try:
        value = float(value)
        if value >= 1024 ** 3:
            return f"{value / (1024 ** 3):.1f} GB"
        return f"{value / (1024 ** 2):.0f} MB"
    except Exception:
        return "Not available"


def format_uptime(seconds):
    if seconds is None:
        return "Not available"

    try:
        seconds = int(seconds)
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        minutes = (seconds % 3600) // 60

        if days > 0:
            return f"{days}d {hours}h"
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"
    except Exception:
        return "Not available"


def run_powershell(command, timeout=15):
    try:
        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NO_WINDOW

        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                command,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            creationflags=creationflags,
            timeout=timeout,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def coverage_percent(checks):
    if not checks:
        return 0
    available = sum(1 for item in checks if bool(item))
    return round((available / len(checks)) * 100)


def make_result(
    title,
    score,
    facts=None,
    issues=None,
    actions=None,
    note="",
    coverage=100,
    extra=None,
):
    coverage = clamp(int(coverage))
    result = {
        "title": title,
        "score": clamp(int(score)),
        "facts": facts or [],
        "issues": issues or [],
        "actions": actions or [],
        "note": note,
        "coverage": coverage,
        "partial": coverage < 100,
    }

    if extra:
        result.update(extra)

    return result


# =========================================================
# SYSTEM INFORMATION
# =========================================================

def get_cpu_model():
    command = r"""
    Get-CimInstance Win32_Processor |
    Select-Object -First 1 -ExpandProperty Name
    """
    output = run_powershell(command, timeout=8)
    return output.strip() if output else "Not available"


def get_windows_info():
    command = r"""
    $os = Get-CimInstance Win32_OperatingSystem |
    Select-Object -First 1 Caption, Version, BuildNumber
    $os | ConvertTo-Json -Compress
    """

    output = run_powershell(command, timeout=8)
    if output:
        try:
            data = json.loads(output)
            caption = data.get("Caption") or "Windows"
            version = data.get("Version") or "Not available"
            build = data.get("BuildNumber") or "Not available"
            return {
                "available": True,
                "name": caption,
                "version": version,
                "build": build,
            }
        except Exception:
            pass

    return {
        "available": False,
        "name": "Windows",
        "version": "Not available",
        "build": "Not available",
    }


def get_uptime():
    try:
        boot_time = psutil.boot_time()
        now = datetime.now().timestamp()
        seconds = now - boot_time
        return {
            "available": True,
            "seconds": seconds,
            "text": format_uptime(seconds),
        }
    except Exception:
        return {
            "available": False,
            "seconds": None,
            "text": "Not available",
        }


# =========================================================
# CPU / RAM / STORAGE
# =========================================================

def scan_cpu():
    try:
        return psutil.cpu_percent(interval=1)
    except Exception:
        return None


def scan_memory():
    try:
        ram = psutil.virtual_memory()
        return {
            "available": True,
            "percent": ram.percent,
            "used": ram.used,
            "total": ram.total,
            "free": ram.available,
        }
    except Exception:
        return {
            "available": False,
            "percent": None,
            "used": None,
            "total": None,
            "free": None,
        }


def scan_disks():
    drives = []
    seen = set()

    try:
        partitions = psutil.disk_partitions(all=False)
    except Exception:
        partitions = []

    for partition in partitions:
        device = partition.device
        if not device or device in seen:
            continue

        seen.add(device)
        try:
            usage = psutil.disk_usage(partition.mountpoint)
            drives.append(
                {
                    "device": device,
                    "mountpoint": partition.mountpoint,
                    "filesystem": partition.fstype,
                    "total": usage.total,
                    "used": usage.used,
                    "free": usage.free,
                    "percent": usage.percent,
                }
            )
        except Exception:
            pass

    return drives


def find_system_drive(disks):
    system_drive = os.environ.get("SystemDrive", "C:").upper().rstrip("\\")

    for drive in disks:
        device = str(drive.get("device", "")).upper().rstrip("\\")
        if device.startswith(system_drive):
            return drive

    return disks[0] if disks else None


# =========================================================
# PROCESS INFORMATION
# =========================================================

def scan_top_processes(limit=5):
    processes = []

    try:
        iterator = psutil.process_iter(["pid", "name", "memory_info"])
        for process in iterator:
            try:
                info = process.info
                memory_info = info.get("memory_info")
                memory = memory_info.rss if memory_info else 0
                processes.append(
                    {
                        "name": info.get("name") or "Unknown",
                        "pid": info.get("pid") or 0,
                        "memory": memory,
                    }
                )
            except Exception:
                pass
    except Exception:
        pass

    processes.sort(key=lambda item: item["memory"], reverse=True)
    return processes[:limit]


# =========================================================
# GPU
# =========================================================

def gpu_preference_score(item):
    name = str(item.get("name", "")).lower()
    score = 0

    if "microsoft basic" in name:
        return -1000

    if any(token in name for token in ("rtx", "gtx", "radeon rx", "arc a")):
        score += 500
    elif "nvidia" in name or "amd" in name or "radeon" in name:
        score += 300
    elif "intel" in name:
        score += 100

    vram = item.get("vram") or 0
    score += min(int(vram / (1024 ** 3)) * 10, 100)
    return score


def scan_gpu():
    gpu = {
        "available": False,
        "name": "Not available",
        "vram": None,
        "usage": None,
        "temperature": None,
        "driver": None,
        "gpu_count": 0,
        "all_gpus": [],
        "source": None,
    }

    command = r"""
    $items = Get-CimInstance Win32_VideoController |
    Select-Object Name, AdapterRAM, DriverVersion
    $items | ConvertTo-Json -Compress
    """

    output = run_powershell(command, timeout=10)
    controllers = []

    if output:
        try:
            raw = json.loads(output)
            if isinstance(raw, dict):
                raw = [raw]

            if isinstance(raw, list):
                for item in raw:
                    if not isinstance(item, dict):
                        continue

                    adapter_ram = safe_int(item.get("AdapterRAM"), 0)
                    controllers.append(
                        {
                            "name": item.get("Name") or "Unknown GPU",
                            "vram": adapter_ram if adapter_ram > 0 else None,
                            "driver": item.get("DriverVersion") or "Unknown",
                        }
                    )
        except Exception:
            controllers = []

    real_controllers = [
        item
        for item in controllers
        if "microsoft basic" not in item["name"].lower()
    ]

    if not real_controllers:
        real_controllers = controllers

    if real_controllers:
        preferred = max(real_controllers, key=gpu_preference_score)
        gpu.update(
            {
                "available": True,
                "name": preferred["name"],
                "vram": preferred["vram"],
                "driver": preferred["driver"],
                "gpu_count": len(real_controllers),
                "all_gpus": [item["name"] for item in real_controllers],
                "source": "Windows",
            }
        )

    # NVIDIA gives reliable usage and temperature information when available.
    try:
        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NO_WINDOW

        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,utilization.gpu,temperature.gpu,driver_version",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            creationflags=creationflags,
            timeout=5,
        )

        if result.returncode == 0 and result.stdout.strip():
            parsed = []
            for line in result.stdout.strip().splitlines():
                parts = [part.strip() for part in line.split(",")]
                if len(parts) < 5:
                    continue

                parsed.append(
                    {
                        "name": parts[0],
                        "vram_mb": safe_float(parts[1], 0),
                        "usage": safe_float(parts[2]),
                        "temperature": safe_float(parts[3]),
                        "driver": parts[4],
                    }
                )

            if parsed:
                preferred = max(parsed, key=lambda item: item["vram_mb"] or 0)
                gpu.update(
                    {
                        "available": True,
                        "name": preferred["name"],
                        "vram": preferred["vram_mb"] * 1024 * 1024,
                        "usage": preferred["usage"],
                        "temperature": preferred["temperature"],
                        "driver": preferred["driver"],
                        "gpu_count": len(parsed),
                        "all_gpus": [item["name"] for item in parsed],
                        "source": "NVIDIA",
                    }
                )
    except Exception:
        pass

    return gpu


# =========================================================
# NETWORK
# =========================================================

def get_active_adapter():
    command = r"""
    $route = Get-NetRoute -DestinationPrefix "0.0.0.0/0" -ErrorAction SilentlyContinue |
    Where-Object {$_.NextHop -ne "0.0.0.0"} |
    Sort-Object RouteMetric |
    Select-Object -First 1

    if ($route) {
        Get-NetAdapter -InterfaceIndex $route.InterfaceIndex -ErrorAction SilentlyContinue |
        Select-Object Name, InterfaceDescription, LinkSpeed, MacAddress, ifIndex |
        ConvertTo-Json -Compress
    }
    """

    output = run_powershell(command, timeout=10)
    adapter = {
        "available": False,
        "name": "Not available",
        "description": "Not available",
        "link_speed": "Not available",
        "mac": "Not available",
        "interface_index": None,
    }

    if output:
        try:
            data = json.loads(output)
            if isinstance(data, dict):
                adapter.update(
                    {
                        "available": True,
                        "name": data.get("Name") or "Not available",
                        "description": data.get("InterfaceDescription") or "Not available",
                        "link_speed": data.get("LinkSpeed") or "Not available",
                        "mac": data.get("MacAddress") or "Not available",
                        "interface_index": data.get("ifIndex"),
                    }
                )
        except Exception:
            pass

    return adapter


def get_default_gateway():
    command = r"""
    Get-NetRoute -DestinationPrefix "0.0.0.0/0" -ErrorAction SilentlyContinue |
    Where-Object {$_.NextHop -ne "0.0.0.0"} |
    Sort-Object RouteMetric |
    Select-Object -First 1 -ExpandProperty NextHop
    """

    output = run_powershell(command, timeout=10)
    return output if output else "Not available"


def get_dns_servers():
    command = r"""
    Get-DnsClientServerAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object {$_.ServerAddresses.Count -gt 0} |
    Select-Object -ExpandProperty ServerAddresses |
    Select-Object -Unique
    """

    output = run_powershell(command, timeout=10)
    if not output:
        return []

    return [line.strip() for line in output.splitlines() if line.strip()]


def test_dns():
    try:
        socket.gethostbyname("cloudflare.com")
        return {"available": True, "ok": True}
    except socket.gaierror:
        return {"available": True, "ok": False}
    except Exception:
        return {"available": False, "ok": False}


def parse_ping_output(output):
    result = {"ping": None, "packet_loss": None}

    matches = re.findall(
        r"(?:time|เวลา)\s*[=<]\s*(\d+)\s*ms",
        output,
        flags=re.IGNORECASE,
    )

    numbers = [safe_int(value) for value in matches]
    if numbers:
        result["ping"] = round(sum(numbers) / len(numbers))
    elif re.search(r"(?:time|เวลา)\s*<\s*1\s*ms", output, flags=re.IGNORECASE):
        result["ping"] = 1

    loss_patterns = [
        r"(\d{1,3})%\s*loss",
        r"lost\s*=\s*\d+\s*\((\d{1,3})%",
        r"สูญหาย\s*=\s*\d+\s*\((\d{1,3})%",
    ]

    for pattern in loss_patterns:
        match = re.search(pattern, output, flags=re.IGNORECASE)
        if match:
            value = safe_int(match.group(1))
            if 0 <= value <= 100:
                result["packet_loss"] = value
                break

    if result["packet_loss"] is None:
        percentages = re.findall(r"(\d{1,3})\s*%", output)
        values = [safe_int(value) for value in percentages]
        values = [value for value in values if 0 <= value <= 100]
        if values:
            result["packet_loss"] = values[-1]

    return result


def test_ping():
    result_data = {
        "available": False,
        "internet": False,
        "ping": None,
        "packet_loss": None,
    }

    try:
        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NO_WINDOW

        result = subprocess.run(
            ["ping", "-n", "4", "-w", "2000", "1.1.1.1"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            creationflags=creationflags,
            timeout=12,
        )

        parsed = parse_ping_output(result.stdout)
        result_data.update(
            {
                "available": True,
                "internet": result.returncode == 0,
                "ping": parsed["ping"],
                "packet_loss": parsed["packet_loss"],
            }
        )
    except Exception:
        pass

    return result_data


def scan_network():
    adapter = get_active_adapter()
    ping = test_ping()
    dns = test_dns()

    return {
        "adapter": adapter,
        "gateway": get_default_gateway(),
        "dns_servers": get_dns_servers(),
        "dns_available": dns["available"],
        "dns_ok": dns["ok"],
        "ping_test_available": ping["available"],
        "internet": ping["internet"],
        "ping": ping["ping"],
        "packet_loss": ping["packet_loss"],
    }


# =========================================================
# WINDOWS EVENT LOG
# =========================================================

def scan_event_logs():
    command = r"""
    try {
        $start = (Get-Date).AddHours(-24)
        $events = Get-WinEvent -FilterHashtable @{
            LogName=@('System','Application')
            Level=@(1,2,3)
            StartTime=$start
        } -MaxEvents 60 -ErrorAction SilentlyContinue |
        Select-Object TimeCreated, LogName, ProviderName, Id, LevelDisplayName, Message

        [PSCustomObject]@{
            Success = $true
            Events = @($events)
        } | ConvertTo-Json -Depth 5 -Compress
    }
    catch {
        [PSCustomObject]@{
            Success = $false
            Events = @()
        } | ConvertTo-Json -Depth 5 -Compress
    }
    """

    output = run_powershell(command, timeout=15)
    if not output:
        return {"available": False, "events": []}

    try:
        payload = json.loads(output)
        available = bool(payload.get("Success"))
        data = payload.get("Events") or []
        if isinstance(data, dict):
            data = [data]
    except Exception:
        return {"available": False, "events": []}

    events = []
    for item in data:
        if not isinstance(item, dict):
            continue

        message = str(item.get("Message") or "").replace("\r", " ").replace("\n", " ")
        if len(message) > 350:
            message = message[:350] + "..."

        events.append(
            {
                "time": item.get("TimeCreated") or "",
                "log": item.get("LogName") or "Unknown",
                "provider": item.get("ProviderName") or "Unknown",
                "id": safe_int(item.get("Id"), 0),
                "level": item.get("LevelDisplayName") or "Unknown",
                "message": message,
            }
        )

    return {"available": available, "events": events}


def analyze_event_logs(event_scan):
    events = event_scan.get("events", [])
    analysis = {
        "available": bool(event_scan.get("available")),
        "total": len(events),
        "critical": 0,
        "errors": 0,
        "warnings": 0,
        "hardware_errors": 0,
        "storage_errors": 0,
        "shutdown_errors": 0,
        "gpu_errors": 0,
        "app_crashes": 0,
        "generic_errors": 0,
        "ignored_noise": 0,
        "important": [],
    }

    for event in events:
        provider = str(event.get("provider") or "").lower()
        level = str(event.get("level") or "").lower()
        message = str(event.get("message") or "").lower()
        event_id = safe_int(event.get("id"), 0)

        if "critical" in level:
            analysis["critical"] += 1
        elif "error" in level:
            analysis["errors"] += 1
        elif "warning" in level:
            analysis["warnings"] += 1

        # Common Windows noise. These should not heavily influence health scoring.
        if "microsoft-windows-capi2" in provider:
            analysis["ignored_noise"] += 1
            continue

        if "distributedcom" in provider and event_id == 10016:
            analysis["ignored_noise"] += 1
            continue

        # Common Service Control Manager events often describe software/service startup issues,
        # not physical hardware failure. Keep them as generic Windows errors.
        category = None

        if "whea" in provider or (
            "hardware error" in message and ("error" in level or "critical" in level)
        ):
            analysis["hardware_errors"] += 1
            category = "Hardware"

        elif ("kernel-power" in provider and event_id == 41) or event_id == 6008:
            analysis["shutdown_errors"] += 1
            category = "Unexpected Shutdown"

        elif any(token in provider for token in ("nvlddmkm", "amdwddmg", "dxgkrnl")):
            if "error" in level or "critical" in level:
                analysis["gpu_errors"] += 1
                category = "Graphics"

        elif provider == "display" and ("error" in level or "critical" in level):
            analysis["gpu_errors"] += 1
            category = "Graphics"

        elif any(
            token in provider
            for token in ("disk", "ntfs", "storahci", "stornvme", "volmgr", "volsnap")
        ):
            # Storage warnings are common. Only errors/critical events affect score.
            if "error" in level or "critical" in level:
                analysis["storage_errors"] += 1
                category = "Storage"

        elif (event_id == 1000 or "application error" in provider) and (
            "error" in level or "critical" in level
        ):
            analysis["app_crashes"] += 1
            category = "Application Crash"

        elif "error" in level or "critical" in level:
            analysis["generic_errors"] += 1
            category = "Windows"

        if category and len(analysis["important"]) < 8:
            analysis["important"].append({**event, "category": category})

    return analysis


# =========================================================
# COLLECT SYSTEM DATA
# =========================================================

def collect_system_data():
    cpu = scan_cpu()
    memory = scan_memory()
    disks = scan_disks()
    gpu = scan_gpu()
    network = scan_network()
    processes = scan_top_processes(5)
    windows = get_windows_info()
    uptime = get_uptime()
    cpu_model = get_cpu_model()

    return {
        "cpu": cpu,
        "cpu_model": cpu_model,
        "memory": memory,
        "disks": disks,
        "system_drive": find_system_drive(disks),
        "gpu": gpu,
        "network": network,
        "processes": processes,
        "windows": windows,
        "uptime": uptime,
    }


# =========================================================
# DOCTOR - INTERNET
# =========================================================

def doctor_internet(data):
    network = data["network"]
    score = 100
    facts = []
    issues = []
    actions = []

    checks = [
        network["ping_test_available"],
        network["dns_available"],
        network["ping"] is not None,
        network["packet_loss"] is not None,
        network["adapter"]["available"],
    ]
    coverage = coverage_percent(checks)

    if network["ping_test_available"]:
        if network["internet"]:
            facts.append("Internet connection is reachable.")
        else:
            score -= 45
            issues.append("OpenFix could not reach the internet.")
            actions.append("Check the router, Wi-Fi connection or Ethernet cable.")
    else:
        facts.append("Internet reachability test is not available.")

    if network["dns_available"]:
        if network["dns_ok"]:
            facts.append("Website name lookup (DNS) is working.")
        else:
            score -= 20
            issues.append("Website name lookup may not be working correctly.")
            actions.append("Check DNS settings before resetting the whole network.")
    else:
        facts.append("DNS test is not available.")

    ping = network["ping"]
    if ping is None:
        facts.append("Internet response time could not be measured.")
    elif ping < 80:
        facts.append(f"Internet response time looks good: {ping} ms.")
    elif ping < 150:
        score -= 10
        facts.append(f"Internet response time: {ping} ms.")
        issues.append("Network delay is higher than ideal.")
    else:
        score -= 25
        facts.append(f"Internet response time: {ping} ms.")
        issues.append("Network delay is very high.")
        actions.append("Check Wi-Fi quality, downloads and ISP conditions.")

    loss = network["packet_loss"]
    if loss is None:
        facts.append("Packet loss could not be measured.")
    elif loss == 0:
        facts.append("No packet loss was detected.")
    elif loss < 3:
        score -= 3
        facts.append(f"Packet loss: {loss}%.")
    elif loss < 10:
        score -= 15
        issues.append(f"The connection is losing some data packets ({loss}%).")
        actions.append("Check Wi-Fi signal, cable quality and router stability.")
    else:
        score -= 30
        issues.append(f"Heavy packet loss was detected ({loss}%).")
        actions.append("Check the local network connection before changing Windows settings.")

    adapter = network["adapter"]
    if adapter["available"]:
        facts.append(f"Active network adapter: {adapter['name']}.")
        facts.append(f"Adapter connection speed: {adapter['link_speed']}.")
    else:
        facts.append("Active network adapter details are not available.")

    return make_result(
        "Internet Doctor",
        score,
        facts,
        issues,
        actions,
        (
            "Ping means response delay. Packet loss means some network data did not arrive. "
            "This scan is only a short snapshot."
        ),
        coverage=coverage,
    )


# =========================================================
# DOCTOR - GAMING
# =========================================================

def doctor_gaming(data):
    score = 100
    facts = []
    issues = []
    actions = []

    cpu = data["cpu"]
    ram = data["memory"]["percent"]
    gpu = data["gpu"]
    network = data["network"]

    coverage = coverage_percent(
        [
            cpu is not None,
            ram is not None,
            gpu["available"],
            gpu["temperature"] is not None,
            network["ping"] is not None or network["packet_loss"] is not None,
        ]
    )

    if cpu is None:
        facts.append("CPU usage could not be measured.")
    else:
        facts.append(f"CPU usage: {cpu:.0f}%.")
        if cpu >= 95:
            score -= 25
            issues.append("CPU usage is extremely high.")
            actions.append("Check which program is using the most CPU while gaming.")
        elif cpu >= 85:
            score -= 12
            issues.append("CPU usage is high.")

    if ram is None:
        facts.append("RAM usage could not be measured.")
    else:
        facts.append(f"RAM usage: {ram:.0f}%.")
        if ram >= 95:
            score -= 25
            issues.append("RAM usage is extremely high.")
            actions.append("Close unnecessary applications before playing.")
        elif ram >= 85:
            score -= 12
            issues.append("RAM usage is high.")

    if gpu["available"]:
        facts.append(f"Graphics device: {gpu['name']}.")
        if gpu["gpu_count"] > 1:
            facts.append(f"{gpu['gpu_count']} graphics devices were detected.")
    else:
        facts.append("Graphics device information is not available.")

    if gpu["temperature"] is None:
        facts.append("GPU temperature cannot be read on this system.")
    else:
        temperature = gpu["temperature"]
        facts.append(f"GPU temperature: {temperature:.0f}°C.")
        if temperature >= 90:
            score -= 30
            issues.append("GPU temperature is dangerously high.")
            actions.append("Check GPU fans, dust and case airflow.")
        elif temperature >= 83:
            score -= 12
            issues.append("GPU temperature is higher than ideal.")

    ping = network["ping"]
    loss = network["packet_loss"]

    if ping is not None:
        facts.append(f"Network response time: {ping} ms.")
    if loss is not None:
        facts.append(f"Packet loss: {loss}%.")
        if loss >= 3:
            score -= 15
            issues.append("Network instability may cause online-game lag.")
            actions.append("Check the network connection before lowering graphics settings.")

    return make_result(
        "Gaming Doctor",
        score,
        facts,
        issues,
        actions,
        "This scan checks common system conditions. It does not currently measure in-game FPS or frame time.",
        coverage=coverage,
    )


# =========================================================
# DOCTOR - SLOW PC
# =========================================================

def doctor_slow_pc(data):
    score = 100
    facts = []
    issues = []
    actions = []

    cpu = data["cpu"]
    memory = data["memory"]
    ram = memory["percent"]
    system_drive = data["system_drive"]
    processes = data["processes"]

    coverage = coverage_percent(
        [
            cpu is not None,
            ram is not None,
            bool(processes),
            system_drive is not None,
        ]
    )

    if cpu is not None:
        facts.append(f"CPU usage: {cpu:.0f}%.")
        if cpu >= 90:
            score -= 22
            issues.append("CPU usage is very high.")
            actions.append("Check Task Manager for applications using a lot of CPU.")
        elif cpu >= 80:
            score -= 10
            issues.append("CPU usage is currently high.")
    else:
        facts.append("CPU usage is not available.")

    if ram is not None:
        facts.append(f"RAM usage: {ram:.0f}%.")
        if ram >= 95:
            score -= 28
            issues.append("Almost all available RAM is being used.")
        elif ram >= 85:
            score -= 15
            issues.append("RAM usage is high.")
    else:
        facts.append("RAM usage is not available.")

    if processes:
        top = processes[0]
        facts.append(f"Highest RAM usage: {top['name']} ({format_bytes(top['memory'])}).")

        if ram is not None and ram >= 85 and memory["total"]:
            share = top["memory"] / memory["total"]
            if share >= 0.15:
                actions.append(
                    f"Check {top['name']} first because it is using a large share of system RAM."
                )

    if system_drive:
        free_gb = system_drive["free"] / (1024 ** 3)
        free_percent = 100 - system_drive["percent"]
        facts.append(f"Windows drive free space: {free_gb:.1f} GB ({free_percent:.0f}% free).")

        if free_gb < 5 or free_percent < 3:
            score -= 20
            issues.append("The Windows drive is almost full.")
            actions.append("Free some space on the Windows drive.")
    else:
        facts.append("Windows drive information is not available.")

    return make_result(
        "Slow PC Doctor",
        score,
        facts,
        issues,
        actions,
        "CPU and RAM usage can change quickly. For better results, run this scan while the PC feels slow.",
        coverage=coverage,
    )


# =========================================================
# DOCTOR - STORAGE
# =========================================================

def doctor_storage(data):
    score = 100
    facts = []
    issues = []
    actions = []
    disks = data["disks"]

    if not disks:
        return make_result(
            "Storage Doctor",
            100,
            [],
            [],
            ["Try running the scan again if drive information should be available."],
            "Drive information could not be read, so OpenFix did not score storage health.",
            coverage=0,
        )

    for drive in disks:
        free_gb = drive["free"] / (1024 ** 3)
        free_percent = 100 - drive["percent"]
        facts.append(
            f"{drive['device']} has {free_gb:.1f} GB free ({free_percent:.0f}% free)."
        )

        if free_gb < 5 or free_percent < 3:
            score -= 28
            issues.append(f"{drive['device']} is critically low on free space.")
            actions.append(
                f"Free space on {drive['device']} before large updates or installations."
            )
        elif free_gb < 15 or free_percent < 8:
            score -= 12
            issues.append(f"{drive['device']} is getting low on free space.")
            actions.append(f"Consider freeing some space on {drive['device']}.")

    return make_result(
        "Storage Doctor",
        score,
        facts,
        issues,
        actions,
        "This Doctor checks free space. It does not prove whether an SSD or HDD is physically healthy.",
        coverage=100,
    )


# =========================================================
# WINDOWS EVENT DOCTOR
# =========================================================

def create_event_result(event_scan):
    analysis = analyze_event_logs(event_scan)
    score = 100
    facts = []
    issues = []
    actions = []

    if not analysis["available"]:
        return make_result(
            "Windows Event Doctor",
            100,
            ["Windows Event Log data could not be read."],
            [],
            ["Try the scan again if Windows Event Log should be available."],
            "OpenFix did not lower the score because event data was unavailable.",
            coverage=0,
            extra={"event_analysis": analysis},
        )

    facts.extend(
        [
            f"Windows events checked: {analysis['total']}.",
            f"Errors recorded: {analysis['errors']}.",
            f"Warnings recorded: {analysis['warnings']}.",
        ]
    )

    if analysis["ignored_noise"]:
        facts.append(f"Common background events ignored: {analysis['ignored_noise']}.")

    if analysis["hardware_errors"]:
        count = analysis["hardware_errors"]
        score -= min(45, count * 25)
        issues.append(f"Windows recorded {count} possible hardware error event(s).")
        actions.append("Prioritize dedicated hardware diagnostics before changing Windows settings.")

    if analysis["storage_errors"]:
        count = analysis["storage_errors"]
        score -= min(35, count * 15)
        issues.append(f"Windows recorded {count} important storage-related event(s).")
        actions.append("Back up important files and check drive health.")

    if analysis["shutdown_errors"]:
        count = analysis["shutdown_errors"]
        score -= min(30, count * 15)
        issues.append(f"{count} unexpected shutdown event(s) were detected.")
        actions.append("Check recent crashes, temperatures and power stability.")

    if analysis["gpu_errors"]:
        count = analysis["gpu_errors"]
        score -= min(25, count * 10)
        issues.append(f"Windows recorded {count} graphics-related error event(s).")
        actions.append("Check graphics driver stability if display problems or crashes are occurring.")

    if analysis["app_crashes"]:
        count = analysis["app_crashes"]
        score -= min(15, count * 5)
        issues.append(f"{count} application crash event(s) were detected.")
        actions.append("Identify the application that crashed before reinstalling drivers or Windows.")

    if analysis["generic_errors"]:
        score -= min(5, analysis["generic_errors"])
        facts.append(f"Other Windows errors: {analysis['generic_errors']}.")

    if analysis["important"]:
        facts.append("Important recent events:")
        for event in analysis["important"][:5]:
            facts.append(
                f"[{event['category']}] {event['provider']} (Event ID {event['id']})"
            )

    serious_count = (
        analysis["hardware_errors"]
        + analysis["storage_errors"]
        + analysis["shutdown_errors"]
        + analysis["gpu_errors"]
        + analysis["app_crashes"]
    )

    if serious_count == 0:
        facts.append(
            "No major hardware, storage, graphics, shutdown or application-crash event was detected."
        )

    return make_result(
        "Windows Event Doctor",
        score,
        facts,
        issues,
        actions,
        (
            "Event ID is Windows' reference number for an event. Windows can contain harmless warnings "
            "and errors even on healthy PCs."
        ),
        coverage=100,
        extra={"event_analysis": analysis},
    )


def doctor_event_log():
    return create_event_result(scan_event_logs())


# =========================================================
# LOCAL SMART DOCTOR
# =========================================================

def doctor_smart(data, event_analysis):
    score = 100
    facts = []
    issues = []
    recommendations = []

    def add_action(priority, text):
        recommendations.append((priority, text))

    cpu = data["cpu"]
    memory = data["memory"]
    ram = memory["percent"]
    network = data["network"]
    gpu = data["gpu"]
    disks = data["disks"]

    coverage = coverage_percent(
        [
            cpu is not None,
            ram is not None,
            bool(disks),
            network["ping_test_available"],
            gpu["available"],
            event_analysis["available"],
        ]
    )

    high_cpu = cpu is not None and cpu >= 85
    high_ram = ram is not None and ram >= 85
    very_high_ram = ram is not None and ram >= 95
    high_gpu_temp = gpu["temperature"] is not None and gpu["temperature"] >= 83
    critical_gpu_temp = gpu["temperature"] is not None and gpu["temperature"] >= 90
    low_storage = False
    critical_storage = False

    # CPU
    if cpu is not None:
        facts.append(f"CPU usage: {cpu:.0f}%.")
        if cpu >= 95:
            score -= 20
            issues.append("CPU usage is extremely high.")
            add_action(2, "Check which application is using the most CPU.")
        elif cpu >= 85:
            score -= 10
            issues.append("CPU usage is high.")
    else:
        facts.append("CPU usage is not available.")

    # RAM
    if ram is not None:
        facts.append(f"RAM usage: {ram:.0f}%.")
        if ram >= 95:
            score -= 25
            issues.append("RAM usage is extremely high.")
            add_action(2, "Close unnecessary applications and check which program uses the most RAM.")
        elif ram >= 85:
            score -= 12
            issues.append("RAM usage is high.")
    else:
        facts.append("RAM usage is not available.")

    # Top process correlation
    if data["processes"]:
        top = data["processes"][0]
        facts.append(f"Highest RAM usage: {top['name']} ({format_bytes(top['memory'])}).")

        if high_ram and memory["total"]:
            share = top["memory"] / memory["total"]
            if share >= 0.15:
                add_action(
                    1,
                    f"Check {top['name']} first because it is using a large share of system RAM.",
                )

    # GPU
    if gpu["available"]:
        facts.append(f"Main graphics device: {gpu['name']}.")
        if gpu["gpu_count"] > 1:
            facts.append(f"{gpu['gpu_count']} graphics devices were detected.")
    else:
        facts.append("Graphics device information is not available.")

    if gpu["temperature"] is not None:
        temperature = gpu["temperature"]
        facts.append(f"GPU temperature: {temperature:.0f}°C.")

        if temperature >= 90:
            score -= 25
            issues.append("GPU temperature is dangerously high.")
            add_action(0, "Check GPU cooling, fans and case airflow before performance tuning.")
        elif temperature >= 83:
            score -= 10
            issues.append("GPU temperature is higher than ideal.")
            add_action(3, "Check case airflow and GPU cooling.")

    # Storage
    for drive in disks:
        free_gb = drive["free"] / (1024 ** 3)
        free_percent = 100 - drive["percent"]
        facts.append(f"{drive['device']} has {free_gb:.1f} GB free.")

        if free_gb < 5 or free_percent < 3:
            critical_storage = True
            low_storage = True
            score -= 25
            issues.append(f"{drive['device']} is critically low on free space.")
            add_action(1, f"Free space on {drive['device']} before doing other software troubleshooting.")
        elif free_gb < 15 or free_percent < 8:
            low_storage = True
            score -= 10
            issues.append(f"{drive['device']} is getting low on free space.")
            add_action(3, f"Consider freeing space on {drive['device']}.")

    # Network
    if network["ping_test_available"]:
        if network["internet"]:
            facts.append("Internet connection is reachable.")
        else:
            score -= 30
            issues.append("OpenFix could not reach the internet.")
            add_action(1, "Check the router, Wi-Fi or Ethernet connection.")
    else:
        facts.append("Internet reachability test is not available.")

    ping = network["ping"]
    loss = network["packet_loss"]

    if ping is not None:
        facts.append(f"Internet response time: {ping} ms.")
    if loss is not None:
        facts.append(f"Packet loss: {loss}%.")

    if loss is not None and loss >= 3 and ping is not None and ping < 80:
        score -= 18
        issues.append("Internet response speed looks normal, but the connection appears unstable.")
        add_action(2, "Check Wi-Fi signal, Ethernet cable and router stability.")
    elif loss is not None and loss >= 3:
        score -= 18
        issues.append("Packet loss may be causing an unstable connection.")
        add_action(2, "Check the local network connection.")
    elif ping is not None and ping >= 150:
        score -= 15
        issues.append("Internet response time is very high.")
        add_action(3, "Check network traffic, Wi-Fi quality and ISP conditions.")

    # Windows Events
    if event_analysis["available"]:
        if event_analysis["hardware_errors"]:
            score -= 30
            issues.append("Windows recorded possible hardware errors.")
            add_action(0, "Run dedicated hardware diagnostics before changing Windows settings.")

        if event_analysis["storage_errors"]:
            score -= 25
            issues.append("Windows recorded important storage-related errors.")
            add_action(0, "Back up important files and check drive health.")

        if event_analysis["shutdown_errors"]:
            score -= 20
            issues.append("Unexpected shutdowns were recorded.")
            add_action(1, "Check temperatures, power stability and recent crash history.")

        if event_analysis["gpu_errors"]:
            score -= 15
            issues.append("Windows recorded graphics-related errors.")
            add_action(2, "Check graphics driver stability.")

        if event_analysis["app_crashes"]:
            score -= 8
            issues.append("Application crashes were recorded.")
            add_action(4, "Identify which application crashed before reinstalling drivers or Windows.")
    else:
        facts.append("Windows Event Log analysis is not available for this scan.")

    # Correlations: these do not add new penalties, they improve priority/explanation.
    if low_storage and not high_cpu and not high_ram:
        add_action(2, "Storage space is currently a more likely concern than CPU or RAM usage.")

    if high_ram and not high_cpu:
        add_action(2, "Memory pressure is more noticeable than CPU load in this scan.")

    if high_cpu and high_ram:
        add_action(1, "CPU and RAM are both under heavy load, so check active applications before changing drivers or Windows.")

    if event_analysis["available"] and event_analysis["storage_errors"] and critical_storage:
        add_action(0, "Storage errors and very low free space appeared together: back up important files first.")

    if event_analysis["available"] and event_analysis["gpu_errors"] and high_gpu_temp:
        add_action(0, "Graphics errors and high GPU temperature appeared together: check cooling before reinstalling drivers.")

    if event_analysis["available"] and event_analysis["shutdown_errors"] and critical_gpu_temp:
        add_action(0, "Unexpected shutdowns and very high GPU temperature appeared together: check cooling and power stability first.")

    if very_high_ram and data["processes"]:
        top = data["processes"][0]
        add_action(1, f"RAM is nearly full. Review {top['name']} before restarting or changing system settings.")

    # Deduplicate and label priority.
    unique = []
    seen = set()
    for priority, text in sorted(recommendations, key=lambda item: item[0]):
        if text in seen:
            continue
        seen.add(text)
        unique.append((priority, text))

    actions = []
    for index, (priority, text) in enumerate(unique[:7], start=1):
        if index == 1:
            prefix = "Do first"
        elif index <= 3:
            prefix = "Next"
        else:
            prefix = "Then"
        actions.append(f"{prefix}: {text}")

    return make_result(
        "Local Smart Doctor",
        score,
        facts,
        issues,
        actions,
        "Smart Doctor uses built-in local rules. It does not use Cloud AI or an external AI API.",
        coverage=coverage,
    )


# =========================================================
# FULL SYSTEM SCAN
# =========================================================

def doctor_full(data, event_scan):
    event_result = create_event_result(event_scan)
    event_analysis = event_result["event_analysis"]

    internet = doctor_internet(data)
    gaming = doctor_gaming(data)
    slow = doctor_slow_pc(data)
    storage = doctor_storage(data)
    smart = doctor_smart(data, event_analysis)

    areas = [
        (internet, 0.20),
        (gaming, 0.15),
        (slow, 0.15),
        (storage, 0.20),
        (event_result, 0.30),
    ]

    numerator = 0.0
    denominator = 0.0
    for result, base_weight in areas:
        availability = result["coverage"] / 100
        effective_weight = base_weight * availability
        if effective_weight <= 0:
            continue
        numerator += result["score"] * effective_weight
        denominator += effective_weight

    overall_score = round(numerator / denominator) if denominator > 0 else 100

    overall_coverage = round(
        sum(result["coverage"] * weight for result, weight in areas)
        / sum(weight for _, weight in areas)
    )

    facts = [
        f"Internet Doctor: {internet['score']}/100 — coverage {internet['coverage']}%.",
        f"Gaming Doctor: {gaming['score']}/100 — coverage {gaming['coverage']}%.",
        f"Slow PC Doctor: {slow['score']}/100 — coverage {slow['coverage']}%.",
        f"Storage Doctor: {storage['score']}/100 — coverage {storage['coverage']}%.",
        f"Windows Event Doctor: {event_result['score']}/100 — coverage {event_result['coverage']}%.",
        f"Local Smart Doctor: {smart['score']}/100 — coverage {smart['coverage']}%.",
    ]

    issues = list(smart["issues"][:5])
    actions = list(smart["actions"][:6])

    if overall_coverage < 100:
        facts.append(
            f"This was a partial scan: {overall_coverage}% of the planned diagnostic data was available."
        )

    return make_result(
        "Full System Scan",
        overall_score,
        facts,
        issues,
        actions,
        (
            "Overall score uses only diagnostic areas that returned usable data. "
            "Unavailable data does not automatically lower the health score."
        ),
        coverage=overall_coverage,
        extra={
            "dashboard_data": data,
            "event_analysis": event_analysis,
        },
    )


# =========================================================
# WORKER THREAD
# =========================================================

class ScanWorker(QThread):
    finished = Signal(dict)

    def __init__(self, mode):
        super().__init__()
        self.mode = mode

    def run(self):
        try:
            if self.mode == "events":
                self.finished.emit(doctor_event_log())
                return

            data = collect_system_data()

            if self.mode == "internet":
                result = doctor_internet(data)
            elif self.mode == "gaming":
                result = doctor_gaming(data)
            elif self.mode == "slow":
                result = doctor_slow_pc(data)
            elif self.mode == "storage":
                result = doctor_storage(data)
            elif self.mode == "smart":
                event_scan = scan_event_logs()
                analysis = analyze_event_logs(event_scan)
                result = doctor_smart(data, analysis)
            else:
                event_scan = scan_event_logs()
                result = doctor_full(data, event_scan)

            self.finished.emit(result)

        except Exception as error:
            self.finished.emit(
                make_result(
                    "Scan Error",
                    100,
                    [],
                    [],
                    ["Try the scan again. If the problem continues, restart OpenFix and test the same Doctor again."],
                    f"Internal scan error: {error}",
                    coverage=0,
                )
            )


# =========================================================
# UI COMPONENTS
# =========================================================

class NavButton(QPushButton):
    def __init__(self, text):
        super().__init__(text)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(44)


class StatCard(QFrame):
    def __init__(self, title, value="--", subtitle="Waiting for scan"):
        super().__init__()
        self.setObjectName("StatCard")
        self.setProperty("state", "neutral")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 15, 18, 16)
        layout.setSpacing(6)

        top = QHBoxLayout()
        self.title_label = QLabel(title)
        self.title_label.setObjectName("StatTitle")

        self.status_label = QLabel("WAITING")
        self.status_label.setObjectName("StatStatus")
        self.status_label.setProperty("state", "neutral")

        top.addWidget(self.title_label)
        top.addStretch()
        top.addWidget(self.status_label)

        self.value_label = QLabel(value)
        self.value_label.setObjectName("StatValue")
        self.value_label.setWordWrap(True)

        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setObjectName("StatSubtitle")
        self.subtitle_label.setWordWrap(True)

        layout.addLayout(top)
        layout.addWidget(self.value_label)
        layout.addWidget(self.subtitle_label)

    def set_state(self, state, status_text):
        self.setProperty("state", state)
        self.status_label.setProperty("state", state)
        self.status_label.setText(status_text.upper())

        for widget in (self, self.status_label):
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    def set_value(self, value, subtitle, state="neutral", status_text="Info"):
        self.value_label.setText(value)
        self.subtitle_label.setText(subtitle)
        self.set_state(state, status_text)


class InfoValueCard(QFrame):
    def __init__(self, title, value="Not scanned yet"):
        super().__init__()
        self.setObjectName("InfoValueCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(5)

        title_label = QLabel(title)
        title_label.setObjectName("InfoValueTitle")

        self.value_label = QLabel(value)
        self.value_label.setObjectName("InfoValueText")
        self.value_label.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addWidget(self.value_label)

    def set_value(self, value):
        self.value_label.setText(value)


class SectionCard(QFrame):
    def __init__(self, title):
        super().__init__()
        self.setObjectName("SectionCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(8)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("SectionTitle")

        self.text_label = QLabel("")
        self.text_label.setObjectName("SectionText")
        self.text_label.setWordWrap(True)
        self.text_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        layout.addWidget(self.title_label)
        layout.addWidget(self.text_label)

    def set_lines(self, lines, empty_text):
        if not lines:
            self.text_label.setText(empty_text)
            return

        self.text_label.setText("\n".join(f"• {line}" for line in lines))


class SummaryBanner(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("SummaryBanner")
        self.setProperty("state", "neutral")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 17, 20, 17)

        left = QVBoxLayout()
        self.title = QLabel("System Health")
        self.title.setObjectName("SummaryTitle")

        self.text = QLabel("Run a Full System Scan to see your PC health summary.")
        self.text.setObjectName("SummaryText")
        self.text.setWordWrap(True)

        self.coverage = QLabel("SCAN COVERAGE —")
        self.coverage.setObjectName("CoverageText")

        left.addWidget(self.title)
        left.addWidget(self.text)
        left.addWidget(self.coverage)
        layout.addLayout(left, 1)

        self.score = QLabel("--")
        self.score.setObjectName("SummaryScore")
        layout.addWidget(self.score)

    def set_state(self, state):
        self.setProperty("state", state)
        self.style().unpolish(self)
        self.style().polish(self)

    def update_summary(self, result):
        score = result["score"]
        issues = result.get("issues", [])
        coverage = result.get("coverage", 100)

        self.score.setText(str(score))
        self.coverage.setText(f"SCAN COVERAGE {coverage}%")

        if score >= 90:
            state = "good"
            status = "System looks healthy"
        elif score >= 75:
            state = "minor"
            status = "Minor items found"
        elif score >= 50:
            state = "warning"
            status = "Needs attention"
        else:
            state = "danger"
            status = "Important issues found"

        detail = (
            f"{len(issues)} item(s) worth checking."
            if issues
            else "No major problem was detected."
        )

        if coverage < 100:
            detail += " Some diagnostic data was unavailable."

        self.text.setText(f"{status} • {detail}")
        self.set_state(state)


class ResultPanel(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("ResultPanel")

        main = QVBoxLayout(self)
        main.setContentsMargins(22, 22, 22, 22)
        main.setSpacing(16)

        header = QHBoxLayout()
        left = QVBoxLayout()

        self.title = QLabel("No scan yet")
        self.title.setObjectName("ResultTitle")

        self.explanation = QLabel("Start a scan to see the results.")
        self.explanation.setObjectName("ResultExplanation")
        self.explanation.setWordWrap(True)

        self.coverage = QLabel("Scan coverage: --")
        self.coverage.setObjectName("ResultCoverage")

        left.addWidget(self.title)
        left.addWidget(self.explanation)
        left.addWidget(self.coverage)
        header.addLayout(left, 1)

        score_layout = QVBoxLayout()
        caption = QLabel("ESTIMATED SCORE")
        caption.setObjectName("ScoreCaption")

        self.score = QLabel("--")
        self.score.setObjectName("ResultScore")

        self.status = QLabel("Waiting")
        self.status.setObjectName("StatusBadge")
        self.status.setProperty("state", "neutral")

        score_layout.addWidget(caption, alignment=Qt.AlignRight)
        score_layout.addWidget(self.score, alignment=Qt.AlignRight)
        score_layout.addWidget(self.status, alignment=Qt.AlignRight)
        header.addLayout(score_layout)
        main.addLayout(header)

        self.facts_card = SectionCard("What we found")
        self.issues_card = SectionCard("Possible problems")
        self.actions_card = SectionCard("What you should do")

        main.addWidget(self.facts_card)
        main.addWidget(self.issues_card)
        main.addWidget(self.actions_card)

        self.note = QLabel("Measured information and estimated conclusions are shown separately.")
        self.note.setObjectName("ResultNote")
        self.note.setWordWrap(True)
        main.addWidget(self.note)

    def set_status_state(self, state):
        self.status.setProperty("state", state)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

    def set_scanning(self):
        self.title.setText("Scanning...")
        self.explanation.setText("OpenFix is collecting diagnostic information from this PC.")
        self.coverage.setText("Scan coverage: calculating...")
        self.score.setText("--")
        self.status.setText("Scanning")
        self.set_status_state("neutral")

        self.facts_card.set_lines([], "Collecting information...")
        self.issues_card.set_lines([], "Waiting for scan results...")
        self.actions_card.set_lines([], "Recommendations will appear here if needed.")
        self.note.setText("Local diagnostic scan in progress. No Cloud AI or external AI API is being used.")

    def set_result(self, result):
        score = result["score"]
        coverage = result.get("coverage", 100)

        self.title.setText(result["title"])
        self.score.setText(f"{score}/100")
        self.coverage.setText(f"Scan coverage: {coverage}%")

        if coverage == 0:
            self.status.setText("No data")
            self.explanation.setText("This scan could not collect enough information to estimate this area.")
            self.set_status_state("neutral")
        elif score >= 90:
            self.status.setText("Healthy")
            self.explanation.setText("No major problem was detected in the available scan data.")
            self.set_status_state("good")
        elif score >= 75:
            self.status.setText("Minor issues")
            self.explanation.setText("A few items may be worth checking.")
            self.set_status_state("minor")
        elif score >= 50:
            self.status.setText("Needs attention")
            self.explanation.setText("Some diagnostic results may need attention.")
            self.set_status_state("warning")
        else:
            self.status.setText("Important issues")
            self.explanation.setText("OpenFix found items that should be checked carefully.")
            self.set_status_state("danger")

        if 0 < coverage < 100:
            self.explanation.setText(
                self.explanation.text() + " This is a partial scan because some data was unavailable."
            )

        self.facts_card.set_lines(
            result.get("facts", []),
            "No diagnostic facts are available.",
        )
        self.issues_card.set_lines(
            result.get("issues", []),
            "No major problems were found in the available data.",
        )
        self.actions_card.set_lines(
            result.get("actions", []),
            "No immediate action appears necessary.",
        )

        note = result.get("note", "")
        self.note.setText(
            "Important: " + note if note else "This result is diagnostic guidance, not a guarantee."
        )


class PageHeader(QWidget):
    def __init__(self, title, subtitle):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        title_label = QLabel(title)
        title_label.setObjectName("PageTitle")

        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("PageSubtitle")
        subtitle_label.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)


# =========================================================
# MAIN WINDOW
# =========================================================

class OpenFixWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.worker = None
        self.active_result_panel = None
        self.active_progress = None
        self.scan_buttons = []

        self.setWindowTitle(f"OpenFix AI {APP_VERSION}")
        self.resize(1380, 900)
        self.setMinimumSize(1120, 740)

        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)

        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.sidebar = self.build_sidebar()
        root_layout.addWidget(self.sidebar)

        content = QWidget()
        content.setObjectName("Content")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(34, 25, 34, 28)
        content_layout.setSpacing(0)

        content_layout.addWidget(self.build_topbar())

        self.pages = QStackedWidget()
        content_layout.addWidget(self.pages, 1)
        root_layout.addWidget(content, 1)

        self.dashboard_page = self.build_dashboard_page()
        self.smart_page = self.build_doctor_page(
            "Local Smart Doctor",
            "Combines local checks, connects related symptoms and helps decide what should be investigated first.",
            "smart",
        )
        self.internet_page = self.build_doctor_page(
            "Internet Doctor",
            "Checks connection availability, response delay, DNS and connection stability.",
            "internet",
        )
        self.gaming_page = self.build_doctor_page(
            "Gaming Doctor",
            "Checks common CPU, RAM, graphics and network conditions that may affect gaming.",
            "gaming",
        )
        self.slow_page = self.build_doctor_page(
            "Slow PC Doctor",
            "Checks common reasons Windows or applications may feel slow.",
            "slow",
        )
        self.storage_page = self.build_doctor_page(
            "Storage Doctor",
            "Checks available space across your drives.",
            "storage",
        )
        self.event_page = self.build_doctor_page(
            "Windows Event Doctor",
            "Checks recent Windows errors while filtering common background noise.",
            "events",
        )

        for page in (
            self.dashboard_page,
            self.smart_page,
            self.internet_page,
            self.gaming_page,
            self.slow_page,
            self.storage_page,
            self.event_page,
        ):
            self.pages.addWidget(page)

        self.apply_style()
        self.show_page(0, self.dashboard_nav)

    # -----------------------------------------------------
    # SIDEBAR
    # -----------------------------------------------------

    def build_sidebar(self):
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(240)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(18, 24, 18, 20)
        layout.setSpacing(7)

        logo = QLabel("OpenFix AI")
        logo.setObjectName("Logo")

        version = QLabel(APP_VERSION)
        version.setObjectName("SidebarVersion")

        layout.addWidget(logo)
        layout.addWidget(version)
        layout.addSpacing(25)

        section = QLabel("PC DIAGNOSTICS")
        section.setObjectName("SidebarSection")
        layout.addWidget(section)

        self.dashboard_nav = NavButton("⌂   Dashboard")
        self.smart_nav = NavButton("✦   Smart Doctor")
        self.internet_nav = NavButton("◉   Internet")
        self.gaming_nav = NavButton("◆   Gaming")
        self.slow_nav = NavButton("◐   Slow PC")
        self.storage_nav = NavButton("▣   Storage")
        self.event_nav = NavButton("⚠   Windows Events")

        self.nav_buttons = [
            self.dashboard_nav,
            self.smart_nav,
            self.internet_nav,
            self.gaming_nav,
            self.slow_nav,
            self.storage_nav,
            self.event_nav,
        ]

        for button in self.nav_buttons:
            layout.addWidget(button)

        layout.addStretch()

        local_badge = QLabel("●  LOCAL ANALYSIS")
        local_badge.setObjectName("LocalBadge")

        privacy = QLabel("No Cloud AI\nNo external AI API\nRead-only diagnostics")
        privacy.setObjectName("PrivacyText")

        layout.addWidget(local_badge)
        layout.addWidget(privacy)

        connections = [
            (self.dashboard_nav, 0),
            (self.smart_nav, 1),
            (self.internet_nav, 2),
            (self.gaming_nav, 3),
            (self.slow_nav, 4),
            (self.storage_nav, 5),
            (self.event_nav, 6),
        ]

        for button, index in connections:
            button.clicked.connect(
                lambda checked=False, idx=index, btn=button: self.show_page(idx, btn)
            )

        return sidebar

    # -----------------------------------------------------
    # TOP BAR
    # -----------------------------------------------------

    def build_topbar(self):
        wrapper = QWidget()
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 20)

        title = QLabel("PC Health & Diagnostics")
        title.setObjectName("TopTitle")
        layout.addWidget(title)
        layout.addStretch()

        badge = QLabel("MEASURED FACTS + ESTIMATED ANALYSIS")
        badge.setObjectName("FactsBadge")
        layout.addWidget(badge)

        guide = QPushButton("How to Use")
        guide.setObjectName("SecondaryButton")

        terms = QPushButton("Simple Terms")
        terms.setObjectName("SecondaryButton")

        safety = QPushButton("Safety")
        safety.setObjectName("SafetyButton")

        guide.clicked.connect(self.show_guide)
        terms.clicked.connect(self.show_terms)
        safety.clicked.connect(self.show_safety)

        layout.addWidget(guide)
        layout.addWidget(terms)
        layout.addWidget(safety)
        return wrapper

    # -----------------------------------------------------
    # DASHBOARD
    # -----------------------------------------------------

    def build_dashboard_page(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        page = QWidget()
        scroll.setWidget(page)

        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 24)
        layout.setSpacing(18)

        layout.addWidget(
            PageHeader(
                "System Dashboard",
                "A clear overview of your PC. Run a Full System Scan to update the information below.",
            )
        )

        self.summary_banner = SummaryBanner()
        layout.addWidget(self.summary_banner)

        row1 = QHBoxLayout()
        row1.setSpacing(14)
        self.cpu_card = StatCard("CPU")
        self.ram_card = StatCard("RAM")
        self.storage_card = StatCard("Windows Drive")
        row1.addWidget(self.cpu_card)
        row1.addWidget(self.ram_card)
        row1.addWidget(self.storage_card)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(14)
        self.network_card = StatCard("Internet")
        self.gpu_card = StatCard("Graphics")
        self.events_card = StatCard("Windows Events")
        row2.addWidget(self.network_card)
        row2.addWidget(self.gpu_card)
        row2.addWidget(self.events_card)
        layout.addLayout(row2)

        system_title = QLabel("System Information")
        system_title.setObjectName("DashboardSectionTitle")
        layout.addWidget(system_title)

        info_row1 = QHBoxLayout()
        info_row1.setSpacing(12)
        self.cpu_model_card = InfoValueCard("Processor")
        self.total_ram_card = InfoValueCard("Installed RAM")
        self.windows_card = InfoValueCard("Windows")
        info_row1.addWidget(self.cpu_model_card)
        info_row1.addWidget(self.total_ram_card)
        info_row1.addWidget(self.windows_card)
        layout.addLayout(info_row1)

        info_row2 = QHBoxLayout()
        info_row2.setSpacing(12)
        self.gpu_info_card = InfoValueCard("Graphics Device")
        self.uptime_card = InfoValueCard("PC Uptime")
        self.adapter_card = InfoValueCard("Network Adapter")
        info_row2.addWidget(self.gpu_info_card)
        info_row2.addWidget(self.uptime_card)
        info_row2.addWidget(self.adapter_card)
        layout.addLayout(info_row2)

        top_title = QLabel("Top RAM Usage")
        top_title.setObjectName("DashboardSectionTitle")
        layout.addWidget(top_title)

        self.process_card = SectionCard("Applications using the most RAM")
        self.process_card.set_lines([], "Run a Full System Scan to see the top applications.")
        layout.addWidget(self.process_card)

        hero = QFrame()
        hero.setObjectName("HeroCard")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(24, 22, 24, 22)

        left = QVBoxLayout()
        hero_title = QLabel("Full System Scan")
        hero_title.setObjectName("HeroTitle")
        hero_text = QLabel(
            "Checks the main diagnostic areas together and creates one system health overview."
        )
        hero_text.setObjectName("HeroText")
        hero_text.setWordWrap(True)
        left.addWidget(hero_title)
        left.addWidget(hero_text)
        hero_layout.addLayout(left, 1)

        self.full_scan_btn = QPushButton("Start Full Scan")
        self.full_scan_btn.setObjectName("PrimaryButton")
        self.full_scan_btn.setCursor(Qt.PointingHandCursor)
        self.full_scan_btn.clicked.connect(
            lambda: self.start_scan(
                "full",
                self.dashboard_result,
                self.dashboard_progress,
            )
        )
        self.scan_buttons.append(self.full_scan_btn)
        hero_layout.addWidget(self.full_scan_btn)
        layout.addWidget(hero)

        self.dashboard_progress = QProgressBar()
        self.dashboard_progress.setRange(0, 0)
        self.dashboard_progress.hide()
        layout.addWidget(self.dashboard_progress)

        self.dashboard_result = ResultPanel()
        layout.addWidget(self.dashboard_result)
        layout.addStretch()
        return scroll

    # -----------------------------------------------------
    # DOCTOR PAGE
    # -----------------------------------------------------

    def build_doctor_page(self, title, subtitle, mode):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        page = QWidget()
        scroll.setWidget(page)

        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 24)
        layout.setSpacing(18)
        layout.addWidget(PageHeader(title, subtitle))

        action_card = QFrame()
        action_card.setObjectName("ActionCard")
        action_layout = QHBoxLayout(action_card)
        action_layout.setContentsMargins(22, 20, 22, 20)

        info = QVBoxLayout()
        ready = QLabel("Ready to scan")
        ready.setObjectName("ActionTitle")
        description = QLabel(
            "This diagnostic scan is read-only and will not automatically change Windows settings."
        )
        description.setObjectName("ActionText")
        description.setWordWrap(True)
        info.addWidget(ready)
        info.addWidget(description)
        action_layout.addLayout(info, 1)

        button = QPushButton("Run Scan")
        button.setObjectName("PrimaryButton")
        button.setCursor(Qt.PointingHandCursor)
        action_layout.addWidget(button)
        self.scan_buttons.append(button)
        layout.addWidget(action_card)

        progress = QProgressBar()
        progress.setRange(0, 0)
        progress.hide()
        layout.addWidget(progress)

        result = ResultPanel()
        layout.addWidget(result)
        layout.addStretch()

        button.clicked.connect(lambda: self.start_scan(mode, result, progress))
        return scroll

    # -----------------------------------------------------
    # NAVIGATION / SCAN CONTROL
    # -----------------------------------------------------

    def show_page(self, index, active_button):
        self.pages.setCurrentIndex(index)
        for button in self.nav_buttons:
            button.setChecked(button == active_button)

    def set_all_scan_buttons(self, enabled):
        for button in self.scan_buttons:
            button.setEnabled(enabled)

    def start_scan(self, mode, result_panel, progress):
        if self.worker is not None and self.worker.isRunning():
            QMessageBox.information(
                self,
                "Scan already running",
                "OpenFix is already running a scan.\n\nPlease wait for the current scan to finish.",
            )
            return

        self.active_result_panel = result_panel
        self.active_progress = progress
        result_panel.set_scanning()
        progress.show()
        self.set_all_scan_buttons(False)

        self.worker = ScanWorker(mode)
        self.worker.finished.connect(self.scan_complete)
        self.worker.start()

    def scan_complete(self, result):
        if self.active_progress:
            self.active_progress.hide()

        self.set_all_scan_buttons(True)

        if self.active_result_panel:
            self.active_result_panel.set_result(result)

        if "dashboard_data" in result:
            self.update_dashboard(
                result["dashboard_data"],
                result.get("event_analysis", {}),
            )
            self.summary_banner.update_summary(result)

    # -----------------------------------------------------
    # DASHBOARD UPDATE
    # -----------------------------------------------------

    def update_dashboard(self, data, event_analysis):
        cpu = data["cpu"]
        if cpu is None:
            self.cpu_card.set_value("N/A", "Usage unavailable", "neutral", "Unavailable")
        elif cpu < 80:
            self.cpu_card.set_value(f"{cpu:.0f}%", "Normal usage", "good", "Good")
        elif cpu < 90:
            self.cpu_card.set_value(f"{cpu:.0f}%", "Higher usage", "minor", "High")
        else:
            self.cpu_card.set_value(f"{cpu:.0f}%", "Very high usage", "danger", "Very high")

        memory = data["memory"]
        ram = memory["percent"]
        if ram is None:
            self.ram_card.set_value("N/A", "Usage unavailable", "neutral", "Unavailable")
        elif ram < 80:
            self.ram_card.set_value(f"{ram:.0f}%", "Normal usage", "good", "Good")
        elif ram < 90:
            self.ram_card.set_value(f"{ram:.0f}%", "High usage", "minor", "High")
        else:
            self.ram_card.set_value(f"{ram:.0f}%", "Very high usage", "danger", "Very high")

        drive = data["system_drive"]
        if drive:
            free_gb = drive["free"] / (1024 ** 3)
            free_percent = 100 - drive["percent"]

            if free_gb < 5 or free_percent < 3:
                state, label = "danger", "Critical"
            elif free_gb < 15 or free_percent < 8:
                state, label = "warning", "Low"
            else:
                state, label = "good", "Good"

            self.storage_card.set_value(
                f"{free_gb:.0f} GB",
                f"{drive['device']} free space • {free_percent:.0f}% free",
                state,
                label,
            )
        else:
            self.storage_card.set_value("N/A", "Drive information unavailable", "neutral", "Unavailable")

        network = data["network"]
        if not network["ping_test_available"]:
            self.network_card.set_value("N/A", "Connectivity test unavailable", "neutral", "Unavailable")
        elif not network["internet"]:
            self.network_card.set_value("Offline", "Internet connection not confirmed", "danger", "Problem")
        else:
            ping = network["ping"]
            loss = network["packet_loss"]
            value = f"{ping} ms" if ping is not None else "Online"

            if loss is not None and loss >= 3:
                state, label = "warning", "Unstable"
                subtitle = f"{loss}% packet loss"
            elif ping is not None and ping >= 150:
                state, label = "warning", "Slow response"
                subtitle = f"{loss or 0}% packet loss"
            else:
                state, label = "good", "Good"
                subtitle = f"{loss or 0}% packet loss"

            self.network_card.set_value(value, subtitle, state, label)

        gpu = data["gpu"]
        if gpu["available"]:
            name = gpu["name"]
            if len(name) > 30:
                name = name[:27] + "..."

            if gpu["temperature"] is None:
                state, label = "neutral", "Temp N/A"
                subtitle = "Temperature unavailable"
            elif gpu["temperature"] >= 90:
                state, label = "danger", "Hot"
                subtitle = f"{gpu['temperature']:.0f}°C"
            elif gpu["temperature"] >= 83:
                state, label = "warning", "Warm"
                subtitle = f"{gpu['temperature']:.0f}°C"
            else:
                state, label = "good", "Good"
                subtitle = f"{gpu['temperature']:.0f}°C"

            self.gpu_card.set_value(name, subtitle, state, label)
        else:
            self.gpu_card.set_value("N/A", "GPU information unavailable", "neutral", "Unavailable")

        if not event_analysis.get("available", False):
            self.events_card.set_value("N/A", "Event Log unavailable", "neutral", "Unavailable")
        else:
            serious_events = (
                event_analysis.get("hardware_errors", 0)
                + event_analysis.get("storage_errors", 0)
                + event_analysis.get("shutdown_errors", 0)
                + event_analysis.get("gpu_errors", 0)
            )

            if serious_events == 0:
                self.events_card.set_value("Good", "No major system event detected", "good", "Good")
            elif serious_events <= 2:
                self.events_card.set_value(str(serious_events), "Important event(s) detected", "warning", "Check")
            else:
                self.events_card.set_value(str(serious_events), "Several important events detected", "danger", "Attention")

        self.cpu_model_card.set_value(data["cpu_model"])
        self.total_ram_card.set_value(format_bytes(memory["total"]) if memory["total"] else "Not available")

        windows = data["windows"]
        if windows["available"]:
            self.windows_card.set_value(f"{windows['name']} • Build {windows['build']}")
        else:
            self.windows_card.set_value("Not available")

        self.gpu_info_card.set_value(gpu["name"] if gpu["available"] else "Not available")
        self.uptime_card.set_value(data["uptime"]["text"])

        adapter = network["adapter"]
        self.adapter_card.set_value(adapter["name"] if adapter["available"] else "Not available")

        process_lines = []
        for index, process in enumerate(data["processes"][:3], start=1):
            process_lines.append(
                f"{index}. {process['name']} — {format_bytes(process['memory'])}"
            )

        self.process_card.set_lines(process_lines, "Process information is not available.")

    # -----------------------------------------------------
    # HELP
    # -----------------------------------------------------

    def show_guide(self):
        QMessageBox.information(
            self,
            "How to Use OpenFix AI",
            (
                "Start with Full System Scan for a general overview.\n\n"
                "WHAT WE FOUND\n"
                "Information OpenFix read or measured from your PC.\n\n"
                "POSSIBLE PROBLEMS\n"
                "OpenFix's interpretation of those measurements.\n\n"
                "WHAT YOU SHOULD DO\n"
                "Suggested next steps, ordered so the most useful action appears first.\n\n"
                "SCAN COVERAGE\n"
                "Shows how much of the planned diagnostic information was available. "
                "A partial scan is not automatically a bad-health result."
            ),
        )

    def show_terms(self):
        QMessageBox.information(
            self,
            "Simple Terms",
            (
                "PING / RESPONSE TIME\n"
                "How long data takes to travel to another computer and back. Lower is usually better.\n\n"
                "PACKET LOSS\n"
                "Network data that did not reach its destination. Packet loss can cause lag or unstable calls/games.\n\n"
                "DNS\n"
                "The system that converts website names into network addresses.\n\n"
                "EVENT ID\n"
                "A reference number Windows gives to a recorded system event.\n\n"
                "SCAN COVERAGE\n"
                "How much of the planned diagnostic data OpenFix was able to read.\n\n"
                "CPU\n"
                "The main processor that performs calculations.\n\n"
                "RAM\n"
                "Fast temporary memory used by Windows and running applications.\n\n"
                "UPTIME\n"
                "How long the PC has been running since the last full boot."
            ),
        )

    def show_safety(self):
        QMessageBox.warning(
            self,
            "Safety & Privacy",
            (
                "OpenFix AI currently performs read-only diagnostics.\n\n"
                "• No Cloud AI is used.\n"
                "• No external AI API is used.\n"
                "• Smart analysis runs locally.\n"
                "• OpenFix does not automatically edit the Registry.\n"
                "• OpenFix does not automatically remove drivers.\n"
                "• OpenFix does not automatically disable Windows services.\n\n"
                "Internet Doctor performs normal connectivity tests such as DNS lookup and ping. "
                "These are not AI services or AI APIs.\n\n"
                "A low score does not prove hardware is broken, and a high score does not guarantee that no problem exists."
            ),
        )

    # -----------------------------------------------------
    # STYLE
    # -----------------------------------------------------

    def apply_style(self):
        self.setStyleSheet(
            """
            * {
                font-family: "Segoe UI";
            }

            #Root, #Content {
                background: #0b0e13;
            }

            QScrollArea {
                background: transparent;
                border: none;
            }

            QScrollArea > QWidget > QWidget {
                background: transparent;
            }

            #Sidebar {
                background: #12161c;
                border-right: 1px solid #232a34;
            }

            #Logo {
                color: #ffffff;
                font-size: 25px;
                font-weight: 800;
            }

            #SidebarVersion {
                color: #697482;
                font-size: 11px;
            }

            #SidebarSection {
                color: #626d7b;
                font-size: 10px;
                font-weight: 700;
            }

            NavButton {
                background: transparent;
                color: #99a4b3;
                border: none;
                border-radius: 9px;
                text-align: left;
                padding-left: 13px;
                font-size: 13px;
                font-weight: 600;
                outline: none;
            }

            NavButton:hover {
                background: #1a1f27;
                color: #ffffff;
            }

            NavButton:checked {
                background: #1d2938;
                color: #8bb6ff;
            }

            #LocalBadge {
                color: #67dca3;
                background: #14261f;
                border: 1px solid #214735;
                border-radius: 8px;
                padding: 8px 10px;
                font-size: 10px;
                font-weight: 800;
            }

            #PrivacyText {
                color: #66717f;
                font-size: 10px;
                padding-top: 4px;
            }

            #TopTitle {
                color: #c7ced8;
                font-size: 13px;
                font-weight: 600;
            }

            #FactsBadge {
                color: #8793a2;
                background: #161a20;
                border: 1px solid #282f39;
                border-radius: 8px;
                padding: 7px 10px;
                font-size: 9px;
                font-weight: 700;
            }

            #PageTitle {
                color: #ffffff;
                font-size: 30px;
                font-weight: 800;
            }

            #PageSubtitle {
                color: #858f9d;
                font-size: 14px;
            }

            #DashboardSectionTitle {
                color: #e8ebef;
                font-size: 16px;
                font-weight: 750;
                padding-top: 4px;
            }

            #SecondaryButton {
                background: #181d24;
                color: #d3d9e1;
                border: 1px solid #2b323c;
                border-radius: 8px;
                padding: 9px 13px;
                font-weight: 600;
            }

            #SecondaryButton:hover {
                background: #222832;
            }

            #SafetyButton {
                background: #2b2114;
                color: #e7bc76;
                border: 1px solid #513b1e;
                border-radius: 8px;
                padding: 9px 13px;
                font-weight: 600;
            }

            #SummaryBanner {
                background: #141b24;
                border: 1px solid #263a53;
                border-radius: 14px;
            }

            #SummaryBanner[state="good"] {
                border: 1px solid #24543f;
            }

            #SummaryBanner[state="minor"] {
                border: 1px solid #5a4d25;
            }

            #SummaryBanner[state="warning"] {
                border: 1px solid #6a4224;
            }

            #SummaryBanner[state="danger"] {
                border: 1px solid #6d2d34;
            }

            #SummaryTitle {
                color: #ffffff;
                font-size: 16px;
                font-weight: 750;
            }

            #SummaryText {
                color: #8fa0b5;
                font-size: 12px;
            }

            #CoverageText {
                color: #667484;
                font-size: 9px;
                font-weight: 700;
            }

            #SummaryScore {
                color: #8cb8ff;
                font-size: 36px;
                font-weight: 850;
            }

            #StatCard {
                background: #151920;
                border: 1px solid #252c36;
                border-radius: 14px;
                min-height: 122px;
            }

            #StatCard[state="good"] {
                border: 1px solid #224836;
            }

            #StatCard[state="minor"] {
                border: 1px solid #514624;
            }

            #StatCard[state="warning"] {
                border: 1px solid #614021;
            }

            #StatCard[state="danger"] {
                border: 1px solid #652b32;
            }

            #StatTitle {
                color: #76818f;
                font-size: 11px;
                font-weight: 700;
            }

            #StatValue {
                color: #ffffff;
                font-size: 24px;
                font-weight: 800;
            }

            #StatSubtitle {
                color: #707b89;
                font-size: 11px;
            }

            #StatStatus {
                color: #8793a2;
                background: #1d232c;
                border-radius: 6px;
                padding: 4px 7px;
                font-size: 8px;
                font-weight: 800;
            }

            #StatStatus[state="good"] {
                color: #6fe0a5;
                background: #153025;
            }

            #StatStatus[state="minor"] {
                color: #e1c76d;
                background: #302a18;
            }

            #StatStatus[state="warning"] {
                color: #f0a35d;
                background: #382516;
            }

            #StatStatus[state="danger"] {
                color: #ff8080;
                background: #351b1f;
            }

            #InfoValueCard {
                background: #12161c;
                border: 1px solid #222933;
                border-radius: 11px;
                min-height: 82px;
            }

            #InfoValueTitle {
                color: #727d8a;
                font-size: 10px;
                font-weight: 700;
            }

            #InfoValueText {
                color: #dce2ea;
                font-size: 12px;
                font-weight: 600;
            }

            #HeroCard {
                background: #161b23;
                border: 1px solid #29364c;
                border-radius: 15px;
            }

            #HeroTitle {
                color: #ffffff;
                font-size: 19px;
                font-weight: 750;
            }

            #HeroText {
                color: #818c9b;
                font-size: 13px;
            }

            #PrimaryButton {
                background: #367df6;
                color: #ffffff;
                border: none;
                border-radius: 9px;
                padding: 11px 18px;
                font-size: 13px;
                font-weight: 700;
                min-width: 110px;
                outline: none;
            }

            #PrimaryButton:hover {
                background: #4a8aff;
            }

            #PrimaryButton:disabled {
                background: #26354b;
                color: #748398;
            }

            #ActionCard {
                background: #151920;
                border: 1px solid #252c36;
                border-radius: 14px;
            }

            #ActionTitle {
                color: #ffffff;
                font-size: 16px;
                font-weight: 700;
            }

            #ActionText {
                color: #7f8998;
                font-size: 12px;
            }

            #ResultPanel {
                background: #12161c;
                border: 1px solid #272e38;
                border-radius: 16px;
            }

            #ResultTitle {
                color: #ffffff;
                font-size: 21px;
                font-weight: 800;
            }

            #ResultExplanation {
                color: #84909f;
                font-size: 12px;
            }

            #ResultCoverage {
                color: #697685;
                font-size: 10px;
                font-weight: 650;
            }

            #ScoreCaption {
                color: #687381;
                font-size: 9px;
                font-weight: 800;
            }

            #ResultScore {
                color: #ffffff;
                font-size: 37px;
                font-weight: 850;
            }

            #StatusBadge {
                color: #adb7c5;
                background: #202630;
                border-radius: 7px;
                padding: 5px 9px;
                font-size: 10px;
                font-weight: 800;
            }

            #StatusBadge[state="good"] {
                color: #70e1a6;
                background: #153025;
            }

            #StatusBadge[state="minor"] {
                color: #e5ca72;
                background: #302a18;
            }

            #StatusBadge[state="warning"] {
                color: #f0a35d;
                background: #382516;
            }

            #StatusBadge[state="danger"] {
                color: #ff8080;
                background: #351b1f;
            }

            #SectionCard {
                background: #171b22;
                border: 1px solid #242b34;
                border-radius: 12px;
            }

            #SectionTitle {
                color: #e0e5ed;
                font-size: 13px;
                font-weight: 750;
            }

            #SectionText {
                color: #a5afbc;
                font-size: 12px;
            }

            #ResultNote {
                color: #727d8b;
                font-size: 10px;
            }

            QProgressBar {
                background: #191e25;
                border: none;
                border-radius: 4px;
                height: 7px;
            }

            QProgressBar::chunk {
                background: #397ff6;
                border-radius: 4px;
            }

            QMessageBox {
                background: #f5f5f5;
            }

            QMessageBox QLabel {
                color: #151515;
                min-width: 520px;
            }
            """
        )


# =========================================================
# START
# =========================================================

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = OpenFixWindow()
    window.show()
    sys.exit(app.exec())
