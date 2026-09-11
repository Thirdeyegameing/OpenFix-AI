import sys
import os
import re
import json
import socket
import platform
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
    QGridLayout,
    QLabel,
    QPushButton,
    QFrame,
    QProgressBar,
    QScrollArea,
    QStackedWidget,
    QDialog,
)


APP_VERSION = "0.5.2-dev7"


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

        return {
            "ok": result.returncode == 0,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }

    except Exception as error:
        return {
            "ok": False,
            "stdout": "",
            "stderr": str(error),
        }


def make_result(
    title,
    score,
    facts=None,
    issues=None,
    actions=None,
    note="",
    coverage=None,
    extra=None,
):
    result = {
        "title": title,
        "score": clamp(int(score)),
        "facts": facts or [],
        "issues": issues or [],
        "actions": actions or [],
        "note": note,
        "coverage": coverage,
        "scan_time": datetime.now().strftime("%H:%M:%S"),
    }

    if extra:
        result.update(extra)

    return result


def format_prioritized_actions(items, limit=7):
    if not items:
        return []

    unique = []
    seen = set()

    for priority, text in sorted(
        items,
        key=lambda item: item[0],
    ):
        if text in seen:
            continue

        seen.add(text)
        unique.append((priority, text))

    formatted = []

    for index, (priority, text) in enumerate(
        unique[:limit]
    ):
        if index == 0:
            prefix = "Do first"
        elif priority <= 2:
            prefix = "Next"
        else:
            prefix = "Later"

        formatted.append(
            f"{prefix}: {text}"
        )

    return formatted


# =========================================================
# SYSTEM INFORMATION
# =========================================================

def get_cpu_model():
    result = run_powershell(
        r"""
        Get-CimInstance Win32_Processor |
        Select-Object -First 1 -ExpandProperty Name
        """,
        timeout=8,
    )

    if result["ok"] and result["stdout"]:
        return result["stdout"].strip()

    processor = platform.processor()

    return processor or "Not available"


def get_windows_info():
    result = run_powershell(
        r"""
        Get-CimInstance Win32_OperatingSystem |
        Select-Object Caption, Version, BuildNumber |
        ConvertTo-Json -Compress
        """,
        timeout=8,
    )

    if result["ok"] and result["stdout"]:
        try:
            data = json.loads(
                result["stdout"]
            )

            return {
                "caption": (
                    data.get("Caption")
                    or "Microsoft Windows"
                ),
                "version": (
                    data.get("Version")
                    or "Unknown"
                ),
                "build": (
                    data.get("BuildNumber")
                    or "Unknown"
                ),
            }

        except Exception:
            pass

    return {
        "caption": "Microsoft Windows",
        "version": platform.version(),
        "build": "Unknown",
    }


def get_uptime():
    try:
        seconds = (
            datetime.now().timestamp()
            - psutil.boot_time()
        )

        return {
            "seconds": seconds,
            "text": format_uptime(seconds),
        }

    except Exception:
        return {
            "seconds": None,
            "text": "Not available",
        }


# =========================================================
# CPU / MEMORY / STORAGE
# =========================================================

def scan_cpu():
    try:
        return psutil.cpu_percent(
            interval=1
        )

    except Exception:
        return None


def scan_memory():
    try:
        memory = psutil.virtual_memory()

        return {
            "available": True,
            "percent": memory.percent,
            "used": memory.used,
            "total": memory.total,
            "free": memory.available,
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
        partitions = psutil.disk_partitions(
            all=False
        )

    except Exception:
        partitions = []

    for partition in partitions:
        device = partition.device

        if not device:
            continue

        if device in seen:
            continue

        seen.add(device)

        try:
            usage = psutil.disk_usage(
                partition.mountpoint
            )

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
    system_drive = (
        os.environ.get(
            "SystemDrive",
            "C:",
        )
        .upper()
        .rstrip("\\")
    )

    for drive in disks:
        device = (
            str(
                drive.get(
                    "device",
                    "",
                )
            )
            .upper()
            .rstrip("\\")
        )

        if device.startswith(
            system_drive
        ):
            return drive

    if disks:
        return disks[0]

    return None


# =========================================================
# PROCESSES
# =========================================================

def scan_top_processes(limit=5):
    processes = []

    try:
        for process in psutil.process_iter(
            [
                "pid",
                "name",
                "memory_info",
            ]
        ):
            try:
                info = process.info

                memory_info = info.get(
                    "memory_info"
                )

                memory = (
                    memory_info.rss
                    if memory_info
                    else 0
                )

                processes.append(
                    {
                        "name": (
                            info.get("name")
                            or "Unknown"
                        ),
                        "pid": (
                            info.get("pid")
                            or 0
                        ),
                        "memory": memory,
                    }
                )

            except Exception:
                pass

    except Exception:
        pass

    processes.sort(
        key=lambda item: item["memory"],
        reverse=True,
    )

    return processes[:limit]


# =========================================================
# GPU
# =========================================================

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

    result = run_powershell(
        r"""
        Get-CimInstance Win32_VideoController |
        Select-Object Name, AdapterRAM, DriverVersion |
        ConvertTo-Json -Compress
        """,
        timeout=10,
    )

    controllers = []

    if result["ok"] and result["stdout"]:
        try:
            data = json.loads(
                result["stdout"]
            )

            if isinstance(
                data,
                dict,
            ):
                data = [data]

            for item in data:
                name = (
                    item.get("Name")
                    or "Unknown GPU"
                )

                controllers.append(
                    {
                        "name": name,
                        "vram": (
                            safe_int(
                                item.get(
                                    "AdapterRAM"
                                )
                            )
                            or None
                        ),
                        "driver": (
                            item.get(
                                "DriverVersion"
                            )
                            or "Unknown"
                        ),
                        "basic": (
                            "microsoft basic"
                            in name.lower()
                        ),
                    }
                )

        except Exception:
            controllers = []

    real = [
        gpu_item
        for gpu_item in controllers
        if not gpu_item["basic"]
    ]

    if not real:
        real = controllers

    if real:
        preferred = max(
            real,
            key=lambda item:
            item["vram"] or 0,
        )

        gpu["available"] = True
        gpu["name"] = preferred["name"]
        gpu["vram"] = preferred["vram"]
        gpu["driver"] = preferred["driver"]
        gpu["gpu_count"] = len(real)
        gpu["all_gpus"] = [
            item["name"]
            for item in real
        ]
        gpu["source"] = "Windows"

    # NVIDIA enhanced data
    try:
        creationflags = 0

        if os.name == "nt":
            creationflags = subprocess.CREATE_NO_WINDOW

        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu="
                "name,"
                "memory.total,"
                "utilization.gpu,"
                "temperature.gpu,"
                "driver_version",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            creationflags=creationflags,
            timeout=5,
        )

        if (
            result.returncode == 0
            and result.stdout.strip()
        ):
            cards = []

            for line in result.stdout.splitlines():
                parts = [
                    part.strip()
                    for part in line.split(",")
                ]

                if len(parts) < 5:
                    continue

                cards.append(
                    {
                        "name": parts[0],
                        "vram": (
                            safe_float(
                                parts[1],
                                0,
                            )
                            * 1024
                            * 1024
                        ),
                        "usage": safe_float(
                            parts[2]
                        ),
                        "temperature": safe_float(
                            parts[3]
                        ),
                        "driver": parts[4],
                    }
                )

            if cards:
                preferred = max(
                    cards,
                    key=lambda item:
                    item["vram"] or 0,
                )

                gpu["available"] = True
                gpu["name"] = preferred["name"]
                gpu["vram"] = preferred["vram"]
                gpu["usage"] = preferred["usage"]
                gpu["temperature"] = (
                    preferred[
                        "temperature"
                    ]
                )
                gpu["driver"] = preferred["driver"]
                gpu["gpu_count"] = len(cards)
                gpu["all_gpus"] = [
                    item["name"]
                    for item in cards
                ]
                gpu["source"] = "NVIDIA"

    except Exception:
        pass

    return gpu


# =========================================================
# NETWORK
# =========================================================

def get_active_adapter():
    result = run_powershell(
        r"""
        $route =
        Get-NetRoute `
            -DestinationPrefix "0.0.0.0/0" `
            -ErrorAction SilentlyContinue |
        Where-Object {
            $_.NextHop -ne "0.0.0.0"
        } |
        Sort-Object RouteMetric |
        Select-Object -First 1

        if ($route) {
            Get-NetAdapter `
                -InterfaceIndex $route.InterfaceIndex `
                -ErrorAction SilentlyContinue |
            Select-Object `
                Name,
                InterfaceDescription,
                LinkSpeed,
                MacAddress,
                ifIndex |
            ConvertTo-Json -Compress
        }
        """,
        timeout=10,
    )

    adapter = {
        "available": False,
        "name": "Not available",
        "description": "Not available",
        "link_speed": "Not available",
        "mac": "Not available",
        "interface_index": None,
    }

    if result["ok"] and result["stdout"]:
        try:
            data = json.loads(
                result["stdout"]
            )

            adapter["available"] = True
            adapter["name"] = (
                data.get("Name")
                or "Not available"
            )
            adapter["description"] = (
                data.get(
                    "InterfaceDescription"
                )
                or "Not available"
            )
            adapter["link_speed"] = (
                data.get("LinkSpeed")
                or "Not available"
            )
            adapter["mac"] = (
                data.get("MacAddress")
                or "Not available"
            )
            adapter["interface_index"] = (
                data.get("ifIndex")
            )

        except Exception:
            pass

    return adapter


def get_default_gateway():
    result = run_powershell(
        r"""
        Get-NetRoute `
            -DestinationPrefix "0.0.0.0/0" `
            -ErrorAction SilentlyContinue |
        Where-Object {
            $_.NextHop -ne "0.0.0.0"
        } |
        Sort-Object RouteMetric |
        Select-Object -First 1 `
            -ExpandProperty NextHop
        """,
        timeout=10,
    )

    if result["ok"] and result["stdout"]:
        return result["stdout"]

    return "Not available"


def get_dns_servers():
    result = run_powershell(
        r"""
        Get-DnsClientServerAddress `
            -AddressFamily IPv4 `
            -ErrorAction SilentlyContinue |
        Where-Object {
            $_.ServerAddresses.Count -gt 0
        } |
        Select-Object `
            -ExpandProperty ServerAddresses |
        Select-Object -Unique
        """,
        timeout=10,
    )

    if not result["ok"]:
        return []

    return [
        line.strip()
        for line in result[
            "stdout"
        ].splitlines()
        if line.strip()
    ]


def test_dns():
    try:
        socket.gethostbyname(
            "cloudflare.com"
        )

        return True

    except Exception:
        return False


