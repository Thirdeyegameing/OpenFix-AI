import sys
import os
import socket
import subprocess
import json
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
)


APP_VERSION = "0.2.0"


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

def run_powershell(command):
    """
    Run a PowerShell command silently and return stdout.
    """
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
            timeout=12,
        )

        return result.stdout.strip()

    except Exception:
        return ""


def get_system_drive():
    return os.environ.get("SystemDrive", "C:") + "\\"


# =========================================================
# SYSTEM SCANNERS
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

        device = partition.device

        if not device:
            continue

        if device in seen:
            continue

        seen.add(device)

        try:
            usage = psutil.disk_usage(partition.mountpoint)

            drives.append(
                {
                    "device": device,
                    "mountpoint": partition.mountpoint,
                    "fstype": partition.fstype,
                    "total": usage.total,
                    "used": usage.used,
                    "free": usage.free,
                    "percent": usage.percent,
                }
            )

        except (
            PermissionError,
            FileNotFoundError,
            OSError,
        ):
            pass

    return drives


def scan_top_processes(limit=5):
    processes = []

    for proc in psutil.process_iter(
        ["pid", "name", "memory_info"]
    ):

        try:
            info = proc.info

            if info["memory_info"] is None:
                continue

            memory = info["memory_info"].rss

            processes.append(
                {
                    "name": info["name"] or "Unknown",
                    "pid": info["pid"],
                    "memory": memory,
                }
            )

        except (
            psutil.NoSuchProcess,
            psutil.AccessDenied,
            psutil.ZombieProcess,
        ):
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

    # -------------------------
    # Get basic GPU data
    # -------------------------

    ps_command = r"""
    $gpus = Get-CimInstance Win32_VideoController |
    Select-Object Name, AdapterRAM, DriverVersion

    $gpus | ConvertTo-Json -Compress
    """

    output = run_powershell(ps_command)

    if output:

        try:
            data = json.loads(output)

            if isinstance(data, list):
                data = data[0]

            gpu["name"] = data.get("Name", "Unknown")
            gpu["vram"] = data.get("AdapterRAM")
            gpu["driver"] = data.get("DriverVersion")

        except Exception:
            pass

    # -------------------------
    # NVIDIA extra info
    # -------------------------

    try:
        creationflags = 0

        if os.name == "nt":
            creationflags = subprocess.CREATE_NO_WINDOW

        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,"
                "utilization.gpu,temperature.gpu,"
                "driver_version",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            creationflags=creationflags,
            timeout=5,
        )

        if result.returncode == 0:

            line = result.stdout.strip().splitlines()[0]

            parts = [
                item.strip()
                for item in line.split(",")
            ]

            if len(parts) >= 5:

                gpu["name"] = parts[0]

                try:
                    gpu["vram"] = (
                        float(parts[1]) * 1024 * 1024
                    )
                except Exception:
                    pass

                try:
                    gpu["usage"] = float(parts[2])
                except Exception:
                    pass

                try:
                    gpu["temperature"] = float(parts[3])
                except Exception:
                    pass

                gpu["driver"] = parts[4]

    except Exception:
        pass

    return gpu


# =========================================================
# NETWORK
# =========================================================

def get_default_gateway():
    command = r"""
    $route = Get-NetRoute -DestinationPrefix "0.0.0.0/0" |
    Where-Object {$_.NextHop -ne "0.0.0.0"} |
    Sort-Object RouteMetric |
    Select-Object -First 1 -ExpandProperty NextHop

    $route
    """

    output = run_powershell(command)

    return output if output else "Unknown"


