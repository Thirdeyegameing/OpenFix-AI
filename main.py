import sys
import os
import socket
import subprocess
import json
import psutil

from PySide6.QtCore import QThread, Signal
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
)


APP_VERSION = "0.4.3.1"


# =========================================================
# HELPERS
# =========================================================

def format_bytes(value):
    if value is None:
        return "Unknown"

    try:
        gb = value / (1024 ** 3)

        if gb >= 1:
            return f"{gb:.1f} GB"

        mb = value / (1024 ** 2)
        return f"{mb:.0f} MB"

    except Exception:
        return "Unknown"


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


# =========================================================
# CPU / RAM / DISK
# =========================================================

def scan_cpu():
    return psutil.cpu_percent(interval=1)


def scan_memory():
    ram = psutil.virtual_memory()

    return {
        "percent": ram.percent,
        "used": ram.used,
        "total": ram.total,
        "available": ram.available,
    }


def scan_disks():
    drives = []
    seen = set()

    for partition in psutil.disk_partitions(all=False):

        if not partition.device:
            continue

        if partition.device in seen:
            continue

        seen.add(partition.device)

        try:
            usage = psutil.disk_usage(partition.mountpoint)

            drives.append(
                {
                    "device": partition.device,
                    "mountpoint": partition.mountpoint,
                    "fstype": partition.fstype,
                    "total": usage.total,
                    "used": usage.used,
                    "free": usage.free,
                    "percent": usage.percent,
                }
            )

        except Exception:
            pass

    return drives


def scan_top_processes(limit=5):
    processes = []

    for proc in psutil.process_iter(
        ["pid", "name", "memory_info"]
    ):
        try:
            info = proc.info

            memory = (
                info["memory_info"].rss
                if info["memory_info"]
                else 0
            )

            processes.append(
                {
                    "name": info["name"] or "Unknown",
                    "pid": info["pid"],
                    "memory": memory,
                }
            )

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
        "name": "Unknown",
        "vram": None,
        "usage": None,
        "temperature": None,
        "driver": None,
    }

    command = r"""
    $gpu = Get-CimInstance Win32_VideoController |
    Select-Object Name, AdapterRAM, DriverVersion

    $gpu | ConvertTo-Json -Compress
    """

    output = run_powershell(command)

    if output:
        try:
            data = json.loads(output)

            if isinstance(data, list):
                data = data[0]

            gpu["name"] = (
                data.get("Name")
                or "Unknown"
            )

            gpu["vram"] = data.get(
                "AdapterRAM"
            )

            gpu["driver"] = data.get(
                "DriverVersion"
            )

        except Exception:
            pass

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
            creationflags=creationflags,
            timeout=5,
        )

        if result.returncode == 0:

            line = (
                result.stdout.strip()
                .splitlines()[0]
            )

            parts = [
                x.strip()
                for x in line.split(",")
            ]

            if len(parts) >= 5:

                gpu["name"] = parts[0]

                try:
                    gpu["vram"] = (
                        float(parts[1])
                        * 1024
                        * 1024
                    )
                except Exception:
                    pass

                try:
                    gpu["usage"] = float(
                        parts[2]
                    )
                except Exception:
                    pass

                try:
                    gpu["temperature"] = float(
                        parts[3]
                    )
                except Exception:
                    pass

                gpu["driver"] = parts[4]

    except Exception:
        pass

    return gpu


# =========================================================
# NETWORK
# =========================================================

def get_active_adapter():
    command = r"""
    $adapter =
    Get-NetAdapter |
    Where-Object {$_.Status -eq "Up"} |
    Sort-Object LinkSpeed -Descending |
    Select-Object -First 1 `
        Name,
        InterfaceDescription,
        LinkSpeed,
        MacAddress

    $adapter | ConvertTo-Json -Compress
    """

    output = run_powershell(command)

    adapter = {
        "name": "Unknown",
        "description": "Unknown",
        "link_speed": "Unknown",
        "mac": "Unknown",
    }

    if output:
        try:
            data = json.loads(output)

            adapter["name"] = (
                data.get("Name")
                or "Unknown"
            )

            adapter["description"] = (
                data.get("InterfaceDescription")
                or "Unknown"
            )

            adapter["link_speed"] = (
                data.get("LinkSpeed")
                or "Unknown"
            )

            adapter["mac"] = (
                data.get("MacAddress")
                or "Unknown"
            )

        except Exception:
            pass

    return adapter