def parse_ping_output(output):
    result = {
        "ping": None,
        "packet_loss": None,
    }

    times = re.findall(
        r"(?:time|เวลา)\s*[=<]\s*(\d+)\s*ms",
        output,
        flags=re.IGNORECASE,
    )

    values = [
        safe_int(item)
        for item in times
    ]

    if values:
        result["ping"] = round(
            sum(values)
            / len(values)
        )

    elif re.search(
        r"(?:time|เวลา)\s*<\s*1\s*ms",
        output,
        flags=re.IGNORECASE,
    ):
        result["ping"] = 1

    patterns = [
        r"(\d{1,3})%\s*loss",
        r"lost\s*=\s*\d+\s*\((\d{1,3})%",
        r"สูญหาย\s*=\s*\d+\s*\((\d{1,3})%",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            output,
            flags=re.IGNORECASE,
        )

        if match:
            value = safe_int(
                match.group(1)
            )

            if 0 <= value <= 100:
                result[
                    "packet_loss"
                ] = value
                break

    if result[
        "packet_loss"
    ] is None:
        percentages = re.findall(
            r"(\d{1,3})\s*%",
            output,
        )

        percentages = [
            safe_int(item)
            for item in percentages
        ]

        percentages = [
            value
            for value in percentages
            if 0 <= value <= 100
        ]

        if percentages:
            result[
                "packet_loss"
            ] = percentages[-1]

    return result