def get_dns_servers():
    command = r"""
    $dns =
    Get-DnsClientServerAddress -AddressFamily IPv4 |
    Where-Object {$_.ServerAddresses.Count -gt 0} |
    Select-Object -ExpandProperty ServerAddresses

    $dns | Select-Object -Unique
    """

    output = run_powershell(command)

    if not output:
        return []

    return [
        line.strip()
        for line in output.splitlines()
        if line.strip()
    ]


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
                data.get("Name") or "Unknown"
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

        # -------------------------
        # Ping average
        # -------------------------

        marker = "average ="

        if marker in output:

            after = output.split(marker, 1)[1]

            number = ""

            for char in after:

                if char.isdigit():
                    number += char

                elif number:
                    break

            if number:
                result_data["ping"] = int(number)

        # Thai Windows may not use "average ="
        # Try to extract last ms fallback.

        if result_data["ping"] is None:

            lines = output.splitlines()

            times = []

            for line in lines:

                if "ms" in line and "1.1.1.1" in line:

                    if "time=" in line:

                        try:
                            part = line.split("time=", 1)[1]
                            digits = ""

                            for char in part:

                                if char.isdigit():
                                    digits += char

                                elif digits:
                                    break

                            if digits:
                                times.append(int(digits))

                        except Exception:
                            pass

                    elif "time<1ms" in line:
                        times.append(1)

            if times:
                result_data["ping"] = (
                    sum(times) // len(times)
                )

        # -------------------------
        # Packet loss
        # -------------------------

        if "lost =" in output:

            try:
                lost_part = output.split(
                    "lost =", 1
                )[1]

                inside = lost_part.split(
                    "(", 1
                )[1].split("%", 1)[0]

                digits = "".join(
                    char
                    for char in inside
                    if char.isdigit()
                )

                if digits:
                    result_data["packet_loss"] = int(
                        digits
                    )

            except Exception:
                pass

        # fallback for "% loss"
        if result_data["packet_loss"] is None:

            for line in output.splitlines():

                if "%" in line:

                    try:
                        before = line.split("%")[0]

                        digits = ""

                        for char in reversed(before):

                            if char.isdigit():
                                digits = char + digits

                            elif digits:
                                break

                        if digits:

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


def test_dns():
    try:
        socket.gethostbyname("cloudflare.com")
        return True
    except Exception:
        return False


def scan_network():

    adapter = get_active_adapter()

    gateway = get_default_gateway()

    dns_servers = get_dns_servers()

    ping_result = test_ping()

    dns_ok = test_dns()

    return {
        "adapter": adapter,
        "gateway": gateway,
        "dns_servers": dns_servers,
        "dns_ok": dns_ok,
        "internet": ping_result["internet"],
        "ping": ping_result["ping"],
        "packet_loss": ping_result["packet_loss"],
    }


# =========================================================
# ANALYZER
# =========================================================

def analyze_system(data):

    issues = []
    recommendations = []

    score = 100

    cpu = data["cpu"]
    ram = data["memory"]["percent"]

    # CPU
    if cpu >= 95:

        score -= 20

        issues.append(
            "CPU usage is extremely high."
        )

        recommendations.append(
            "Check applications using high CPU."
        )

    elif cpu >= 80:

        score -= 10

        issues.append(
            "CPU usage is currently high."
        )

    # RAM
    if ram >= 95:

        score -= 25

        issues.append(
            "Memory usage is critically high."
        )

        recommendations.append(
            "Close unnecessary applications."
        )

    elif ram >= 85:

        score -= 12

        issues.append(
            "Memory usage is high."
        )

    # Disk
    for drive in data["disks"]:

        free_gb = drive["free"] / (1024 ** 3)

        if free_gb < 5:

            score -= 20

            issues.append(
                f'{drive["device"]} has less '
                f'than 5 GB free.'
            )

            recommendations.append(
                f'Free up space on '
                f'{drive["device"]}.'
            )

        elif free_gb < 15:

            score -= 8

            issues.append(
                f'{drive["device"]} is running '
                f'low on free space.'
            )

    # Network
    network = data["network"]

    if not network["internet"]:

        score -= 25

        issues.append(
            "Internet connectivity test failed."
        )

    if not network["dns_ok"]:

        score -= 10

        issues.append(
            "DNS resolution test failed."
        )

        recommendations.append(
            "Check DNS configuration."
        )

    packet_loss = network["packet_loss"]

    if packet_loss is not None:

        if packet_loss >= 10:

            score -= 20

            issues.append(
                f"High packet loss detected "
                f"({packet_loss}%)."
            )

        elif packet_loss >= 3:

            score -= 8

            issues.append(
                f"Packet loss detected "
                f"({packet_loss}%)."
            )

    ping = network["ping"]

    if ping is not None:

        if ping >= 150:

            score -= 12

            issues.append(
                f"Network latency is high "
                f"({ping} ms)."
            )

        elif ping >= 80:

            score -= 5

            issues.append(
                f"Network latency is elevated "
                f"({ping} ms)."
            )

    # GPU
    gpu_temp = data["gpu"]["temperature"]

    if gpu_temp is not None:

        if gpu_temp >= 90:

            score -= 20

            issues.append(
                f"GPU temperature is critically "
                f"high ({gpu_temp:.0f}°C)."
            )

        elif gpu_temp >= 83:

            score -= 8

            issues.append(
                f"GPU temperature is high "
                f"({gpu_temp:.0f}°C)."
            )

    if not issues:

        recommendations.append(
            "No critical problems were detected."
        )

    score = max(0, score)

    return {
        "score": score,
        "issues": issues,
        "recommendations": recommendations,
    }