def get_default_gateway():
    command = r"""
    Get-NetRoute -DestinationPrefix "0.0.0.0/0" |
    Where-Object {$_.NextHop -ne "0.0.0.0"} |
    Sort-Object RouteMetric |
    Select-Object -First 1 -ExpandProperty NextHop
    """

    output = run_powershell(command)

    return (
        output
        if output
        else "Unknown"
    )


def get_dns_servers():
    command = r"""
    Get-DnsClientServerAddress -AddressFamily IPv4 |
    Where-Object {$_.ServerAddresses.Count -gt 0} |
    Select-Object -ExpandProperty ServerAddresses |
    Select-Object -Unique
    """

    output = run_powershell(command)

    if not output:
        return []

    return [
        line.strip()
        for line in output.splitlines()
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


def test_ping():
    result_data = {
        "internet": False,
        "ping": None,
        "packet_loss": None,
    }

    try:
        creationflags = 0

        if os.name == "nt":
            creationflags = subprocess.CREATE_NO_WINDOW

        result = subprocess.run(
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

        output = result.stdout.lower()

        if result.returncode == 0:
            result_data["internet"] = True

        times = []

        for line in output.splitlines():

            if "time=" in line:

                try:
                    after = line.split(
                        "time=", 1
                    )[1]

                    digits = ""

                    for char in after:

                        if char.isdigit():
                            digits += char

                        elif digits:
                            break

                    if digits:
                        times.append(
                            int(digits)
                        )

                except Exception:
                    pass

            elif "time<1ms" in line:
                times.append(1)

        if times:
            result_data["ping"] = (
                sum(times)
                // len(times)
            )

        for line in output.splitlines():

            if "%" in line:

                before = line.split("%")[0]
                digits = ""

                for char in reversed(before):

                    if char.isdigit():
                        digits = (
                            char + digits
                        )

                    elif digits:
                        break

                if digits:

                    try:
                        value = int(digits)

                        if 0 <= value <= 100:
                            result_data[
                                "packet_loss"
                            ] = value

                    except Exception:
                        pass

    except Exception:
        pass

    return result_data


def scan_network():
    ping_result = test_ping()

    return {
        "adapter": get_active_adapter(),
        "gateway": get_default_gateway(),
        "dns_servers": get_dns_servers(),
        "dns_ok": test_dns(),
        "internet": ping_result["internet"],
        "ping": ping_result["ping"],
        "packet_loss": ping_result["packet_loss"],
    }


# =========================================================
# WINDOWS EVENT LOG
# =========================================================

def scan_event_logs():

    command = r"""
    $start = (Get-Date).AddHours(-24)

    $events = Get-WinEvent -FilterHashtable @{
        LogName=@('System','Application')
        Level=@(1,2,3)
        StartTime=$start
    } -MaxEvents 40 -ErrorAction SilentlyContinue |
    Select-Object `
        TimeCreated,
        LogName,
        ProviderName,
        Id,
        LevelDisplayName,
        Message

    $events | ConvertTo-Json -Depth 3 -Compress
    """

    output = run_powershell(
        command,
        timeout=15,
    )

    if not output:
        return []

    try:
        data = json.loads(output)

        if isinstance(data, dict):
            data = [data]

    except Exception:
        return []

    events = []

    for item in data:

        if not isinstance(
            item,
            dict,
        ):
            continue

        message = (
            item.get("Message")
            or ""
        )

        message = (
            str(message)
            .replace("\r", " ")
            .replace("\n", " ")
        )

        if len(message) > 250:
            message = (
                message[:250]
                + "..."
            )

        events.append(
            {
                "time": (
                    item.get("TimeCreated")
                    or ""
                ),
                "log": (
                    item.get("LogName")
                    or "Unknown"
                ),
                "provider": (
                    item.get("ProviderName")
                    or "Unknown"
                ),
                "id": (
                    item.get("Id")
                    or 0
                ),
                "level": (
                    item.get("LevelDisplayName")
                    or "Unknown"
                ),
                "message": message,
            }
        )

    return events


# =========================================================
# SMART EVENT ANALYZER
# =========================================================

def analyze_event_logs(events):

    critical = 0
    errors = 0
    warnings = 0

    crashes = 0
    gpu_errors = 0
    disk_errors = 0
    shutdown_errors = 0
    hardware_errors = 0

    generic_errors = 0
    ignored_noise = 0

    important = []

    for event in events:

        level = str(
            event.get("level")
            or "Unknown"
        ).lower()

        provider = str(
            event.get("provider")
            or "Unknown"
        ).lower()

        message = str(
            event.get("message")
            or ""
        ).lower()

        try:
            event_id = int(
                event.get("id")
                or 0
            )

        except Exception:
            event_id = 0

        if "critical" in level:
            critical += 1

        elif "error" in level:
            errors += 1

        elif "warning" in level:
            warnings += 1

        is_noise = False

        if (
            "microsoft-windows-capi2"
            in provider
        ):
            is_noise = True

        elif (
            "distributedcom"
            in provider
            and event_id == 10016
        ):
            is_noise = True

        if is_noise:
            ignored_noise += 1
            continue

        category = None

        if (
            "whea" in provider
            or "hardware error"
            in message
        ):
            hardware_errors += 1
            category = "hardware"

        elif (
            event_id in (
                41,
                6008,
            )
            or "kernel-power"
            in provider
        ):
            shutdown_errors += 1
            category = "shutdown"

        elif (
            "display" in provider
            or "nvlddmkm" in provider
            or "amdwddmg" in provider
            or "dxgkrnl" in provider
            or "graphics driver"
            in message
        ):
            gpu_errors += 1
            category = "gpu"

        elif (
            "disk" in provider
            or "ntfs" in provider
            or "storahci" in provider
            or "stornvme" in provider
            or "volmgr" in provider
        ):
            disk_errors += 1
            category = "disk"

        elif (
            event_id == 1000
            or "application error"
            in provider
            or "application crash"
            in message
        ):
            crashes += 1
            category = "crash"

        elif (
            "critical" in level
            or "error" in level
        ):
            generic_errors += 1
            category = "generic"

        if (
            category is not None
            and len(important) < 8
        ):
            important.append(
                {
                    **event,
                    "category": category,
                }
            )

    return {
        "total": len(events),
        "critical": critical,
        "errors": errors,
        "warnings": warnings,

        "crashes": crashes,
        "gpu_errors": gpu_errors,
        "disk_errors": disk_errors,
        "shutdown_errors": shutdown_errors,
        "hardware_errors": hardware_errors,

        "generic_errors": generic_errors,
        "ignored_noise": ignored_noise,

        "important": important,
    }


# =========================================================
# DATA COLLECTION
# =========================================================

def collect_system_data():

    data = {}

    data["cpu"] = scan_cpu()
    data["memory"] = scan_memory()
    data["disks"] = scan_disks()
    data["gpu"] = scan_gpu()
    data["network"] = scan_network()
    data["processes"] = scan_top_processes(5)

    return data


# =========================================================
# INTERNET DOCTOR
# =========================================================

def doctor_internet(data):

    network = data["network"]

    score = 100
    findings = []

    if network["internet"]:

        findings.append(
            "Internet connection is working."
        )

    else:

        score -= 40

        findings.append(
            "Internet connectivity test failed."
        )

    if network["dns_ok"]:

        findings.append(
            "DNS resolution is working."
        )

    else:

        score -= 20

        findings.append(
            "DNS resolution problem detected."
        )

    ping = network["ping"]

    if ping is not None:

        if ping >= 150:

            score -= 25

            findings.append(
                f"Ping is very high ({ping} ms)."
            )

        elif ping >= 80:

            score -= 10

            findings.append(
                f"Ping is elevated ({ping} ms)."
            )

        else:

            findings.append(
                f"Ping is good ({ping} ms)."
            )

    packet_loss = network["packet_loss"]

    if packet_loss is not None:

        if packet_loss >= 10:

            score -= 25

            findings.append(
                f"High packet loss ({packet_loss}%)."
            )

        elif packet_loss >= 3:

            score -= 10

            findings.append(
                f"Packet loss detected ({packet_loss}%)."
            )

        else:

            findings.append(
                f"Packet loss is {packet_loss}%."
            )

    findings.append(
        "Adapter link speed: "
        + str(
            network[
                "adapter"
            ][
                "link_speed"
            ]
        )
    )

    return {
        "title": "Internet Doctor",
        "score": max(
            0,
            score,
        ),
        "findings": findings,
    }


# =========================================================
# GAMING DOCTOR
# =========================================================

def doctor_gaming(data):

    score = 100
    findings = []

    cpu = data["cpu"]

    ram = data[
        "memory"
    ][
        "percent"
    ]

    gpu = data["gpu"]

    if cpu >= 90:

        score -= 20

        findings.append(
            "CPU usage is very high."
        )

    elif cpu >= 75:

        score -= 10

        findings.append(
            f"CPU usage is elevated ({cpu:.0f}%)."
        )

    else:

        findings.append(
            f"CPU usage: {cpu:.0f}%."
        )

    if ram >= 90:

        score -= 25

        findings.append(
            "RAM usage is critically high."
        )

    elif ram >= 80:

        score -= 10

        findings.append(
            "RAM usage is high."
        )

    else:

        findings.append(
            f"RAM usage: {ram:.0f}%."
        )

    if gpu["usage"] is not None:

        findings.append(
            f'GPU usage: '
            f'{gpu["usage"]:.0f}%.'
        )

    if (
        gpu["temperature"]
        is not None
    ):

        temp = gpu[
            "temperature"
        ]

        if temp >= 90:

            score -= 25

            findings.append(
                f"GPU temperature "
                f"is critical "
                f"({temp:.0f}°C)."
            )

        elif temp >= 83:

            score -= 10

            findings.append(
                f"GPU temperature "
                f"is high "
                f"({temp:.0f}°C)."
            )

        else:

            findings.append(
                f"GPU temperature: "
                f"{temp:.0f}°C."
            )

    network = data["network"]

    if (
        network["ping"]
        is not None
        and network["ping"] >= 100
    ):

        score -= 10

        findings.append(
            f'Network latency may affect '
            f'online games '
            f'({network["ping"]} ms).'
        )

    if (
        network["packet_loss"]
        is not None
        and network["packet_loss"] >= 3
    ):

        score -= 15

        findings.append(
            f'Packet loss may cause lag '
            f'({network["packet_loss"]}%).'
        )

    return {
        "title": "Gaming Doctor",
        "score": max(
            0,
            score,
        ),
        "findings": findings,
    }


# =========================================================
# SLOW PC DOCTOR
# =========================================================

def doctor_slow_pc(data):

    score = 100
    findings = []

    cpu = data["cpu"]

    ram = data[
        "memory"
    ][
        "percent"
    ]

    if cpu >= 85:

        score -= 20

        findings.append(
            "High CPU usage may slow the PC."
        )

    else:

        findings.append(
            "CPU usage is normal."
        )

    if ram >= 90:

        score -= 25

        findings.append(
            "RAM is nearly full."
        )

    elif ram >= 80:

        score -= 10

        findings.append(
            "RAM usage is high."
        )

    else:

        findings.append(
            "RAM usage is normal."
        )

    if data["processes"]:

        top = data[
            "processes"
        ][0]

        findings.append(
            "Highest RAM process: "
            f'{top["name"]} '
            f'({format_bytes(top["memory"])}).'
        )

    for drive in data["disks"]:

        if drive["percent"] >= 95:

            score -= 20

            findings.append(
                f'{drive["device"]} '
                f'is almost full.'
            )

    return {
        "title": "Slow PC Doctor",
        "score": max(
            0,
            score,
        ),
        "findings": findings,
    }


# =========================================================
# STORAGE DOCTOR
# =========================================================

def doctor_storage(data):

    score = 100
    findings = []

    for drive in data["disks"]:

        free_gb = (
            drive["free"]
            / (1024 ** 3)
        )

        if free_gb < 5:

            score -= 25

            findings.append(
                f'{drive["device"]} '
                f'is critically low on space '
                f'({free_gb:.1f} GB free).'
            )

        elif free_gb < 15:

            score -= 10

            findings.append(
                f'{drive["device"]} '
                f'is running low on space '
                f'({free_gb:.1f} GB free).'
            )

        else:

            findings.append(
                f'{drive["device"]}: '
                f'{free_gb:.1f} GB free.'
            )

    return {
        "title": "Storage Doctor",
        "score": max(
            0,
            score,
        ),
        "findings": findings,
    }


# =========================================================
# WINDOWS EVENT DOCTOR
# =========================================================

def doctor_event_log():

    events = scan_event_logs()

    analysis = analyze_event_logs(
        events
    )

    score = 100
    findings = []

    findings.append(
        f'Recent events scanned: '
        f'{analysis["total"]}'
    )

    findings.append(
        f'Critical: '
        f'{analysis["critical"]}'
    )

    findings.append(
        f'Errors: '
        f'{analysis["errors"]}'
    )

    findings.append(
        f'Warnings: '
        f'{analysis["warnings"]}'
    )

    if (
        analysis["ignored_noise"]
        > 0
    ):

        findings.append(
            f'Background/noise events ignored: '
            f'{analysis["ignored_noise"]}'
        )

    if analysis[
        "hardware_errors"
    ]:

        penalty = min(
            40,
            analysis[
                "hardware_errors"
            ] * 25,
        )

        score -= penalty

        findings.append(
            f'Hardware/WHEA events: '
            f'{analysis["hardware_errors"]}'
        )

    if analysis[
        "disk_errors"
    ]:

        penalty = min(
            30,
            analysis[
                "disk_errors"
            ] * 15,
        )

        score -= penalty

        findings.append(
            f'Disk/storage related events: '
            f'{analysis["disk_errors"]}'
        )

    if analysis[
        "shutdown_errors"
    ]:

        penalty = min(
            30,
            analysis[
                "shutdown_errors"
            ] * 15,
        )

        score -= penalty

        findings.append(
            f'Unexpected shutdown events: '
            f'{analysis["shutdown_errors"]}'
        )

    if analysis[
        "gpu_errors"
    ]:

        penalty = min(
            20,
            analysis[
                "gpu_errors"
            ] * 10,
        )

        score -= penalty

        findings.append(
            f'Display/GPU related events: '
            f'{analysis["gpu_errors"]}'
        )

    if analysis[
        "crashes"
    ]:

        penalty = min(
            15,
            analysis[
                "crashes"
            ] * 5,
        )

        score -= penalty

        findings.append(
            f'Application crashes detected: '
            f'{analysis["crashes"]}'
        )

    if analysis[
        "generic_errors"
    ]:

        penalty = min(
            5,
            analysis[
                "generic_errors"
            ],
        )

        score -= penalty

        findings.append(
            f'Other Windows errors: '
            f'{analysis["generic_errors"]}'
        )

    if analysis[
        "important"
    ]:

        findings.append("")
        findings.append(
            "Important events:"
        )

        category_names = {
            "hardware": "Hardware",
            "shutdown": "Shutdown",
            "gpu": "GPU",
            "disk": "Storage",
            "crash": "Application Crash",
            "generic": "Windows",
        }

        for event in analysis[
            "important"
        ][:5]:

            category = (
                category_names.get(
                    event.get(
                        "category"
                    ),
                    "Windows",
                )
            )

            findings.append(
                f'[{category}] '
                f'{event["provider"]} '
                f'(ID {event["id"]})'
            )

    serious_count = (
        analysis[
            "hardware_errors"
        ]
        + analysis[
            "disk_errors"
        ]
        + analysis[
            "shutdown_errors"
        ]
        + analysis[
            "gpu_errors"
        ]
        + analysis[
            "crashes"
        ]
    )

    if serious_count == 0:

        findings.append("")

        findings.append(
            "No serious hardware, GPU, "
            "disk, shutdown or application "
            "crash events were detected."
        )

    if not events:

        findings.append(
            "No recent Windows events were available."
        )

    return {
        "title": "Windows Event Doctor",
        "score": max(
            0,
            score,
        ),
        "findings": findings,
    }


# =========================================================
# FULL SYSTEM SCAN
# =========================================================

def doctor_full(data):

    internet = doctor_internet(
        data
    )

    gaming = doctor_gaming(
        data
    )

    slow_pc = doctor_slow_pc(
        data
    )

    storage = doctor_storage(
        data
    )

    event_log = doctor_event_log()

    scores = [
        internet["score"],
        gaming["score"],
        slow_pc["score"],
        storage["score"],
        event_log["score"],
    ]

    overall = (
        sum(scores)
        // len(scores)
    )

    findings = [
        (
            f'Internet Doctor: '
            f'{internet["score"]}/100'
        ),
        (
            f'Gaming Doctor: '
            f'{gaming["score"]}/100'
        ),
        (
            f'Slow PC Doctor: '
            f'{slow_pc["score"]}/100'
        ),
        (
            f'Storage Doctor: '
            f'{storage["score"]}/100'
        ),
        (
            f'Windows Event Doctor: '
            f'{event_log["score"]}/100'
        ),
    ]

    return {
        "title": "Full System Scan",
        "score": overall,
        "findings": findings,
    }


# =========================================================
# WORKER THREAD
# =========================================================

class DoctorWorker(QThread):

    finished = Signal(dict)

    def __init__(
        self,
        mode,
    ):

        super().__init__()

        self.mode = mode

    def run(self):

        if self.mode == "events":

            result = doctor_event_log()

        else:

            data = collect_system_data()

            if self.mode == "internet":

                result = doctor_internet(
                    data
                )

            elif self.mode == "gaming":

                result = doctor_gaming(
                    data
                )

            elif self.mode == "slow":

                result = doctor_slow_pc(
                    data
                )

            elif self.mode == "storage":

                result = doctor_storage(
                    data
                )

            else:

                result = doctor_full(
                    data
                )

        self.finished.emit(
            result
        )


# =========================================================
# UI COMPONENTS
# =========================================================

class DoctorButton(QPushButton):

    def __init__(
        self,
        title,
        subtitle,
    ):

        super().__init__()

        self.setText(
            f"{title}\n{subtitle}"
        )

        self.setObjectName(
            "DoctorButton"
        )

        self.setMinimumHeight(
            85
        )


class ResultCard(QFrame):

    def __init__(self):

        super().__init__()

        self.setObjectName(
            "ResultCard"
        )

        layout = QVBoxLayout(
            self
        )

        self.title = QLabel(
            "Doctor Result"
        )

        self.title.setObjectName(
            "ResultTitle"
        )

        self.score = QLabel("--")

        self.score.setObjectName(
            "ResultScore"
        )

        self.details = QLabel(
            "Choose a Doctor Mode above to start a scan."
        )

        self.details.setWordWrap(
            True
        )

        self.details.setObjectName(
            "ResultDetails"
        )

        layout.addWidget(
            self.title
        )

        layout.addWidget(
            self.score
        )

        layout.addWidget(
            self.details
        )


class InfoCard(QFrame):

    def __init__(
        self,
        title,
        text,
    ):

        super().__init__()

        self.setObjectName(
            "InfoCard"
        )

        layout = QVBoxLayout(
            self
        )

        title_label = QLabel(
            title
        )

        title_label.setObjectName(
            "InfoTitle"
        )

        text_label = QLabel(
            text
        )

        text_label.setObjectName(
            "InfoText"
        )

        text_label.setWordWrap(
            True
        )

        layout.addWidget(
            title_label
        )

        layout.addWidget(
            text_label
        )


# =========================================================
# MAIN WINDOW
# =========================================================

class OpenFixWindow(QMainWindow):

    def __init__(self):

        super().__init__()

        self.setWindowTitle(
            f"OpenFix AI v{APP_VERSION}"
        )

        self.resize(
            1100,
            900,
        )

        scroll = QScrollArea()

        scroll.setWidgetResizable(
            True
        )

        scroll.setFrameShape(
            QFrame.NoFrame
        )

        self.setCentralWidget(
            scroll
        )

        root = QWidget()

        root.setObjectName(
            "RootWidget"
        )

        scroll.setWidget(
            root
        )

        layout = QVBoxLayout(
            root
        )

        layout.setContentsMargins(
            30,
            25,
            30,
            35,
        )

        layout.setSpacing(
            18
        )

        header = QLabel(
            "OpenFix AI"
        )

        header.setObjectName(
            "Header"
        )

        subtitle = QLabel(
            "Understand your PC before trying to fix it."
        )

        subtitle.setObjectName(
            "Subtitle"
        )

        version = QLabel(
            f"Diagnostic Engine v{APP_VERSION}"
        )

        version.setObjectName(
            "Version"
        )

        layout.addWidget(
            header
        )

        layout.addWidget(
            subtitle
        )

        layout.addWidget(
            version
        )

        help_row = QHBoxLayout()

        self.guide_btn = QPushButton(
            "How to Use"
        )

        self.guide_btn.setObjectName(
            "TopButton"
        )

        self.safety_btn = QPushButton(
            "Safety & Warnings"
        )

        self.safety_btn.setObjectName(
            "WarningButton"
        )

        help_row.addWidget(
            self.guide_btn
        )

        help_row.addWidget(
            self.safety_btn
        )

        layout.addLayout(
            help_row
        )

        score_card = InfoCard(
            "Health Score Guide",
            (
                "90-100  Healthy / no major issue detected\n"
                "75-89   Minor issues or items worth checking\n"
                "50-74   Needs attention\n"
                "0-49    Serious problems may be present\n\n"
                "Important: The score is only an estimate. "
                "A high score does not guarantee that the PC "
                "has no hardware or software problems."
            ),
        )

        layout.addWidget(
            score_card
        )

        row1 = QHBoxLayout()

        self.internet_btn = DoctorButton(
            "Internet Doctor",
            "Ping, DNS, packet loss, network",
        )

        self.gaming_btn = DoctorButton(
            "Gaming Doctor",
            "CPU, RAM, GPU, performance",
        )

        row1.addWidget(
            self.internet_btn
        )

        row1.addWidget(
            self.gaming_btn
        )

        layout.addLayout(
            row1
        )

        row2 = QHBoxLayout()

        self.slow_btn = DoctorButton(
            "Slow PC Doctor",
            "Find common performance problems",
        )

        self.storage_btn = DoctorButton(
            "Storage Doctor",
            "Check disk space and drives",
        )

        row2.addWidget(
            self.slow_btn
        )

        row2.addWidget(
            self.storage_btn
        )

        layout.addLayout(
            row2
        )

        self.event_btn = DoctorButton(
            "Windows Event Doctor",
            (
                "Crashes, driver errors, "
                "shutdowns and hardware events"
            ),
        )

        layout.addWidget(
            self.event_btn
        )

        self.full_btn = DoctorButton(
            "Full System Scan",
            "Run all diagnostic doctors",
        )

        layout.addWidget(
            self.full_btn
        )

        self.progress = QProgressBar()

        self.progress.setRange(
            0,
            0,
        )

        self.progress.hide()

        layout.addWidget(
            self.progress
        )

        self.result_card = ResultCard()

        layout.addWidget(
            self.result_card
        )

        disclaimer = InfoCard(
            "Important Notice",
            (
                "OpenFix AI is currently a diagnostic tool. "
                "It does not guarantee that every PC problem "
                "will be detected.\n\n"
                "Do not delete system files, modify the Registry, "
                "disable Windows services, uninstall drivers or "
                "change advanced settings only because of one "
                "diagnostic result.\n\n"
                "If a serious hardware problem is suspected, "
                "confirm the result with dedicated diagnostic "
                "software or a qualified technician."
            ),
        )

        layout.addWidget(
            disclaimer
        )

        footer = QLabel(
            "OpenFix AI • Read-only diagnostic mode"
        )

        footer.setObjectName(
            "Footer"
        )

        layout.addWidget(
            footer
        )

        self.guide_btn.clicked.connect(
            self.show_guide
        )

        self.safety_btn.clicked.connect(
            self.show_safety
        )

        self.internet_btn.clicked.connect(
            lambda:
            self.start_doctor(
                "internet"
            )
        )

        self.gaming_btn.clicked.connect(
            lambda:
            self.start_doctor(
                "gaming"
            )
        )

        self.slow_btn.clicked.connect(
            lambda:
            self.start_doctor(
                "slow"
            )
        )

        self.storage_btn.clicked.connect(
            lambda:
            self.start_doctor(
                "storage"
            )
        )

        self.event_btn.clicked.connect(
            lambda:
            self.start_doctor(
                "events"
            )
        )

        self.full_btn.clicked.connect(
            lambda:
            self.start_doctor(
                "full"
            )
        )

        self.apply_style()


    # =====================================================
    # HOW TO USE
    # =====================================================

    def show_guide(self):

        text = (
            "HOW TO USE OPENFIX AI\n\n"
            "1. Choose the Doctor that matches your problem.\n\n"

            "INTERNET DOCTOR\n"
            "Use when your internet is slow, unstable, "
            "has high ping, packet loss or DNS problems.\n\n"

            "GAMING DOCTOR\n"
            "Use when games stutter, FPS drops, "
            "performance feels poor or the PC is under heavy load.\n\n"

            "SLOW PC DOCTOR\n"
            "Use when Windows feels slow, "
            "programs open slowly or the computer is lagging.\n\n"

            "STORAGE DOCTOR\n"
            "Use when drives are nearly full "
            "or you want to check available disk space.\n\n"

            "WINDOWS EVENT DOCTOR\n"
            "Use when games or programs crash, "
            "Windows restarts unexpectedly, "
            "or you suspect driver or hardware errors.\n\n"

            "FULL SYSTEM SCAN\n"
            "Runs all available diagnostic Doctors "
            "and calculates an overall score.\n\n"

            "After scanning:\n"
            "• Read the findings carefully.\n"
            "• Treat the score as guidance, not proof.\n"
            "• Avoid advanced Windows changes unless you "
            "understand exactly what they do."
        )

        QMessageBox.information(
            self,
            "How to Use OpenFix AI",
            text,
        )


    # =====================================================
    # SAFETY
    # =====================================================

    def show_safety(self):

        text = (
            "OPENFIX AI SAFETY & WARNINGS\n\n"

            "• OpenFix AI currently performs "
            "read-only diagnostics.\n\n"

            "• A low score does not automatically mean "
            "that hardware is failing.\n\n"

            "• A score of 100 does not guarantee that "
            "the computer has no problems.\n\n"

            "• Windows Event Viewer normally contains "
            "some warnings and errors even on healthy systems.\n\n"

            "• Do not delete Windows system files because "
            "of one diagnostic result.\n\n"

            "• Do not modify the Windows Registry unless "
            "you know exactly what the change does.\n\n"

            "• Do not disable Windows services randomly.\n\n"

            "• Do not remove or downgrade drivers without "
            "understanding the consequences.\n\n"

            "• Creating a Windows Restore Point is recommended "
            "before future advanced repair features.\n\n"

            "• Suspected hardware failures should be confirmed "
            "using dedicated diagnostic tools."
        )

        QMessageBox.warning(
            self,
            "Safety & Warnings",
            text,
        )


    # =====================================================
    # STYLE
    # =====================================================

    def apply_style(self):

        self.setStyleSheet("""
            QMainWindow {
                background: #1d1f21;
            }

            #RootWidget {
                background: #1d1f21;
            }

            QScrollArea {
                background: #1d1f21;
                border: none;
            }

            QWidget {
                font-family: Segoe UI;
            }

            #Header {
                font-size: 32px;
                font-weight: 800;
                color: #ffffff;
            }

            #Subtitle {
                font-size: 15px;
                color: #d1d5db;
            }

            #Version {
                font-size: 12px;
                color: #9ca3af;
            }

            #TopButton {
                background: #2563eb;
                color: white;
                border: none;
                border-radius: 10px;
                padding: 12px;
                font-size: 14px;
                font-weight: 700;
            }

            #TopButton:hover {
                background: #1d4ed8;
            }

            #WarningButton {
                background: #b45309;
                color: white;
                border: none;
                border-radius: 10px;
                padding: 12px;
                font-size: 14px;
                font-weight: 700;
            }

            #WarningButton:hover {
                background: #92400e;
            }

            #DoctorButton {
                background: #ffffff;
                border: 1px solid #e5e7eb;
                border-radius: 14px;
                padding: 16px;
                text-align: left;
                font-size: 15px;
                font-weight: 600;
                color: #111827;
            }

            #DoctorButton:hover {
                background: #f3f4f6;
                border: 1px solid #9ca3af;
            }

            #DoctorButton:disabled {
                color: #9ca3af;
            }

            #ResultCard {
                background: #ffffff;
                border-radius: 16px;
                padding: 18px;
            }

            #ResultTitle {
                font-size: 22px;
                font-weight: 700;
                color: #111827;
            }

            #ResultScore {
                font-size: 42px;
                font-weight: 800;
                color: #111827;
            }

            #ResultDetails {
                font-size: 14px;
                color: #4b5563;
            }

            #InfoCard {
                background: #292c30;
                border: 1px solid #3f444b;
                border-radius: 14px;
                padding: 12px;
            }

            #InfoTitle {
                font-size: 16px;
                font-weight: 700;
                color: #ffffff;
            }

            #InfoText {
                font-size: 13px;
                color: #d1d5db;
            }

            #Footer {
                color: #9ca3af;
                font-size: 12px;
            }

            QProgressBar {
                border: none;
                background: #374151;
                border-radius: 5px;
                height: 8px;
            }

            QMessageBox {
                background: #f9fafb;
            }

            QMessageBox QLabel {
                color: #111827;
                min-width: 540px;
            }
        """)


    # =====================================================
    # BUTTON STATE
    # =====================================================

    def set_buttons_enabled(
        self,
        enabled,
    ):

        self.internet_btn.setEnabled(
            enabled
        )

        self.gaming_btn.setEnabled(
            enabled
        )

        self.slow_btn.setEnabled(
            enabled
        )

        self.storage_btn.setEnabled(
            enabled
        )

        self.event_btn.setEnabled(
            enabled
        )

        self.full_btn.setEnabled(
            enabled
        )


    # =====================================================
    # START DOCTOR
    # =====================================================

    def start_doctor(
        self,
        mode,
    ):

        self.set_buttons_enabled(
            False
        )

        self.progress.show()

        self.result_card.title.setText(
            "Scanning..."
        )

        self.result_card.score.setText(
            "--"
        )

        self.result_card.details.setText(
            "Collecting diagnostic data. Please wait."
        )

        self.worker = DoctorWorker(
            mode
        )

        self.worker.finished.connect(
            self.doctor_complete
        )

        self.worker.start()


    # =====================================================
    # RESULT
    # =====================================================

    def doctor_complete(
        self,
        result,
    ):

        self.progress.hide()

        self.set_buttons_enabled(
            True
        )

        self.result_card.title.setText(
            result["title"]
        )

        self.result_card.score.setText(
            f'{result["score"]}/100'
        )

        lines = []

        for item in result[
            "findings"
        ]:

            if item == "":

                lines.append("")

            else:

                lines.append(
                    f"• {item}"
                )

        lines.append("")

        lines.append(
            "Note: This diagnostic result is an estimate "
            "and should be used as guidance."
        )

        self.result_card.details.setText(
            "\n".join(
                lines
            )
        )


# =========================================================
# START APPLICATION
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