def test_ping():
    output = {
        "internet": False,
        "ping": None,
        "packet_loss": None,
    }

    try:
        creationflags = 0

        if os.name == "nt":
            creationflags = subprocess.CREATE_NO_WINDOW

        process = subprocess.run(
            [
                "ping",
                "-n",
                "4",
                "-w",
                "2000",
                "1.1.1.1",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            creationflags=creationflags,
            timeout=12,
        )

        parsed = parse_ping_output(
            process.stdout
        )

        output["internet"] = (
            process.returncode == 0
        )
        output["ping"] = parsed["ping"]
        output["packet_loss"] = (
            parsed["packet_loss"]
        )

    except Exception:
        pass

    return output


def scan_network():
    ping = test_ping()

    return {
        "adapter": get_active_adapter(),
        "gateway": get_default_gateway(),
        "dns_servers": get_dns_servers(),
        "dns_ok": test_dns(),
        "internet": ping["internet"],
        "ping": ping["ping"],
        "packet_loss": ping["packet_loss"],
    }


# =========================================================
# EVENT LOG
# =========================================================

def scan_event_logs():
    result = run_powershell(
        r"""
        try {
            $start = (Get-Date).AddHours(-24)

            $events =
            Get-WinEvent `
                -FilterHashtable @{
                    LogName=@(
                        'System',
                        'Application'
                    )
                    Level=@(1,2,3)
                    StartTime=$start
                } `
                -MaxEvents 60 `
                -ErrorAction SilentlyContinue |
            Select-Object `
                TimeCreated,
                LogName,
                ProviderName,
                Id,
                LevelDisplayName,
                Message

            [PSCustomObject]@{
                Success = $true
                Events = @($events)
            } |
            ConvertTo-Json `
                -Depth 5 `
                -Compress
        }
        catch {
            [PSCustomObject]@{
                Success = $false
                Events = @()
            } |
            ConvertTo-Json `
                -Depth 5 `
                -Compress
        }
        """,
        timeout=15,
    )

    package = {
        "available": False,
        "events": [],
    }

    if not result["stdout"]:
        return package

    try:
        data = json.loads(
            result["stdout"]
        )

        package[
            "available"
        ] = bool(
            data.get("Success")
        )

        raw_events = (
            data.get("Events")
            or []
        )

        if isinstance(
            raw_events,
            dict,
        ):
            raw_events = [
                raw_events
            ]

        events = []

        for item in raw_events:
            if not isinstance(
                item,
                dict,
            ):
                continue

            message = str(
                item.get("Message")
                or ""
            )

            message = (
                message
                .replace("\r", " ")
                .replace("\n", " ")
            )

            if len(message) > 350:
                message = (
                    message[:350]
                    + "..."
                )

            events.append(
                {
                    "provider": (
                        item.get(
                            "ProviderName"
                        )
                        or "Unknown"
                    ),
                    "id": safe_int(
                        item.get("Id")
                    ),
                    "level": (
                        item.get(
                            "LevelDisplayName"
                        )
                        or "Unknown"
                    ),
                    "message": message,
                }
            )

        package["events"] = events

    except Exception:
        pass

    return package


def analyze_event_logs(package):
    events = package[
        "events"
    ]

    analysis = {
        "available": package[
            "available"
        ],
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
        provider = str(
            event.get(
                "provider"
            )
            or ""
        ).lower()

        level = str(
            event.get(
                "level"
            )
            or ""
        ).lower()

        message = str(
            event.get(
                "message"
            )
            or ""
        ).lower()

        event_id = safe_int(
            event.get("id")
        )

        if "critical" in level:
            analysis[
                "critical"
            ] += 1
        elif "error" in level:
            analysis[
                "errors"
            ] += 1
        elif "warning" in level:
            analysis[
                "warnings"
            ] += 1

        if (
            "microsoft-windows-capi2"
            in provider
        ):
            analysis[
                "ignored_noise"
            ] += 1
            continue

        if (
            "distributedcom"
            in provider
            and event_id == 10016
        ):
            analysis[
                "ignored_noise"
            ] += 1
            continue

        category = None

        if (
            "whea"
            in provider
            or (
                "hardware error"
                in message
                and (
                    "error" in level
                    or "critical"
                    in level
                )
            )
        ):
            analysis[
                "hardware_errors"
            ] += 1
            category = "Hardware"

        elif (
            (
                "kernel-power"
                in provider
                and event_id == 41
            )
            or event_id == 6008
        ):
            analysis[
                "shutdown_errors"
            ] += 1
            category = "Unexpected Shutdown"

        elif any(
            token in provider
            for token in (
                "nvlddmkm",
                "amdwddmg",
                "dxgkrnl",
            )
        ) and (
            "error" in level
            or "critical" in level
        ):
            analysis[
                "gpu_errors"
            ] += 1
            category = "Graphics"

        elif (
            provider == "display"
            and (
                "error" in level
                or "critical" in level
            )
        ):
            analysis[
                "gpu_errors"
            ] += 1
            category = "Graphics"

        elif any(
            token in provider
            for token in (
                "disk",
                "ntfs",
                "storahci",
                "stornvme",
                "volmgr",
                "volsnap",
            )
        ) and (
            "error" in level
            or "critical" in level
        ):
            analysis[
                "storage_errors"
            ] += 1
            category = "Storage"

        elif (
            event_id == 1000
            or "application error"
            in provider
        ) and (
            "error" in level
            or "critical" in level
        ):
            analysis[
                "app_crashes"
            ] += 1
            category = "Application Crash"

        elif (
            "error" in level
            or "critical" in level
        ):
            analysis[
                "generic_errors"
            ] += 1
            category = "Windows"

        if (
            category
            and len(
                analysis["important"]
            ) < 8
        ):
            analysis[
                "important"
            ].append(
                {
                    **event,
                    "category": category,
                }
            )

    return analysis


# =========================================================
# COLLECT DATA
# =========================================================

def collect_system_data():
    disks = scan_disks()

    return {
        "cpu": scan_cpu(),
        "cpu_model": get_cpu_model(),
        "memory": scan_memory(),
        "disks": disks,
        "system_drive": (
            find_system_drive(
                disks
            )
        ),
        "processes": (
            scan_top_processes(5)
        ),
        "gpu": scan_gpu(),
        "network": scan_network(),
        "windows": get_windows_info(),
        "uptime": get_uptime(),
    }


def calculate_coverage(
    data,
    event_analysis=None,
):
    checks = []

    checks.append(
        data["cpu"] is not None
    )

    checks.append(
        data[
            "memory"
        ]["available"]
    )

    checks.append(
        data[
            "system_drive"
        ] is not None
    )

    checks.append(
        data[
            "network"
        ]["adapter"][
            "available"
        ]
        or data[
            "network"
        ]["internet"]
    )

    checks.append(
        data["gpu"][
            "available"
        ]
    )

    checks.append(
        bool(
            data["processes"]
        )
    )

    if event_analysis is not None:
        checks.append(
            event_analysis[
                "available"
            ]
        )

    available = sum(
        1
        for value in checks
        if value
    )

    if not checks:
        return 0

    return round(
        available
        / len(checks)
        * 100
    )


# =========================================================
# DOCTORS
# =========================================================

def doctor_internet(data):
    network = data["network"]

    score = 100
    facts = []
    issues = []
    actions = []

    if network["internet"]:
        facts.append(
            "Internet connection is reachable."
        )
    else:
        score -= 45
        issues.append(
            "OpenFix could not reach the internet."
        )
        actions.append(
            "Check the router, Wi-Fi connection or Ethernet cable."
        )

    if network["dns_ok"]:
        facts.append(
            "Website name lookup (DNS) is working."
        )
    else:
        score -= 20
        issues.append(
            "Website name lookup may not be working correctly."
        )

    ping = network["ping"]

    if ping is None:
        facts.append(
            "Response time could not be measured."
        )
    elif ping < 80:
        facts.append(
            f"Internet response time looks good: {ping} ms."
        )
    elif ping < 150:
        score -= 10
        issues.append(
            f"Network delay is higher than ideal ({ping} ms)."
        )
    else:
        score -= 25
        issues.append(
            f"Network delay is very high ({ping} ms)."
        )

    loss = network[
        "packet_loss"
    ]

    if loss is None:
        facts.append(
            "Packet loss could not be measured."
        )
    elif loss == 0:
        facts.append(
            "No packet loss was detected."
        )
    elif loss < 3:
        score -= 3
        facts.append(
            f"Packet loss: {loss}%."
        )
    elif loss < 10:
        score -= 15
        issues.append(
            f"Some network data is being lost ({loss}%)."
        )
    else:
        score -= 30
        issues.append(
            f"Heavy packet loss was detected ({loss}%)."
        )

    adapter = network[
        "adapter"
    ]

    if adapter["available"]:
        facts.append(
            f"Active adapter: {adapter['name']}."
        )
        facts.append(
            f"Adapter speed: {adapter['link_speed']}."
        )

    coverage_checks = [
        network["internet"],
        network["dns_ok"],
        ping is not None,
        loss is not None,
        adapter["available"],
    ]

    coverage = round(
        sum(
            1
            for item in coverage_checks
            if item
        )
        / len(coverage_checks)
        * 100
    )

    return make_result(
        "Internet Doctor",
        score,
        facts,
        issues,
        actions,
        (
            "Ping measures response delay. "
            "Packet loss measures network data that did not arrive."
        ),
        coverage=coverage,
    )


def doctor_gaming(data):
    score = 100
    facts = []
    issues = []
    actions = []

    cpu = data["cpu"]
    ram = data[
        "memory"
    ]["percent"]

    gpu = data["gpu"]
    network = data["network"]

    if cpu is not None:
        facts.append(
            f"CPU usage: {cpu:.0f}%."
        )

        if cpu >= 95:
            score -= 25
            issues.append(
                "CPU usage is extremely high."
            )
        elif cpu >= 85:
            score -= 12
            issues.append(
                "CPU usage is high."
            )

    if ram is not None:
        facts.append(
            f"RAM usage: {ram:.0f}%."
        )

        if ram >= 95:
            score -= 25
            issues.append(
                "RAM usage is extremely high."
            )
        elif ram >= 85:
            score -= 12
            issues.append(
                "RAM usage is high."
            )

    if gpu["available"]:
        facts.append(
            f"Graphics device: {gpu['name']}."
        )

    if gpu[
        "temperature"
    ] is not None:
        temperature = gpu[
            "temperature"
        ]

        facts.append(
            f"GPU temperature: {temperature:.0f}°C."
        )

        if temperature >= 90:
            score -= 30
            issues.append(
                "GPU temperature is dangerously high."
            )
            actions.append(
                "Check GPU cooling, fans and case airflow."
            )
        elif temperature >= 83:
            score -= 12
            issues.append(
                "GPU temperature is higher than ideal."
            )
    else:
        facts.append(
            "GPU temperature sensor data is not available."
        )

    if (
        network["packet_loss"]
        is not None
        and network["packet_loss"] >= 3
    ):
        score -= 15
        issues.append(
            "Network instability may cause online-game lag."
        )

    coverage = calculate_coverage(
        data
    )

    return make_result(
        "Gaming Doctor",
        score,
        facts,
        issues,
        actions,
        (
            "This scan checks common system conditions. "
            "It does not currently measure in-game FPS or frame time."
        ),
        coverage=coverage,
    )


def doctor_slow_pc(data):
    score = 100
    facts = []
    issues = []
    actions = []

    cpu = data["cpu"]
    memory = data["memory"]
    ram = memory["percent"]

    if cpu is not None:
        facts.append(
            f"CPU usage: {cpu:.0f}%."
        )

        if cpu >= 90:
            score -= 22
            issues.append(
                "CPU usage is very high."
            )
        elif cpu >= 80:
            score -= 10
            issues.append(
                "CPU usage is currently high."
            )

    if ram is not None:
        facts.append(
            f"RAM usage: {ram:.0f}%."
        )

        if ram >= 95:
            score -= 28
            issues.append(
                "Almost all available RAM is being used."
            )
        elif ram >= 85:
            score -= 15
            issues.append(
                "RAM usage is high."
            )

    if data["processes"]:
        top = data[
            "processes"
        ][0]

        facts.append(
            "Highest RAM usage: "
            f"{top['name']} "
            f"({format_bytes(top['memory'])})."
        )

    drive = data[
        "system_drive"
    ]

    if drive:
        free_gb = (
            drive["free"]
            / (1024 ** 3)
        )

        facts.append(
            f"Windows drive free space: {free_gb:.1f} GB."
        )

        if free_gb < 5:
            score -= 20
            issues.append(
                "The Windows drive is almost full."
            )

    return make_result(
        "Slow PC Doctor",
        score,
        facts,
        issues,
        actions,
        (
            "Run this Doctor while the PC actually feels slow for more useful results."
        ),
        coverage=calculate_coverage(
            data
        ),
    )


def doctor_storage(data):
    disks = data["disks"]

    if not disks:
        return make_result(
            "Storage Doctor",
            80,
            [],
            [],
            [],
            (
                "Drive information could not be read. "
                "No storage-health conclusion was made."
            ),
            coverage=0,
        )

    score = 100
    facts = []
    issues = []
    actions = []

    for drive in disks:
        free_gb = (
            drive["free"]
            / (1024 ** 3)
        )

        free_percent = (
            100
            - drive["percent"]
        )

        facts.append(
            f"{drive['device']} has "
            f"{free_gb:.1f} GB free "
            f"({free_percent:.0f}% free)."
        )

        if (
            free_gb < 5
            or free_percent < 3
        ):
            score -= 28
            issues.append(
                f"{drive['device']} is critically low on free space."
            )
            actions.append(
                f"Free space on {drive['device']}."
            )

        elif (
            free_gb < 15
            or free_percent < 8
        ):
            score -= 12
            issues.append(
                f"{drive['device']} is getting low on free space."
            )

    return make_result(
        "Storage Doctor",
        score,
        facts,
        issues,
        actions,
        (
            "This checks available space only. "
            "It does not prove whether an SSD or HDD is physically healthy."
        ),
        coverage=100,
    )


def create_event_result(
    package
):
    analysis = analyze_event_logs(
        package
    )

    if not analysis[
        "available"
    ]:
        return make_result(
            "Windows Event Doctor",
            100,
            [],
            [],
            [],
            (
                "Windows Event data could not be read. "
                "The score was not reduced because missing data is not a fault."
            ),
            coverage=0,
            extra={
                "event_analysis": analysis,
            },
        )

    score = 100
    facts = [
        f"Windows events checked: {analysis['total']}.",
        f"Errors recorded: {analysis['errors']}.",
        f"Warnings recorded: {analysis['warnings']}.",
    ]
    issues = []
    actions = []

    if analysis[
        "ignored_noise"
    ]:
        facts.append(
            f"Common background events ignored: {analysis['ignored_noise']}."
        )

    if analysis[
        "hardware_errors"
    ]:
        count = analysis[
            "hardware_errors"
        ]

        score -= min(
            45,
            count * 25,
        )

        issues.append(
            f"{count} possible hardware error event(s) were recorded."
        )
        actions.append(
            "Use dedicated hardware diagnostics before changing Windows settings."
        )

    if analysis[
        "storage_errors"
    ]:
        count = analysis[
            "storage_errors"
        ]

        score -= min(
            35,
            count * 15,
        )

        issues.append(
            f"{count} important storage-related event(s) were recorded."
        )
        actions.append(
            "Back up important files and check drive health."
        )

    if analysis[
        "shutdown_errors"
    ]:
        count = analysis[
            "shutdown_errors"
        ]

        score -= min(
            30,
            count * 15,
        )

        issues.append(
            f"{count} unexpected shutdown event(s) were detected."
        )

    if analysis[
        "gpu_errors"
    ]:
        count = analysis[
            "gpu_errors"
        ]

        score -= min(
            25,
            count * 10,
        )

        issues.append(
            f"{count} graphics-related error event(s) were detected."
        )

    if analysis[
        "app_crashes"
    ]:
        count = analysis[
            "app_crashes"
        ]

        score -= min(
            15,
            count * 5,
        )

        issues.append(
            f"{count} application crash event(s) were detected."
        )

    if analysis[
        "generic_errors"
    ]:
        score -= min(
            5,
            analysis[
                "generic_errors"
            ],
        )

        facts.append(
            f"Other Windows errors: {analysis['generic_errors']}."
        )

    if analysis[
        "important"
    ]:
        facts.append(
            "Important recent events:"
        )

        for event in analysis[
            "important"
        ][:5]:
            facts.append(
                f"[{event['category']}] "
                f"{event['provider']} "
                f"(Event ID {event['id']})"
            )

    return make_result(
        "Windows Event Doctor",
        score,
        facts,
        issues,
        actions,
        (
            "Windows can contain harmless warnings and errors even when the PC is working normally."
        ),
        coverage=100,
        extra={
            "event_analysis": analysis,
        },
    )


# =========================================================
# SMART DOCTOR
# =========================================================

def doctor_smart(
    data,
    event_analysis,
):
    score = 100

    facts = []
    issues = []
    recommended = []

    def action(
        priority,
        text,
    ):
        recommended.append(
            (
                priority,
                text,
            )
        )

    cpu = data["cpu"]
    memory = data["memory"]
    ram = memory["percent"]
    gpu = data["gpu"]
    network = data["network"]

    # CPU
    if cpu is not None:
        facts.append(
            f"CPU usage: {cpu:.0f}%."
        )

        if cpu >= 95:
            score -= 20
            issues.append(
                "CPU usage is extremely high."
            )
            action(
                2,
                "Check which application is using the most CPU.",
            )

        elif cpu >= 85:
            score -= 10
            issues.append(
                "CPU usage is high."
            )

    # RAM / process correlation
    if ram is not None:
        facts.append(
            f"RAM usage: {ram:.0f}%."
        )

        if ram >= 95:
            score -= 25
            issues.append(
                "RAM usage is extremely high."
            )

        elif ram >= 85:
            score -= 12
            issues.append(
                "RAM usage is high."
            )

    if (
        data["processes"]
        and memory["total"]
    ):
        top = data[
            "processes"
        ][0]

        percent = (
            top["memory"]
            / memory["total"]
            * 100
        )

        facts.append(
            f"Highest RAM usage: "
            f"{top['name']} — "
            f"{format_bytes(top['memory'])} "
            f"({percent:.1f}% of installed RAM)."
        )

        if (
            ram is not None
            and ram >= 85
            and percent >= 15
        ):
            action(
                0,
                f"Check {top['name']} first because it is using a large share of RAM.",
            )

    # Storage
    low_storage = False
    critical_storage = False

    for drive in data[
        "disks"
    ]:
        free_gb = (
            drive["free"]
            / (1024 ** 3)
        )

        free_percent = (
            100
            - drive["percent"]
        )

        if (
            free_gb < 5
            or free_percent < 3
        ):
            low_storage = True
            critical_storage = True

            score -= 25

            issues.append(
                f"{drive['device']} is critically low on free space."
            )

        elif (
            free_gb < 15
            or free_percent < 8
        ):
            low_storage = True

            score -= 10

            issues.append(
                f"{drive['device']} is getting low on free space."
            )

    # Network correlation
    ping = network[
        "ping"
    ]

    loss = network[
        "packet_loss"
    ]

    if ping is not None:
        facts.append(
            f"Internet response time: {ping} ms."
        )

    if loss is not None:
        facts.append(
            f"Packet loss: {loss}%."
        )

    if (
        loss is not None
        and loss >= 3
        and ping is not None
        and ping < 80
    ):
        score -= 18

        issues.append(
            "Internet response speed is good, but the connection appears unstable."
        )

        action(
            1,
            "Check Wi-Fi signal, Ethernet cable and router stability.",
        )

    elif (
        loss is not None
        and loss >= 3
    ):
        score -= 18

        issues.append(
            "Packet loss may be causing an unstable internet connection."
        )

    elif (
        ping is not None
        and ping >= 150
    ):
        score -= 15

        issues.append(
            "Internet response time is very high."
        )

    # GPU
    hot_gpu = False

    if gpu[
        "temperature"
    ] is not None:
        temperature = gpu[
            "temperature"
        ]

        facts.append(
            f"GPU temperature: {temperature:.0f}°C."
        )

        if temperature >= 90:
            hot_gpu = True

            score -= 25

            issues.append(
                "GPU temperature is dangerously high."
            )

            action(
                0,
                "Check GPU cooling, fans and case airflow.",
            )

        elif temperature >= 83:
            hot_gpu = True

            score -= 10

            issues.append(
                "GPU temperature is higher than ideal."
            )

    # Events
    storage_event = (
        event_analysis[
            "storage_errors"
        ] > 0
    )

    gpu_event = (
        event_analysis[
            "gpu_errors"
        ] > 0
    )

    if event_analysis[
        "hardware_errors"
    ]:
        score -= 30

        issues.append(
            "Windows recorded possible hardware errors."
        )

        action(
            0,
            "Run dedicated hardware diagnostics before changing Windows settings.",
        )

    if storage_event:
        score -= 25

        issues.append(
            "Windows recorded important storage-related errors."
        )

        if low_storage:
            action(
                0,
                "Back up important files first because storage errors and low free space were detected together.",
            )
        else:
            action(
                0,
                "Back up important files and check drive health.",
            )

    if event_analysis[
        "shutdown_errors"
    ]:
        score -= 20

        issues.append(
            "Unexpected shutdowns were recorded."
        )

        action(
            1,
            "Check temperatures, power stability and recent crash history.",
        )

    if gpu_event:
        score -= 15

        issues.append(
            "Windows recorded graphics-related errors."
        )

        if hot_gpu:
            action(
                0,
                "Check GPU cooling first because graphics errors and high temperature were detected together.",
            )
        else:
            action(
                2,
                "Check graphics driver stability.",
            )

    if event_analysis[
        "app_crashes"
    ]:
        score -= 8

        issues.append(
            "Application crashes were recorded."
        )

        action(
            4,
            "Identify which application crashed before reinstalling drivers or Windows.",
        )

    if (
        low_storage
        and cpu is not None
        and cpu < 70
        and ram is not None
        and ram < 80
    ):
        action(
            2,
            "Storage space is currently a more likely concern than CPU or RAM usage.",
        )

    if (
        critical_storage
        and not storage_event
    ):
        action(
            1,
            "Free space on the nearly-full drive.",
        )

    actions = format_prioritized_actions(
        recommended
    )

    coverage = calculate_coverage(
        data,
        event_analysis,
    )

    return make_result(
        "Local Smart Doctor",
        score,
        facts,
        issues,
        actions,
        (
            "Smart Doctor uses built-in local diagnostic rules. "
            "No Cloud AI or external AI API is used."
        ),
        coverage=coverage,
    )


# =========================================================
# FULL SCAN
# =========================================================

def doctor_full(
    data,
    event_package,
):
    event_result = (
        create_event_result(
            event_package
        )
    )

    event_analysis = (
        event_result[
            "event_analysis"
        ]
    )

    internet = doctor_internet(
        data
    )
    gaming = doctor_gaming(
        data
    )
    slow = doctor_slow_pc(
        data
    )
    storage = doctor_storage(
        data
    )
    smart = doctor_smart(
        data,
        event_analysis,
    )

    independent = [
        (
            internet["score"],
            0.20,
            internet["coverage"],
        ),
        (
            gaming["score"],
            0.15,
            gaming["coverage"],
        ),
        (
            slow["score"],
            0.15,
            slow["coverage"],
        ),
        (
            storage["score"],
            0.20,
            storage["coverage"],
        ),
        (
            event_result["score"],
            0.30,
            event_result["coverage"],
        ),
    ]

    weighted_total = 0
    weight_total = 0

    for score, weight, coverage in independent:
        if (
            coverage is not None
            and coverage > 0
        ):
            weighted_total += (
                score * weight
            )
            weight_total += weight

    if weight_total > 0:
        overall = round(
            weighted_total
            / weight_total
        )
    else:
        overall = 100

    coverage = calculate_coverage(
        data,
        event_analysis,
    )

    doctor_scores = {
        "Internet": internet["score"],
        "Gaming": gaming["score"],
        "Slow PC": slow["score"],
        "Storage": storage["score"],
        "Windows Events": event_result["score"],
    }

    healthy = sum(
        1
        for score in doctor_scores.values()
        if score >= 90
    )

    attention = sum(
        1
        for score in doctor_scores.values()
        if score < 90
    )

    facts = [
        f"Internet Doctor: {internet['score']}/100.",
        f"Gaming Doctor: {gaming['score']}/100.",
        f"Slow PC Doctor: {slow['score']}/100.",
        f"Storage Doctor: {storage['score']}/100.",
        f"Windows Event Doctor: {event_result['score']}/100.",
        f"Local Smart Doctor: {smart['score']}/100.",
        f"Scan coverage: {coverage}%.",
    ]

    return make_result(
        "Full System Scan",
        overall,
        facts,
        smart["issues"][:5],
        smart["actions"][:6],
        (
            "The overall score uses independent diagnostic areas. "
            "Missing information is not treated as a hardware fault."
        ),
        coverage=coverage,
        extra={
            "dashboard_data": data,
            "event_analysis": event_analysis,
            "healthy_areas": healthy,
            "attention_areas": attention,
            "smart_score": smart["score"],
        },
    )


# =========================================================
# WORKER
# =========================================================

class ScanWorker(QThread):

    finished = Signal(dict)

    def __init__(
        self,
        mode,
    ):
        super().__init__()

        self.mode = mode

    def run(self):
        try:
            if self.mode == "events":
                package = (
                    scan_event_logs()
                )

                self.finished.emit(
                    create_event_result(
                        package
                    )
                )
                return

            data = (
                collect_system_data()
            )

            if self.mode == "internet":
                result = (
                    doctor_internet(
                        data
                    )
                )

            elif self.mode == "gaming":
                result = (
                    doctor_gaming(
                        data
                    )
                )

            elif self.mode == "slow":
                result = (
                    doctor_slow_pc(
                        data
                    )
                )

            elif self.mode == "storage":
                result = (
                    doctor_storage(
                        data
                    )
                )

            elif self.mode == "smart":
                package = (
                    scan_event_logs()
                )

                analysis = (
                    analyze_event_logs(
                        package
                    )
                )

                result = (
                    doctor_smart(
                        data,
                        analysis,
                    )
                )

            else:
                package = (
                    scan_event_logs()
                )

                result = (
                    doctor_full(
                        data,
                        package,
                    )
                )

            self.finished.emit(
                result
            )

        except Exception as error:
            self.finished.emit(
                make_result(
                    "Scan Error",
                    100,
                    [],
                    [],
                    [],
                    (
                        "The scan could not finish normally. "
                        f"Internal error: {error}"
                    ),
                    coverage=0,
                )
            )


# =========================================================
# MODERN DIALOG
# =========================================================

class ModernDialog(QDialog):

    def __init__(
        self,
        parent,
        title,
        subtitle,
        sections,
        warning=False,
    ):
        super().__init__(
            parent
        )

        self.setModal(
            True
        )

        self.resize(
            720,
            600,
        )

        self.setMinimumSize(
            620,
            480,
        )

        self.setWindowTitle(
            title
        )

        root = QVBoxLayout(
            self
        )

        root.setContentsMargins(
            24,
            22,
            24,
            22,
        )

        root.setSpacing(
            16
        )

        top = QHBoxLayout()

        title_box = QVBoxLayout()

        heading = QLabel(
            title
        )
        heading.setObjectName(
            "DialogTitle"
        )

        description = QLabel(
            subtitle
        )
        description.setObjectName(
            "DialogSubtitle"
        )
        description.setWordWrap(
            True
        )

        title_box.addWidget(
            heading
        )
        title_box.addWidget(
            description
        )

        top.addLayout(
            title_box,
            1,
        )

        close_x = QPushButton(
            "×"
        )
        close_x.setObjectName(
            "DialogCloseX"
        )
        close_x.setFixedSize(
            36,
            36,
        )
        close_x.clicked.connect(
            self.accept
        )

        top.addWidget(
            close_x
        )

        root.addLayout(
            top
        )

        scroll = QScrollArea()
        scroll.setWidgetResizable(
            True
        )
        scroll.setFrameShape(
            QFrame.NoFrame
        )

        container = QWidget()
        content = QVBoxLayout(
            container
        )
        content.setContentsMargins(
            0,
            0,
            6,
            0,
        )
        content.setSpacing(
            10
        )

        for section_title, text in sections:
            card = QFrame()

            card.setObjectName(
                (
                    "DialogWarningCard"
                    if warning
                    else "DialogCard"
                )
            )

            card_layout = QVBoxLayout(
                card
            )
            card_layout.setContentsMargins(
                16,
                14,
                16,
                14,
            )

            card_title = QLabel(
                section_title
            )
            card_title.setObjectName(
                "DialogCardTitle"
            )

            card_text = QLabel(
                text
            )
            card_text.setObjectName(
                "DialogCardText"
            )
            card_text.setWordWrap(
                True
            )

            card_layout.addWidget(
                card_title
            )
            card_layout.addWidget(
                card_text
            )

            content.addWidget(
                card
            )

        content.addStretch()

        scroll.setWidget(
            container
        )

        root.addWidget(
            scroll,
            1,
        )

        footer = QHBoxLayout()
        footer.addStretch()

        close_button = QPushButton(
            "Close"
        )
        close_button.setObjectName(
            "DialogCloseButton"
        )
        close_button.setMinimumWidth(
            110
        )
        close_button.clicked.connect(
            self.accept
        )

        footer.addWidget(
            close_button
        )

        root.addLayout(
            footer
        )


# =========================================================
# COLLAPSIBLE SECTION
# =========================================================

class CollapsibleSection(QFrame):

    def __init__(
        self,
        title,
        subtitle,
        expanded=False,
    ):
        super().__init__()

        self.setObjectName(
            "CollapsibleSection"
        )

        self.expanded = expanded

        root = QVBoxLayout(
            self
        )
        root.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        root.setSpacing(
            0
        )

        header = QFrame()
        header.setObjectName(
            "CollapsibleHeader"
        )

        header_layout = QHBoxLayout(
            header
        )
        header_layout.setContentsMargins(
            16,
            13,
            12,
            13,
        )

        labels = QVBoxLayout()
        labels.setSpacing(
            2
        )

        self.title_label = QLabel(
            title
        )
        self.title_label.setObjectName(
            "CollapsibleTitle"
        )

        self.subtitle_label = QLabel(
            subtitle
        )
        self.subtitle_label.setObjectName(
            "CollapsibleSubtitle"
        )

        labels.addWidget(
            self.title_label
        )
        labels.addWidget(
            self.subtitle_label
        )

        header_layout.addLayout(
            labels,
            1,
        )

        self.toggle_button = QPushButton()
        self.toggle_button.setObjectName(
            "CollapseToggle"
        )
        self.toggle_button.setFixedSize(
            38,
            38,
        )
        self.toggle_button.setCursor(
            Qt.PointingHandCursor
        )

        self.toggle_button.clicked.connect(
            self.toggle
        )

        header_layout.addWidget(
            self.toggle_button
        )

        root.addWidget(
            header
        )

        self.content_frame = QFrame()
        self.content_frame.setObjectName(
            "CollapsibleContent"
        )

        self.content_layout = QVBoxLayout(
            self.content_frame
        )
        self.content_layout.setContentsMargins(
            14,
            14,
            14,
            14,
        )

        root.addWidget(
            self.content_frame
        )

        self.set_expanded(
            expanded
        )


    def add_widget(
        self,
        widget,
    ):
        self.content_layout.addWidget(
            widget
        )


    def add_layout(
        self,
        layout,
    ):
        self.content_layout.addLayout(
            layout
        )


    def toggle(self):
        self.set_expanded(
            not self.expanded
        )


    def set_expanded(
        self,
        expanded,
    ):
        self.expanded = expanded

        self.content_frame.setVisible(
            expanded
        )

        if expanded:
            self.toggle_button.setText(
                "−"
            )
            self.toggle_button.setToolTip(
                "Collapse section"
            )
        else:
            self.toggle_button.setText(
                "+"
            )
            self.toggle_button.setToolTip(
                "Expand section"
            )


# =========================================================
# UI CARDS
# =========================================================

class NavButton(QPushButton):

    def __init__(
        self,
        text,
    ):
        super().__init__(
            text
        )

        self.setCheckable(
            True
        )
        self.setCursor(
            Qt.PointingHandCursor
        )
        self.setMinimumHeight(
            44
        )


class StatCard(QFrame):

    def __init__(
        self,
        title,
    ):
        super().__init__()

        self.setObjectName(
            "StatCard"
        )

        self.state = "neutral"

        root = QVBoxLayout(
            self
        )
        root.setContentsMargins(
            18,
            15,
            18,
            15,
        )
        root.setSpacing(
            7
        )

        top = QHBoxLayout()

        self.title = QLabel(
            title
        )
        self.title.setObjectName(
            "StatTitle"
        )

        self.badge = QLabel(
            "WAITING"
        )
        self.badge.setObjectName(
            "StatBadge"
        )

        top.addWidget(
            self.title
        )
        top.addStretch()
        top.addWidget(
            self.badge
        )

        self.value = QLabel(
            "--"
        )
        self.value.setObjectName(
            "StatValue"
        )
        self.value.setWordWrap(
            True
        )

        self.subtitle = QLabel(
            "Waiting for scan"
        )
        self.subtitle.setObjectName(
            "StatSubtitle"
        )
        self.subtitle.setWordWrap(
            True
        )

        root.addLayout(
            top
        )
        root.addWidget(
            self.value
        )
        root.addWidget(
            self.subtitle
        )


    def set_status(
        self,
        value,
        subtitle,
        badge,
        state,
    ):
        self.value.setText(
            value
        )
        self.subtitle.setText(
            subtitle
        )
        self.badge.setText(
            badge
        )

        self.setProperty(
            "state",
            state,
        )

        self.badge.setProperty(
            "state",
            state,
        )

        self.style().unpolish(
            self
        )
        self.style().polish(
            self
        )

        self.badge.style().unpolish(
            self.badge
        )
        self.badge.style().polish(
            self.badge
        )


class InfoValueCard(QFrame):

    def __init__(
        self,
        title,
    ):
        super().__init__()

        self.setObjectName(
            "InfoValueCard"
        )

        layout = QVBoxLayout(
            self
        )
        layout.setContentsMargins(
            15,
            13,
            15,
            13,
        )

        heading = QLabel(
            title
        )
        heading.setObjectName(
            "InfoValueTitle"
        )

        self.value = QLabel(
            "Not scanned yet"
        )
        self.value.setObjectName(
            "InfoValueText"
        )
        self.value.setWordWrap(
            True
        )

        layout.addWidget(
            heading
        )
        layout.addWidget(
            self.value
        )


    def set_value(
        self,
        value,
    ):
        self.value.setText(
            value
        )


class SectionCard(QFrame):

    def __init__(
        self,
        title,
    ):
        super().__init__()

        self.setObjectName(
            "SectionCard"
        )

        layout = QVBoxLayout(
            self
        )
        layout.setContentsMargins(
            17,
            15,
            17,
            15,
        )

        heading = QLabel(
            title
        )
        heading.setObjectName(
            "SectionTitle"
        )

        self.text = QLabel(
            ""
        )
        self.text.setObjectName(
            "SectionText"
        )
        self.text.setWordWrap(
            True
        )
        self.text.setTextInteractionFlags(
            Qt.TextSelectableByMouse
        )

        layout.addWidget(
            heading
        )
        layout.addWidget(
            self.text
        )


    def set_lines(
        self,
        lines,
        empty_text,
    ):
        if not lines:
            self.text.setText(
                empty_text
            )
            return

        self.text.setText(
            "\n".join(
                f"• {line}"
                for line in lines
            )
        )


class SummaryBanner(QFrame):

    def __init__(self):
        super().__init__()

        self.setObjectName(
            "SummaryBanner"
        )

        root = QHBoxLayout(
            self
        )
        root.setContentsMargins(
            20,
            16,
            20,
            16,
        )

        left = QVBoxLayout()

        title = QLabel(
            "System Health"
        )
        title.setObjectName(
            "SummaryTitle"
        )

        self.text = QLabel(
            "Run a Full System Scan to check this PC."
        )
        self.text.setObjectName(
            "SummaryText"
        )
        self.text.setWordWrap(
            True
        )

        self.meta = QLabel(
            "SCAN COVERAGE --  •  LAST SCAN NEVER"
        )
        self.meta.setObjectName(
            "SummaryMeta"
        )

        left.addWidget(
            title
        )
        left.addWidget(
            self.text
        )
        left.addWidget(
            self.meta
        )

        root.addLayout(
            left,
            1,
        )

        self.score = QLabel(
            "--"
        )
        self.score.setObjectName(
            "SummaryScore"
        )

        root.addWidget(
            self.score
        )


    def update_summary(
        self,
        result,
    ):
        score = result[
            "score"
        ]

        coverage = result.get(
            "coverage"
        )

        healthy = result.get(
            "healthy_areas",
            0,
        )

        attention = result.get(
            "attention_areas",
            0,
        )

        self.score.setText(
            str(score)
        )

        if score >= 90:
            headline = (
                "System looks healthy"
            )
        elif score >= 75:
            headline = (
                "Minor items are worth checking"
            )
        elif score >= 50:
            headline = (
                "Some areas need attention"
            )
        else:
            headline = (
                "Important issues were detected"
            )

        self.text.setText(
            f"{headline} • "
            f"{healthy} area(s) healthy • "
            f"{attention} area(s) to check"
        )

        coverage_text = (
            f"{coverage}%"
            if coverage is not None
            else "N/A"
        )

        self.meta.setText(
            f"SCAN COVERAGE {coverage_text}"
            f"  •  LAST SCAN {result['scan_time']}"
        )


class ResultPanel(QFrame):

    def __init__(self):
        super().__init__()

        self.setObjectName(
            "ResultPanel"
        )

        root = QVBoxLayout(
            self
        )
        root.setContentsMargins(
            22,
            22,
            22,
            22,
        )
        root.setSpacing(
            15
        )

        header = QHBoxLayout()

        left = QVBoxLayout()

        self.title = QLabel(
            "No scan yet"
        )
        self.title.setObjectName(
            "ResultTitle"
        )

        self.description = QLabel(
            "Start a scan to see diagnostic results."
        )
        self.description.setObjectName(
            "ResultExplanation"
        )
        self.description.setWordWrap(
            True
        )

        left.addWidget(
            self.title
        )
        left.addWidget(
            self.description
        )

        header.addLayout(
            left,
            1,
        )

        right = QVBoxLayout()

        caption = QLabel(
            "ESTIMATED SCORE"
        )
        caption.setObjectName(
            "ScoreCaption"
        )

        self.score = QLabel(
            "--"
        )
        self.score.setObjectName(
            "ResultScore"
        )

        self.badge = QLabel(
            "WAITING"
        )
        self.badge.setObjectName(
            "StatusBadge"
        )

        right.addWidget(
            caption,
            alignment=Qt.AlignRight,
        )
        right.addWidget(
            self.score,
            alignment=Qt.AlignRight,
        )
        right.addWidget(
            self.badge,
            alignment=Qt.AlignRight,
        )

        header.addLayout(
            right
        )

        root.addLayout(
            header
        )

        self.facts = SectionCard(
            "What we found"
        )
        self.issues = SectionCard(
            "Possible problems"
        )
        self.actions = SectionCard(
            "What you should do"
        )

        root.addWidget(
            self.facts
        )
        root.addWidget(
            self.issues
        )
        root.addWidget(
            self.actions
        )

        self.note = QLabel(
            ""
        )
        self.note.setObjectName(
            "ResultNote"
        )
        self.note.setWordWrap(
            True
        )

        root.addWidget(
            self.note
        )


    def set_badge(
        self,
        text,
        state,
    ):
        self.badge.setText(
            text
        )
        self.badge.setProperty(
            "state",
            state,
        )

        self.badge.style().unpolish(
            self.badge
        )
        self.badge.style().polish(
            self.badge
        )


    def set_scanning(self):
        self.title.setText(
            "Scanning..."
        )
        self.description.setText(
            "OpenFix is collecting local diagnostic information."
        )
        self.score.setText(
            "--"
        )
        self.set_badge(
            "SCANNING",
            "neutral",
        )

        self.facts.set_lines(
            [],
            "Collecting information...",
        )
        self.issues.set_lines(
            [],
            "Waiting for results...",
        )
        self.actions.set_lines(
            [],
            "Recommendations will appear here if needed.",
        )

        self.note.setText(
            "Local diagnostic scan in progress."
        )


    def set_result(
        self,
        result,
    ):
        score = result[
            "score"
        ]

        coverage = result.get(
            "coverage"
        )

        self.title.setText(
            result["title"]
        )
        self.score.setText(
            f"{score}/100"
        )

        partial = (
            coverage is not None
            and coverage < 100
        )

        if partial:
            self.set_badge(
                "PARTIAL",
                "partial",
            )
            self.description.setText(
                f"Scan completed with {coverage}% diagnostic coverage."
            )

        elif score >= 90:
            self.set_badge(
                "HEALTHY",
                "good",
            )
            self.description.setText(
                "No major problem was detected."
            )

        elif score >= 75:
            self.set_badge(
                "CHECK",
                "minor",
            )
            self.description.setText(
                "A few items may be worth checking."
            )

        elif score >= 50:
            self.set_badge(
                "ATTENTION",
                "warning",
            )
            self.description.setText(
                "Some diagnostic results need attention."
            )

        else:
            self.set_badge(
                "IMPORTANT",
                "danger",
            )
            self.description.setText(
                "Important items should be checked carefully."
            )

        self.facts.set_lines(
            result.get(
                "facts",
                [],
            ),
            "No diagnostic facts are available.",
        )

        self.issues.set_lines(
            result.get(
                "issues",
                [],
            ),
            "No major problems were found.",
        )

        self.actions.set_lines(
            result.get(
                "actions",
                [],
            ),
            "No immediate action appears necessary.",
        )

        coverage_text = (
            f"{coverage}%"
            if coverage is not None
            else "Not available"
        )

        self.note.setText(
            f"Scan coverage: {coverage_text} • "
            f"Scan time: {result['scan_time']}\n"
            f"{result.get('note', '')}"
        )


class PageHeader(QWidget):

    def __init__(
        self,
        title,
        subtitle,
    ):
        super().__init__()

        root = QVBoxLayout(
            self
        )
        root.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        title_label = QLabel(
            title
        )
        title_label.setObjectName(
            "PageTitle"
        )

        subtitle_label = QLabel(
            subtitle
        )
        subtitle_label.setObjectName(
            "PageSubtitle"
        )
        subtitle_label.setWordWrap(
            True
        )

        root.addWidget(
            title_label
        )
        root.addWidget(
            subtitle_label
        )


# =========================================================
# MAIN WINDOW
# =========================================================

class OpenFixWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.worker = None

        self.scan_buttons = []
        self.active_result = None
        self.active_progress = None

        self.setWindowTitle(
            f"OpenFix AI {APP_VERSION}"
        )

        self.resize(
            1360,
            880,
        )

        self.setMinimumSize(
            1100,
            720,
        )

        root = QWidget()
        root.setObjectName(
            "Root"
        )

        self.setCentralWidget(
            root
        )

        main = QHBoxLayout(
            root
        )
        main.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        main.setSpacing(
            0
        )

        self.sidebar = (
            self.build_sidebar()
        )

        main.addWidget(
            self.sidebar
        )

        content = QWidget()
        content.setObjectName(
            "Content"
        )

        content_layout = QVBoxLayout(
            content
        )
        content_layout.setContentsMargins(
            34,
            25,
            34,
            28,
        )

        content_layout.addWidget(
            self.build_topbar()
        )

        self.pages = (
            QStackedWidget()
        )

        content_layout.addWidget(
            self.pages,
            1,
        )

        main.addWidget(
            content,
            1,
        )

        self.dashboard_page = (
            self.build_dashboard()
        )

        self.smart_page = (
            self.build_doctor_page(
                "Local Smart Doctor",
                "Combines several local checks and helps decide what to investigate first.",
                "smart",
            )
        )

        self.internet_page = (
            self.build_doctor_page(
                "Internet Doctor",
                "Checks connection availability, delay, DNS and stability.",
                "internet",
            )
        )

        self.gaming_page = (
            self.build_doctor_page(
                "Gaming Doctor",
                "Checks common CPU, RAM, GPU and network conditions that may affect games.",
                "gaming",
            )
        )

        self.slow_page = (
            self.build_doctor_page(
                "Slow PC Doctor",
                "Checks common reasons Windows or applications may feel slow.",
                "slow",
            )
        )

        self.storage_page = (
            self.build_doctor_page(
                "Storage Doctor",
                "Checks free space across your drives.",
                "storage",
            )
        )

        self.event_page = (
            self.build_doctor_page(
                "Windows Event Doctor",
                "Checks recent Windows errors while filtering common background noise.",
                "events",
            )
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
            self.pages.addWidget(
                page
            )

        self.apply_style()

        self.show_page(
            0,
            self.dashboard_nav,
        )


    # =====================================================
    # SIDEBAR
    # =====================================================

    def build_sidebar(self):
        sidebar = QFrame()
        sidebar.setObjectName(
            "Sidebar"
        )
        sidebar.setFixedWidth(
            240
        )

        root = QVBoxLayout(
            sidebar
        )
        root.setContentsMargins(
            18,
            24,
            18,
            20,
        )
        root.setSpacing(
            7
        )

        logo = QLabel(
            "OpenFix AI"
        )
        logo.setObjectName(
            "Logo"
        )

        version = QLabel(
            APP_VERSION
        )
        version.setObjectName(
            "SidebarVersion"
        )

        root.addWidget(
            logo
        )
        root.addWidget(
            version
        )
        root.addSpacing(
            25
        )

        section = QLabel(
            "PC DIAGNOSTICS"
        )
        section.setObjectName(
            "SidebarSection"
        )

        root.addWidget(
            section
        )

        self.dashboard_nav = (
            NavButton(
                "⌂   Dashboard"
            )
        )
        self.smart_nav = (
            NavButton(
                "✦   Smart Doctor"
            )
        )
        self.internet_nav = (
            NavButton(
                "◉   Internet"
            )
        )
        self.gaming_nav = (
            NavButton(
                "◆   Gaming"
            )
        )
        self.slow_nav = (
            NavButton(
                "◐   Slow PC"
            )
        )
        self.storage_nav = (
            NavButton(
                "▣   Storage"
            )
        )
        self.event_nav = (
            NavButton(
                "⚠   Windows Events"
            )
        )

        self.nav_buttons = [
            self.dashboard_nav,
            self.smart_nav,
            self.internet_nav,
            self.gaming_nav,
            self.slow_nav,
            self.storage_nav,
            self.event_nav,
        ]

        for button in (
            self.nav_buttons
        ):
            root.addWidget(
                button
            )

        root.addStretch()

        badge = QLabel(
            "●  LOCAL ANALYSIS"
        )
        badge.setObjectName(
            "LocalBadge"
        )

        privacy = QLabel(
            "No Cloud AI\n"
            "No external AI API\n"
            "Read-only diagnostics"
        )
        privacy.setObjectName(
            "PrivacyText"
        )

        root.addWidget(
            badge
        )
        root.addWidget(
            privacy
        )

        routes = [
            (
                self.dashboard_nav,
                0,
            ),
            (
                self.smart_nav,
                1,
            ),
            (
                self.internet_nav,
                2,
            ),
            (
                self.gaming_nav,
                3,
            ),
            (
                self.slow_nav,
                4,
            ),
            (
                self.storage_nav,
                5,
            ),
            (
                self.event_nav,
                6,
            ),
        ]

        for button, index in routes:
            button.clicked.connect(
                lambda checked=False,
                idx=index,
                btn=button:
                self.show_page(
                    idx,
                    btn,
                )
            )

        return sidebar


    # =====================================================
    # TOP BAR
    # =====================================================

    def build_topbar(self):
        widget = QWidget()

        layout = QHBoxLayout(
            widget
        )
        layout.setContentsMargins(
            0,
            0,
            0,
            20,
        )

        title = QLabel(
            "PC Health & Diagnostics"
        )
        title.setObjectName(
            "TopTitle"
        )

        layout.addWidget(
            title
        )
        layout.addStretch()

        badge = QLabel(
            "MEASURED FACTS + ESTIMATED ANALYSIS"
        )
        badge.setObjectName(
            "FactsBadge"
        )

        guide = QPushButton(
            "Quick Guide"
        )
        guide.setObjectName(
            "SecondaryButton"
        )

        terms = QPushButton(
            "Simple Terms"
        )
        terms.setObjectName(
            "SecondaryButton"
        )

        safety = QPushButton(
            "Safety & Privacy"
        )
        safety.setObjectName(
            "SafetyButton"
        )

        guide.clicked.connect(
            self.show_guide
        )
        terms.clicked.connect(
            self.show_terms
        )
        safety.clicked.connect(
            self.show_safety
        )

        layout.addWidget(
            badge
        )
        layout.addWidget(
            guide
        )
        layout.addWidget(
            terms
        )
        layout.addWidget(
            safety
        )

        return widget


    # =====================================================
    # DASHBOARD
    # =====================================================

    def build_dashboard(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(
            True
        )
        scroll.setFrameShape(
            QFrame.NoFrame
        )

        page = QWidget()
        scroll.setWidget(
            page
        )

        root = QVBoxLayout(
            page
        )
        root.setContentsMargins(
            0,
            0,
            0,
            24,
        )
        root.setSpacing(
            16
        )

        root.addWidget(
            PageHeader(
                "System Dashboard",
                "A quick view of your PC health and the areas worth checking.",
            )
        )

        self.summary = (
            SummaryBanner()
        )
        root.addWidget(
            self.summary
        )

        # Scan CTA moved very high
        hero = QFrame()
        hero.setObjectName(
            "HeroCard"
        )

        hero_layout = QHBoxLayout(
            hero
        )
        hero_layout.setContentsMargins(
            22,
            18,
            22,
            18,
        )

        text_box = QVBoxLayout()

        hero_title = QLabel(
            "Full System Scan"
        )
        hero_title.setObjectName(
            "HeroTitle"
        )

        hero_text = QLabel(
            "Run the main health checks and update this Dashboard."
        )
        hero_text.setObjectName(
            "HeroText"
        )

        text_box.addWidget(
            hero_title
        )
        text_box.addWidget(
            hero_text
        )

        hero_layout.addLayout(
            text_box,
            1,
        )

        self.full_scan_btn = (
            QPushButton(
                "Start Full Scan"
            )
        )
        self.full_scan_btn.setObjectName(
            "PrimaryButton"
        )
        self.full_scan_btn.setCursor(
            Qt.PointingHandCursor
        )

        hero_layout.addWidget(
            self.full_scan_btn
        )

        root.addWidget(
            hero
        )

        self.scan_buttons.append(
            self.full_scan_btn
        )

        self.dashboard_progress = (
            QProgressBar()
        )
        self.dashboard_progress.setRange(
            0,
            0,
        )
        self.dashboard_progress.hide()

        root.addWidget(
            self.dashboard_progress
        )

        # Main health cards
        row1 = QHBoxLayout()
        row1.setSpacing(
            14
        )

        self.cpu_card = (
            StatCard("CPU")
        )
        self.ram_card = (
            StatCard("RAM")
        )
        self.storage_card = (
            StatCard(
                "Windows Drive"
            )
        )

        row1.addWidget(
            self.cpu_card
        )
        row1.addWidget(
            self.ram_card
        )
        row1.addWidget(
            self.storage_card
        )

        root.addLayout(
            row1
        )

        row2 = QHBoxLayout()
        row2.setSpacing(
            14
        )

        self.network_card = (
            StatCard("Internet")
        )
        self.gpu_card = (
            StatCard("Graphics")
        )
        self.events_card = (
            StatCard(
                "Windows Events"
            )
        )

        row2.addWidget(
            self.network_card
        )
        row2.addWidget(
            self.gpu_card
        )
        row2.addWidget(
            self.events_card
        )

        root.addLayout(
            row2
        )

        # System information collapsible
        self.system_section = (
            CollapsibleSection(
                "System Information",
                "Processor, RAM, Windows, GPU, driver, uptime and network adapter",
                expanded=False,
            )
        )

        info_grid = QGridLayout()
        info_grid.setSpacing(
            12
        )

        self.cpu_model_card = (
            InfoValueCard(
                "Processor"
            )
        )
        self.total_ram_card = (
            InfoValueCard(
                "Installed RAM"
            )
        )
        self.windows_card = (
            InfoValueCard(
                "Windows"
            )
        )
        self.gpu_info_card = (
            InfoValueCard(
                "Graphics Device"
            )
        )
        self.gpu_driver_card = (
            InfoValueCard(
                "Graphics Driver"
            )
        )
        self.uptime_card = (
            InfoValueCard(
                "PC Uptime"
            )
        )
        self.adapter_card = (
            InfoValueCard(
                "Network Adapter"
            )
        )

        info_grid.addWidget(
            self.cpu_model_card,
            0,
            0,
        )
        info_grid.addWidget(
            self.total_ram_card,
            0,
            1,
        )
        info_grid.addWidget(
            self.windows_card,
            0,
            2,
        )
        info_grid.addWidget(
            self.gpu_info_card,
            1,
            0,
        )
        info_grid.addWidget(
            self.gpu_driver_card,
            1,
            1,
        )
        info_grid.addWidget(
            self.uptime_card,
            1,
            2,
        )
        info_grid.addWidget(
            self.adapter_card,
            2,
            0,
            1,
            3,
        )

        self.system_section.add_layout(
            info_grid
        )

        root.addWidget(
            self.system_section
        )

        # Top RAM collapsible
        self.process_section = (
            CollapsibleSection(
                "Top RAM Usage",
                "Applications currently using the most system memory",
                expanded=False,
            )
        )

        self.process_card = (
            SectionCard(
                "Applications using the most RAM"
            )
        )

        self.process_card.set_lines(
            [],
            "Run a Full System Scan to see process information.",
        )

        self.process_section.add_widget(
            self.process_card
        )

        root.addWidget(
            self.process_section
        )

        self.dashboard_result = (
            ResultPanel()
        )

        root.addWidget(
            self.dashboard_result
        )

        root.addStretch()

        self.full_scan_btn.clicked.connect(
            lambda:
            self.start_scan(
                "full",
                self.dashboard_result,
                self.dashboard_progress,
            )
        )

        return scroll


    # =====================================================
    # DOCTOR PAGE
    # =====================================================

    def build_doctor_page(
        self,
        title,
        subtitle,
        mode,
    ):
        scroll = QScrollArea()
        scroll.setWidgetResizable(
            True
        )
        scroll.setFrameShape(
            QFrame.NoFrame
        )

        page = QWidget()
        scroll.setWidget(
            page
        )

        root = QVBoxLayout(
            page
        )
        root.setContentsMargins(
            0,
            0,
            0,
            24,
        )
        root.setSpacing(
            18
        )

        root.addWidget(
            PageHeader(
                title,
                subtitle,
            )
        )

        action = QFrame()
        action.setObjectName(
            "ActionCard"
        )

        action_layout = QHBoxLayout(
            action
        )
        action_layout.setContentsMargins(
            22,
            19,
            22,
            19,
        )

        text = QVBoxLayout()

        ready = QLabel(
            "Ready to scan"
        )
        ready.setObjectName(
            "ActionTitle"
        )

        description = QLabel(
            "Read-only diagnostic scan. OpenFix will not automatically change Windows."
        )
        description.setObjectName(
            "ActionText"
        )

        text.addWidget(
            ready
        )
        text.addWidget(
            description
        )

        action_layout.addLayout(
            text,
            1,
        )

        button = QPushButton(
            "Run Scan"
        )
        button.setObjectName(
            "PrimaryButton"
        )

        action_layout.addWidget(
            button
        )

        self.scan_buttons.append(
            button
        )

        root.addWidget(
            action
        )

        progress = QProgressBar()
        progress.setRange(
            0,
            0,
        )
        progress.hide()

        root.addWidget(
            progress
        )

        result = ResultPanel()

        root.addWidget(
            result
        )

        root.addStretch()

        button.clicked.connect(
            lambda:
            self.start_scan(
                mode,
                result,
                progress,
            )
        )

        return scroll


    # =====================================================
    # NAVIGATION / SCANNING
    # =====================================================

    def show_page(
        self,
        index,
        active,
    ):
        self.pages.setCurrentIndex(
            index
        )

        for button in (
            self.nav_buttons
        ):
            button.setChecked(
                button == active
            )


    def enable_scan_buttons(
        self,
        enabled,
    ):
        for button in (
            self.scan_buttons
        ):
            button.setEnabled(
                enabled
            )


    def start_scan(
        self,
        mode,
        result,
        progress,
    ):
        if (
            self.worker is not None
            and self.worker.isRunning()
        ):
            self.show_small_message(
                "Scan already running",
                "OpenFix is already checking this PC. Please wait for the current scan to finish.",
            )
            return

        self.active_result = result
        self.active_progress = progress

        result.set_scanning()
        progress.show()

        self.enable_scan_buttons(
            False
        )

        self.worker = ScanWorker(
            mode
        )
        self.worker.finished.connect(
            self.scan_complete
        )
        self.worker.start()


    def scan_complete(
        self,
        result,
    ):
        if self.active_progress:
            self.active_progress.hide()

        self.enable_scan_buttons(
            True
        )

        if self.active_result:
            self.active_result.set_result(
                result
            )

        if (
            "dashboard_data"
            in result
        ):
            self.update_dashboard(
                result[
                    "dashboard_data"
                ],
                result[
                    "event_analysis"
                ],
            )

            self.summary.update_summary(
                result
            )


    # =====================================================
    # DASHBOARD UPDATE
    # =====================================================

    def update_dashboard(
        self,
        data,
        events,
    ):
        cpu = data["cpu"]

        if cpu is None:
            self.cpu_card.set_status(
                "N/A",
                "CPU usage could not be read",
                "UNAVAILABLE",
                "unavailable",
            )

        elif cpu < 80:
            self.cpu_card.set_status(
                f"{cpu:.0f}%",
                "Normal usage",
                "GOOD",
                "good",
            )

        elif cpu < 90:
            self.cpu_card.set_status(
                f"{cpu:.0f}%",
                "Higher than normal",
                "CHECK",
                "minor",
            )

        else:
            self.cpu_card.set_status(
                f"{cpu:.0f}%",
                "Very high usage",
                "HIGH",
                "danger",
            )

        # RAM
        memory = data[
            "memory"
        ]

        ram = memory[
            "percent"
        ]

        if ram is None:
            self.ram_card.set_status(
                "N/A",
                "RAM usage unavailable",
                "UNAVAILABLE",
                "unavailable",
            )

        elif ram < 80:
            self.ram_card.set_status(
                f"{ram:.0f}%",
                "Normal usage",
                "GOOD",
                "good",
            )

        elif ram < 90:
            self.ram_card.set_status(
                f"{ram:.0f}%",
                "High usage",
                "CHECK",
                "minor",
            )

        else:
            self.ram_card.set_status(
                f"{ram:.0f}%",
                "Very high usage",
                "HIGH",
                "danger",
            )

        # Windows drive
        drive = data[
            "system_drive"
        ]

        if not drive:
            self.storage_card.set_status(
                "N/A",
                "Drive information unavailable",
                "UNAVAILABLE",
                "unavailable",
            )

        else:
            free_gb = (
                drive["free"]
                / (1024 ** 3)
            )

            free_percent = (
                100
                - drive["percent"]
            )

            subtitle = (
                f"{drive['device']} free space • "
                f"{free_percent:.0f}% free"
            )

            if (
                free_gb < 5
                or free_percent < 3
            ):
                badge = "LOW"
                state = "danger"

            elif (
                free_gb < 15
                or free_percent < 8
            ):
                badge = "CHECK"
                state = "minor"

            else:
                badge = "GOOD"
                state = "good"

            self.storage_card.set_status(
                f"{free_gb:.0f} GB",
                subtitle,
                badge,
                state,
            )

        # Network
        network = data[
            "network"
        ]

        if not network[
            "internet"
        ]:
            self.network_card.set_status(
                "Offline",
                "Internet connection not confirmed",
                "CHECK",
                "danger",
            )

        else:
            ping = network[
                "ping"
            ]
            loss = network[
                "packet_loss"
            ]

            value = (
                f"{ping} ms"
                if ping is not None
                else "Online"
            )

            if (
                loss is not None
                and loss >= 3
            ):
                self.network_card.set_status(
                    value,
                    f"{loss}% packet loss",
                    "UNSTABLE",
                    "warning",
                )

            elif (
                ping is not None
                and ping >= 150
            ):
                self.network_card.set_status(
                    value,
                    "High response delay",
                    "HIGH",
                    "warning",
                )

            else:
                self.network_card.set_status(
                    value,
                    (
                        f"{loss}% packet loss"
                        if loss is not None
                        else "Connection reachable"
                    ),
                    "GOOD",
                    "good",
                )

        # GPU
        gpu = data["gpu"]

        if not gpu[
            "available"
        ]:
            self.gpu_card.set_status(
                "N/A",
                "Graphics information unavailable",
                "UNAVAILABLE",
                "unavailable",
            )

        else:
            name = gpu["name"]

            if len(name) > 30:
                name = (
                    name[:27]
                    + "..."
                )

            temperature = gpu[
                "temperature"
            ]

            if temperature is None:
                self.gpu_card.set_status(
                    name,
                    "Temperature sensor not available",
                    "TEMP N/A",
                    "unavailable",
                )

            elif temperature >= 90:
                self.gpu_card.set_status(
                    name,
                    f"{temperature:.0f}°C",
                    "HOT",
                    "danger",
                )

            elif temperature >= 83:
                self.gpu_card.set_status(
                    name,
                    f"{temperature:.0f}°C",
                    "CHECK",
                    "warning",
                )

            else:
                self.gpu_card.set_status(
                    name,
                    f"{temperature:.0f}°C",
                    "GOOD",
                    "good",
                )

        # Events
        serious = (
            events[
                "hardware_errors"
            ]
            + events[
                "storage_errors"
            ]
            + events[
                "shutdown_errors"
            ]
            + events[
                "gpu_errors"
            ]
        )

        if not events[
            "available"
        ]:
            self.events_card.set_status(
                "N/A",
                "Event data unavailable",
                "UNAVAILABLE",
                "unavailable",
            )

        elif serious == 0:
            self.events_card.set_status(
                "Good",
                "No major system event detected",
                "GOOD",
                "good",
            )

        else:
            self.events_card.set_status(
                str(serious),
                "Important event(s) detected",
                "CHECK",
                "warning",
            )

        # System info
        self.cpu_model_card.set_value(
            data["cpu_model"]
        )

        self.total_ram_card.set_value(
            format_bytes(
                memory["total"]
            )
        )

        windows = data[
            "windows"
        ]

        self.windows_card.set_value(
            f"{windows['caption']} • "
            f"Build {windows['build']}"
        )

        self.gpu_info_card.set_value(
            (
                gpu["name"]
                if gpu["available"]
                else "Not available"
            )
        )

        self.gpu_driver_card.set_value(
            (
                gpu["driver"]
                if gpu["driver"]
                else "Not available"
            )
        )

        self.uptime_card.set_value(
            data[
                "uptime"
            ]["text"]
        )

        adapter = network[
            "adapter"
        ]

        self.adapter_card.set_value(
            (
                f"{adapter['name']} • "
                f"{adapter['description']} • "
                f"{adapter['link_speed']}"
                if adapter[
                    "available"
                ]
                else "Not available"
            )
        )

        # Processes
        lines = []

        total_ram = (
            memory["total"]
            or 0
        )

        for index, process in enumerate(
            data[
                "processes"
            ][:3],
            start=1,
        ):
            if total_ram > 0:
                percent = (
                    process["memory"]
                    / total_ram
                    * 100
                )
            else:
                percent = 0

            lines.append(
                f"{index}. "
                f"{process['name']} — "
                f"{format_bytes(process['memory'])} "
                f"({percent:.1f}% of installed RAM)"
            )

        self.process_card.set_lines(
            lines,
            "Process information is not available.",
        )


    # =====================================================
    # DIALOGS
    # =====================================================

    def show_guide(self):
        dialog = ModernDialog(
            self,
            "How to Use OpenFix AI",
            "A simple guide to understanding the diagnostic results.",
            [
                (
                    "1. Start with Full System Scan",
                    "Use the Dashboard scan first for a general PC health overview.",
                ),
                (
                    "What we found",
                    "Facts that OpenFix read or measured from this PC.",
                ),
                (
                    "Possible problems",
                    "OpenFix's local interpretation of the measured information.",
                ),
                (
                    "What you should do",
                    "Suggested next steps. The most useful action appears first.",
                ),
                (
                    "Scan coverage",
                    "Shows how much of the planned diagnostic information OpenFix was able to read. Partial coverage does not automatically mean the PC has a problem.",
                ),
            ],
        )

        dialog.exec()


    def show_terms(self):
        dialog = ModernDialog(
            self,
            "Simple Terms",
            "Short explanations for common computer terms used by OpenFix.",
            [
                (
                    "Ping / Response Time",
                    "How long data takes to travel to another computer and back. Lower is usually better.",
                ),
                (
                    "Packet Loss",
                    "Network data that did not reach its destination. Packet loss can cause lag, voice problems or unstable connections.",
                ),
                (
                    "DNS",
                    "The system that converts website names into network addresses.",
                ),
                (
                    "Event ID",
                    "A reference number Windows gives to a recorded system event.",
                ),
                (
                    "Scan Coverage",
                    "How much of the planned diagnostic information OpenFix successfully read.",
                ),
                (
                    "CPU",
                    "The main processor that performs calculations.",
                ),
                (
                    "RAM",
                    "Fast temporary memory used by Windows and running applications.",
                ),
                (
                    "Uptime",
                    "How long the PC has been running since its last full boot.",
                ),
            ],
        )

        dialog.exec()


    def show_safety(self):
        dialog = ModernDialog(
            self,
            "Safety & Privacy",
            "Important information about how OpenFix currently works.",
            [
                (
                    "Local analysis",
                    "No Cloud AI and no external AI API are used. Smart Doctor analysis is performed with built-in local rules.",
                ),
                (
                    "Read-only diagnostics",
                    "OpenFix does not automatically edit the Registry, remove drivers or disable Windows services.",
                ),
                (
                    "Normal connectivity checks",
                    "Internet Doctor uses standard network tests such as ping and DNS lookup. These are not AI services.",
                ),
                (
                    "Scores are estimates",
                    "A low score does not prove that hardware is broken. A score of 100 also cannot guarantee that every component is healthy.",
                ),
                (
                    "Before major changes",
                    "Important hardware problems should be confirmed with dedicated diagnostic tools before replacing hardware or making advanced Windows changes.",
                ),
            ],
            warning=True,
        )

        dialog.exec()


    def show_small_message(
        self,
        title,
        message,
    ):
        dialog = ModernDialog(
            self,
            title,
            message,
            [
                (
                    "Current status",
                    "Wait for the current diagnostic scan to finish before starting another one.",
                )
            ],
        )

        dialog.resize(
            560,
            360,
        )
        dialog.exec()


    # =====================================================
    # STYLE
    # =====================================================

    def apply_style(self):
        self.setStyleSheet("""
            * {
                font-family: "Segoe UI";
            }

            #Root,
            #Content,
            QDialog {
                background: #0c0f14;
            }

            QScrollArea {
                background: transparent;
                border: none;
            }

            QScrollArea > QWidget > QWidget {
                background: transparent;
            }

            #Sidebar {
                background: #13171d;
                border-right: 1px solid #242b35;
            }

            #Logo {
                color: #ffffff;
                font-size: 25px;
                font-weight: 800;
            }

            #SidebarVersion {
                color: #6d7785;
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
            }

            NavButton:hover {
                background: #1a1f27;
                color: white;
            }

            NavButton:checked {
                background: #1e2939;
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
                color: white;
                font-size: 30px;
                font-weight: 800;
            }

            #PageSubtitle {
                color: #858f9d;
                font-size: 14px;
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
                border: 1px solid #26415a;
                border-radius: 14px;
            }

            #SummaryTitle {
                color: white;
                font-size: 16px;
                font-weight: 750;
            }

            #SummaryText {
                color: #90a3b9;
                font-size: 12px;
            }

            #SummaryMeta {
                color: #657991;
                font-size: 9px;
                font-weight: 700;
            }

            #SummaryScore {
                color: #8cb8ff;
                font-size: 38px;
                font-weight: 850;
            }

            #HeroCard {
                background: #161b23;
                border: 1px solid #29364c;
                border-radius: 14px;
            }

            #HeroTitle {
                color: white;
                font-size: 18px;
                font-weight: 750;
            }

            #HeroText {
                color: #818c9b;
                font-size: 12px;
            }

            #PrimaryButton {
                background: #367df6;
                color: white;
                border: none;
                border-radius: 9px;
                padding: 11px 18px;
                font-size: 13px;
                font-weight: 700;
                min-width: 110px;
            }

            #PrimaryButton:hover {
                background: #4a8aff;
            }

            #PrimaryButton:disabled {
                background: #26354b;
                color: #748398;
            }

            #StatCard {
                background: #151920;
                border: 1px solid #252c36;
                border-radius: 14px;
                min-height: 112px;
            }

            #StatCard[state="good"] {
                border: 1px solid #1e513b;
            }

            #StatCard[state="warning"],
            #StatCard[state="minor"] {
                border: 1px solid #694517;
            }

            #StatCard[state="danger"] {
                border: 1px solid #71313a;
            }

            #StatTitle {
                color: #7f93ae;
                font-size: 10px;
                font-weight: 700;
            }

            #StatValue {
                color: white;
                font-size: 24px;
                font-weight: 800;
            }

            #StatSubtitle {
                color: #718198;
                font-size: 10px;
            }

            #StatBadge {
                background: #222832;
                color: #8f9bab;
                border-radius: 6px;
                padding: 5px 9px;
                font-size: 8px;
                font-weight: 800;
            }

            #StatBadge[state="good"] {
                background: #123725;
                color: #69e6a0;
            }

            #StatBadge[state="minor"],
            #StatBadge[state="warning"] {
                background: #352512;
                color: #f3b25e;
            }

            #StatBadge[state="danger"] {
                background: #391b20;
                color: #ff7f87;
            }

            #StatBadge[state="unavailable"] {
                background: #202630;
                color: #8a9ab0;
            }

            #CollapsibleSection {
                background: transparent;
                border: 1px solid #252c35;
                border-radius: 13px;
            }

            #CollapsibleHeader {
                background: #14191f;
                border-radius: 12px;
            }

            #CollapsibleTitle {
                color: #e8edf4;
                font-size: 14px;
                font-weight: 750;
            }

            #CollapsibleSubtitle {
                color: #6e7c8e;
                font-size: 10px;
            }

            #CollapseToggle {
                background: #202833;
                color: #90baff;
                border: 1px solid #334257;
                border-radius: 8px;
                font-size: 23px;
                font-weight: 700;
            }

            #CollapseToggle:hover {
                background: #293447;
                border: 1px solid #4971a6;
            }

            #CollapsibleContent {
                background: #101419;
                border-top: 1px solid #222933;
            }

            #InfoValueCard {
                background: #13181e;
                border: 1px solid #252c35;
                border-radius: 10px;
                min-height: 75px;
            }

            #InfoValueTitle {
                color: #73869f;
                font-size: 9px;
                font-weight: 700;
            }

            #InfoValueText {
                color: #edf1f7;
                font-size: 11px;
                font-weight: 600;
            }

            #SectionCard {
                background: #171b22;
                border: 1px solid #242b34;
                border-radius: 11px;
            }

            #SectionTitle {
                color: #e0e5ed;
                font-size: 13px;
                font-weight: 750;
            }

            #SectionText {
                color: #a5afbc;
                font-size: 11px;
            }

            #ActionCard {
                background: #151920;
                border: 1px solid #252c36;
                border-radius: 14px;
            }

            #ActionTitle {
                color: white;
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
                color: white;
                font-size: 21px;
                font-weight: 800;
            }

            #ResultExplanation {
                color: #84909f;
                font-size: 12px;
            }

            #ScoreCaption {
                color: #687381;
                font-size: 9px;
                font-weight: 800;
            }

            #ResultScore {
                color: white;
                font-size: 37px;
                font-weight: 850;
            }

            #StatusBadge {
                color: #adb7c5;
                background: #202630;
                border-radius: 7px;
                padding: 5px 9px;
                font-size: 9px;
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

            #StatusBadge[state="partial"] {
                color: #8dbfff;
                background: #17283d;
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

            #DialogTitle {
                color: white;
                font-size: 24px;
                font-weight: 800;
            }

            #DialogSubtitle {
                color: #7f8b9b;
                font-size: 12px;
            }

            #DialogCard {
                background: #161b22;
                border: 1px solid #282f39;
                border-radius: 11px;
            }

            #DialogWarningCard {
                background: #201b14;
                border: 1px solid #543b1c;
                border-radius: 11px;
            }

            #DialogCardTitle {
                color: #edf2f7;
                font-size: 13px;
                font-weight: 750;
            }

            #DialogCardText {
                color: #a7b1bf;
                font-size: 11px;
            }

            #DialogCloseX {
                background: #191f27;
                color: #aab4c1;
                border: 1px solid #2c3540;
                border-radius: 8px;
                font-size: 20px;
            }

            #DialogCloseX:hover {
                background: #252d38;
                color: white;
            }

            #DialogCloseButton {
                background: #367df6;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 18px;
                font-weight: 700;
            }

            #DialogCloseButton:hover {
                background: #4a8aff;
            }
        """)


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    app = QApplication(
        sys.argv
    )

    window = OpenFixWindow()

    window.show()

    sys.exit(
        app.exec()
    )