# =========================================================
# WORKER THREAD
# =========================================================

class ScanWorker(QThread):

    finished = Signal(dict)

    def run(self):

        data = {}

        data["cpu"] = scan_cpu()
        data["memory"] = scan_memory()
        data["disks"] = scan_disks()
        data["gpu"] = scan_gpu()
        data["network"] = scan_network()
        data["processes"] = scan_top_processes(5)

        data["analysis"] = analyze_system(data)

        self.finished.emit(data)


# =========================================================
# UI COMPONENTS
# =========================================================

class StatusCard(QFrame):

    def __init__(self, title):

        super().__init__()

        self.setObjectName("StatusCard")

        layout = QVBoxLayout(self)

        layout.setContentsMargins(
            20, 16, 20, 16
        )

        self.title = QLabel(title)
        self.title.setObjectName("CardTitle")

        self.status = QLabel(
            "Waiting for scan..."
        )

        self.status.setObjectName(
            "CardStatus"
        )

        self.detail = QLabel("")
        self.detail.setObjectName(
            "CardDetail"
        )

        self.detail.setWordWrap(True)

        layout.addWidget(self.title)
        layout.addWidget(self.status)
        layout.addWidget(self.detail)


class OpenFixWindow(QMainWindow):

    def __init__(self):

        super().__init__()

        self.setWindowTitle(
            f"OpenFix AI v{APP_VERSION}"
        )

        self.resize(1200, 850)

        # -------------------------
        # Scroll area
        # -------------------------

        scroll = QScrollArea()

        scroll.setWidgetResizable(True)

        scroll.setFrameShape(
            QFrame.NoFrame
        )

        self.setCentralWidget(scroll)

        root = QWidget()

        scroll.setWidget(root)

        layout = QVBoxLayout(root)

        layout.setContentsMargins(
            30, 25, 30, 35
        )

        layout.setSpacing(16)

        # -------------------------
        # Header
        # -------------------------

        header = QLabel("OpenFix AI")

        header.setObjectName("Header")

        subtitle = QLabel(
            "Understand what's wrong "
            "with your PC."
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

        layout.addWidget(header)
        layout.addWidget(subtitle)
        layout.addWidget(version)

        # -------------------------
        # Health
        # -------------------------

        health_frame = QFrame()

        health_frame.setObjectName(
            "HealthFrame"
        )

        health_layout = QVBoxLayout(
            health_frame
        )

        health_title = QLabel(
            "PC HEALTH"
        )

        health_title.setAlignment(
            Qt.AlignCenter
        )

        health_title.setObjectName(
            "HealthTitle"
        )

        self.health_score = QLabel("--")

        self.health_score.setAlignment(
            Qt.AlignCenter
        )

        self.health_score.setObjectName(
            "HealthScore"
        )

        health_layout.addWidget(
            health_title
        )

        health_layout.addWidget(
            self.health_score
        )

        layout.addWidget(health_frame)

        # -------------------------
        # Scan button
        # -------------------------

        self.scan_button = QPushButton(
            "SCAN MY PC"
        )

        self.scan_button.setObjectName(
            "ScanButton"
        )

        self.scan_button.clicked.connect(
            self.start_scan
        )

        layout.addWidget(
            self.scan_button
        )

        self.progress = QProgressBar()

        self.progress.setRange(0, 0)

        self.progress.hide()

        layout.addWidget(
            self.progress
        )

        # -------------------------
        # CPU + Memory
        # -------------------------

        row1 = QHBoxLayout()

        self.cpu_card = StatusCard(
            "CPU"
        )

        self.ram_card = StatusCard(
            "Memory"
        )

        row1.addWidget(
            self.cpu_card
        )

        row1.addWidget(
            self.ram_card
        )

        layout.addLayout(row1)

        # -------------------------
        # GPU + Network
        # -------------------------

        row2 = QHBoxLayout()

        self.gpu_card = StatusCard(
            "GPU"
        )

        self.network_card = StatusCard(
            "Network"
        )

        row2.addWidget(
            self.gpu_card
        )

        row2.addWidget(
            self.network_card
        )

        layout.addLayout(row2)

        # -------------------------
        # Storage
        # -------------------------

        self.storage_card = StatusCard(
            "Storage"
        )

        layout.addWidget(
            self.storage_card
        )

        # -------------------------
        # Processes
        # -------------------------

        self.process_card = StatusCard(
            "Top Memory Processes"
        )

        layout.addWidget(
            self.process_card
        )

        # -------------------------
        # Issues
        # -------------------------

        self.issues_card = StatusCard(
            "Issues Found"
        )

        layout.addWidget(
            self.issues_card
        )

        # -------------------------
        # Recommendations
        # -------------------------

        self.recommend_card = StatusCard(
            "Recommendations"
        )

        layout.addWidget(
            self.recommend_card
        )

        layout.addStretch()

        footer = QLabel(
            "OpenFix AI • "
            "Read-only diagnostic mode"
        )

        footer.setObjectName(
            "Footer"
        )

        layout.addWidget(
            footer
        )

        self.apply_style()

    # =====================================================
    # STYLE
    # =====================================================

    def apply_style(self):

        self.setStyleSheet("""
            QMainWindow {
                background: #f3f5f7;
            }

            QScrollArea {
                background: #f3f5f7;
                border: none;
            }

            QWidget {
                font-family: Segoe UI;
            }

            #Header {
                font-size: 30px;
                font-weight: 700;
                color: #15171a;
            }

            #Subtitle {
                font-size: 14px;
                color: #6b7280;
            }

            #Version {
                font-size: 12px;
                color: #9ca3af;
            }

            #HealthFrame {
                background: white;
                border-radius: 16px;
                padding: 12px;
            }

            #HealthTitle {
                color: #6b7280;
                font-size: 13px;
                font-weight: 600;
            }

            #HealthScore {
                font-size: 52px;
                font-weight: 800;
                color: #111827;
            }

            #ScanButton {
                background: #111827;
                color: white;
                border: none;
                padding: 15px;
                border-radius: 10px;
                font-size: 15px;
                font-weight: 700;
            }

            #ScanButton:hover {
                background: #262d3a;
            }

            #ScanButton:disabled {
                background: #9ca3af;
            }

            #StatusCard {
                background: white;
                border-radius: 14px;
                padding: 8px;
            }

            #CardTitle {
                color: #6b7280;
                font-size: 13px;
                font-weight: 600;
            }

            #CardStatus {
                color: #111827;
                font-size: 20px;
                font-weight: 700;
                margin-top: 5px;
            }

            #CardDetail {
                color: #6b7280;
                font-size: 13px;
            }

            #Footer {
                color: #9ca3af;
                font-size: 12px;
            }

            QProgressBar {
                border: none;
                background: #e5e7eb;
                border-radius: 5px;
                height: 7px;
            }
        """)

    # =====================================================
    # SCAN
    # =====================================================

    def start_scan(self):

        self.scan_button.setEnabled(
            False
        )

        self.scan_button.setText(
            "SCANNING..."
        )

        self.progress.show()

        self.worker = ScanWorker()

        self.worker.finished.connect(
            self.scan_complete
        )

        self.worker.start()

    # =====================================================
    # RESULTS
    # =====================================================

    def scan_complete(self, data):

        self.progress.hide()

        self.scan_button.setEnabled(
            True
        )

        self.scan_button.setText(
            "SCAN AGAIN"
        )

        # -------------------------
        # Health
        # -------------------------

        score = data["analysis"]["score"]

        self.health_score.setText(
            str(score)
        )

        # -------------------------
        # CPU
        # -------------------------

        cpu = data["cpu"]

        if cpu >= 90:
            cpu_status = "Critical"

        elif cpu >= 75:
            cpu_status = "High"

        else:
            cpu_status = "Normal"

        self.cpu_card.status.setText(
            f"{cpu_status} • {cpu:.0f}%"
        )

        self.cpu_card.detail.setText(
            "Current processor usage"
        )

        # -------------------------
        # Memory
        # -------------------------

        memory = data["memory"]

        ram = memory["percent"]

        if ram >= 90:
            ram_status = "Critical"

        elif ram >= 80:
            ram_status = "High"

        else:
            ram_status = "Normal"

        self.ram_card.status.setText(
            f"{ram_status} • {ram:.0f}%"
        )

        self.ram_card.detail.setText(
            f'{format_bytes(memory["used"])} used '
            f'of {format_bytes(memory["total"])}'
        )

        # -------------------------
        # GPU
        # -------------------------

        gpu = data["gpu"]

        gpu_status = gpu["name"]

        details = []

        if gpu["vram"]:

            details.append(
                f'VRAM: '
                f'{format_bytes(gpu["vram"])}'
            )

        if gpu["usage"] is not None:

            details.append(
                f'Usage: '
                f'{gpu["usage"]:.0f}%'
            )

        if gpu["temperature"] is not None:

            details.append(
                f'Temp: '
                f'{gpu["temperature"]:.0f}°C'
            )

        if gpu["driver"]:

            details.append(
                f'Driver: {gpu["driver"]}'
            )

        self.gpu_card.status.setText(
            gpu_status
        )

        self.gpu_card.detail.setText(
            " • ".join(details)
            if details
            else "GPU information detected"
        )

        # -------------------------
        # Network
        # -------------------------

        network = data["network"]

        adapter = network["adapter"]

        if network["internet"]:

            network_status = "Online"

        else:

            network_status = "Offline"

        net_details = []

        net_details.append(
            f'Adapter: {adapter["name"]}'
        )

        net_details.append(
            f'Link: {adapter["link_speed"]}'
        )

        net_details.append(
            f'Gateway: {network["gateway"]}'
        )

        if network["ping"] is not None:

            net_details.append(
                f'Ping: '
                f'{network["ping"]} ms'
            )

        if (
            network["packet_loss"]
            is not None
        ):

            net_details.append(
                f'Packet loss: '
                f'{network["packet_loss"]}%'
            )

        if network["dns_servers"]:

            dns_text = ", ".join(
                network["dns_servers"][:3]
            )

            net_details.append(
                f'DNS: {dns_text}'
            )

        self.network_card.status.setText(
            network_status
        )

        self.network_card.detail.setText(
            "\n".join(net_details)
        )

        # -------------------------
        # Storage
        # -------------------------

        disk_lines = []

        for drive in data["disks"]:

            disk_lines.append(
                f'{drive["device"]}  '
                f'{drive["percent"]:.0f}% used  •  '
                f'{format_bytes(drive["free"])} free  •  '
                f'{drive["fstype"]}'
            )

        if disk_lines:

            self.storage_card.status.setText(
                f'{len(disk_lines)} drive(s) detected'
            )

            self.storage_card.detail.setText(
                "\n".join(disk_lines)
            )

        else:

            self.storage_card.status.setText(
                "No drives detected"
            )

        # -------------------------
        # Processes
        # -------------------------

        process_lines = []

        for index, proc in enumerate(
            data["processes"],
            start=1,
        ):

            process_lines.append(
                f'{index}. {proc["name"]}   '
                f'{format_bytes(proc["memory"])}'
            )

        self.process_card.status.setText(
            "Highest RAM usage"
        )

        self.process_card.detail.setText(
            "\n".join(process_lines)
        )

        # -------------------------
        # Issues
        # -------------------------

        issues = data["analysis"]["issues"]

        if issues:

            self.issues_card.status.setText(
                f"{len(issues)} issue(s) detected"
            )

            lines = []

            for issue in issues:

                lines.append(
                    f"• {issue}"
                )

            self.issues_card.detail.setText(
                "\n".join(lines)
            )

        else:

            self.issues_card.status.setText(
                "No critical issues"
            )

            self.issues_card.detail.setText(
                "OpenFix did not detect any "
                "major problems during this scan."
            )

        # -------------------------
        # Recommendations
        # -------------------------

        recommendations = (
            data["analysis"][
                "recommendations"
            ]
        )

        lines = []

        for item in recommendations:

            lines.append(
                f"• {item}"
            )

        self.recommend_card.status.setText(
            "OpenFix suggestions"
        )

        self.recommend_card.detail.setText(
            "\n".join(lines)
        )


# =========================================================
# START APPLICATION
# =========================================================

if __name__ == "__main__":

    app = QApplication(sys.argv)

    window = OpenFixWindow()

    window.show()

    sys.exit(app.exec())