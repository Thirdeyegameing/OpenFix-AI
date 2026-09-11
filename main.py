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
    QStackedWidget,
)

APP_VERSION = "0.3.0"


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


# =========================================================
# SYSTEM SCAN
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

        if not device or device in seen:
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

        except Exception:
            pass

    return drives


def scan_top_processes(limit=5):
    processes = []

    for proc in psutil.process_iter(
        ["pid", "name", "memory_info", "cpu_percent"]
    ):
        try:
            info = proc.info

            memory = info["memory_info"].rss if info["memory_info"] else 0

            processes.append(
                {
                    "name": info["name"] or "Unknown",
                    "pid": info["pid"],
                    "memory": memory,
                    "cpu": info.get("cpu_percent") or 0,
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
                    gpu["vram"] = float(parts[1]) * 1024 * 1024
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

            adapter["name"] = data.get("Name") or "Unknown"
            adapter["description"] = data.get("InterfaceDescription") or "Unknown"
            adapter["link_speed"] = data.get("LinkSpeed") or "Unknown"
            adapter["mac"] = data.get("MacAddress") or "Unknown"

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

        times = []

        for line in output.splitlines():

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
            result_data["ping"] = sum(times) // len(times)

        if "lost =" in output:
            try:
                lost_part = output.split("lost =", 1)[1]
                inside = lost_part.split("(", 1)[1].split("%", 1)[0]

                digits = "".join(
                    char for char in inside if char.isdigit()
                )

                if digits:
                    result_data["packet_loss"] = int(digits)

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
# FULL SCAN
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
# DOCTORS
# =========================================================

def doctor_internet(data):
    network = data["network"]

    findings = []
    score = 100

    if not network["internet"]:
        score -= 40
        findings.append("Internet connectivity test failed.")
    else:
        findings.append("Internet connection is working.")

    if not network["dns_ok"]:
        score -= 20
        findings.append("DNS resolution problem detected.")
    else:
        findings.append("DNS resolution is working.")

    ping = network["ping"]

    if ping is not None:
        if ping >= 150:
            score -= 25
            findings.append(f"Ping is very high ({ping} ms).")
        elif ping >= 80:
            score -= 10
            findings.append(f"Ping is elevated ({ping} ms).")
        else:
            findings.append(f"Ping is good ({ping} ms).")

    packet_loss = network["packet_loss"]

    if packet_loss is not None:
        if packet_loss >= 10:
            score -= 25
            findings.append(
                f"High packet loss detected ({packet_loss}%)."
            )
        elif packet_loss >= 3:
            score -= 10
            findings.append(
                f"Packet loss detected ({packet_loss}%)."
            )
        else:
            findings.append("Packet loss is 0% or very low.")

    link = network["adapter"]["link_speed"]

    if link != "Unknown":
        findings.append(f"Adapter link speed: {link}")

    return {
        "title": "Internet Doctor",
        "score": max(0, score),
        "findings": findings,
    }


def doctor_gaming(data):
    findings = []
    score = 100

    cpu = data["cpu"]
    ram = data["memory"]["percent"]
    gpu = data["gpu"]

    if cpu >= 90:
        score -= 20
        findings.append("CPU usage is very high.")
    elif cpu >= 75:
        score -= 10
        findings.append("CPU usage is elevated.")
    else:
        findings.append("CPU usage is normal.")

    if ram >= 90:
        score -= 25
        findings.append("RAM usage is critically high.")
    elif ram >= 80:
        score -= 10
        findings.append("RAM usage is high.")
    else:
        findings.append("RAM usage is normal.")

    if gpu["usage"] is not None:
        if gpu["usage"] >= 98:
            findings.append(
                "GPU is near full utilization. "
                "This may be normal in GPU-limited games."
            )
        else:
            findings.append(
                f'GPU usage is {gpu["usage"]:.0f}%.'
            )

    if gpu["temperature"] is not None:
        if gpu["temperature"] >= 90:
            score -= 25
            findings.append(
                f'GPU temperature is critically high '
                f'({gpu["temperature"]:.0f}°C).'
            )
        elif gpu["temperature"] >= 83:
            score -= 10
            findings.append(
                f'GPU temperature is high '
                f'({gpu["temperature"]:.0f}°C).'
            )
        else:
            findings.append(
                f'GPU temperature is normal '
                f'({gpu["temperature"]:.0f}°C).'
            )

    network = data["network"]

    if network["ping"] is not None and network["ping"] >= 100:
        score -= 10
        findings.append(
            f'Network latency may affect online games '
            f'({network["ping"]} ms).'
        )

    if (
        network["packet_loss"] is not None
        and network["packet_loss"] >= 3
    ):
        score -= 15
        findings.append(
            f'Packet loss may cause lag '
            f'({network["packet_loss"]}%).'
        )

    return {
        "title": "Gaming Doctor",
        "score": max(0, score),
        "findings": findings,
    }


def doctor_slow_pc(data):
    findings = []
    score = 100

    cpu = data["cpu"]
    ram = data["memory"]["percent"]

    if cpu >= 85:
        score -= 20
        findings.append("High CPU usage may be slowing the PC.")
    else:
        findings.append("CPU usage is currently normal.")

    if ram >= 90:
        score -= 25
        findings.append("RAM is nearly full.")
    elif ram >= 80:
        score -= 10
        findings.append("RAM usage is high.")
    else:
        findings.append("RAM usage is normal.")

    if data["processes"]:
        top = data["processes"][0]

        findings.append(
            f'Highest RAM process: {top["name"]} '
            f'({format_bytes(top["memory"])}).'
        )

    for drive in data["disks"]:
        if drive["percent"] >= 95:
            score -= 20
            findings.append(
                f'{drive["device"]} is almost full.'
            )

    return {
        "title": "Slow PC Doctor",
        "score": max(0, score),
        "findings": findings,
    }


def doctor_storage(data):
    findings = []
    score = 100

    for drive in data["disks"]:

        free_gb = drive["free"] / (1024 ** 3)

        if free_gb < 5:
            score -= 25
            findings.append(
                f'{drive["device"]} is critically low on space '
                f'({free_gb:.1f} GB free).'
            )

        elif free_gb < 15:
            score -= 10
            findings.append(
                f'{drive["device"]} is running low on space '
                f'({free_gb:.1f} GB free).'
            )

        else:
            findings.append(
                f'{drive["device"]} has '
                f'{free_gb:.1f} GB free.'
            )

    return {
        "title": "Storage Doctor",
        "score": max(0, score),
        "findings": findings,
    }


def doctor_full(data):
    findings = []

    internet = doctor_internet(data)
    gaming = doctor_gaming(data)
    slow_pc = doctor_slow_pc(data)
    storage = doctor_storage(data)

    scores = [
        internet["score"],
        gaming["score"],
        slow_pc["score"],
        storage["score"],
    ]

    overall = sum(scores) // len(scores)

    findings.append(
        f'Internet Doctor score: {internet["score"]}/100'
    )
    findings.append(
        f'Gaming Doctor score: {gaming["score"]}/100'
    )
    findings.append(
        f'Slow PC Doctor score: {slow_pc["score"]}/100'
    )
    findings.append(
        f'Storage Doctor score: {storage["score"]}/100'
    )

    return {
        "title": "Full System Scan",
        "score": overall,
        "findings": findings,
    }


# =========================================================
# WORKER
# =========================================================

class DoctorWorker(QThread):
    finished = Signal(dict)

    def __init__(self, mode):
        super().__init__()
        self.mode = mode

    def run(self):
        data = collect_system_data()

        if self.mode == "internet":
            result = doctor_internet(data)

        elif self.mode == "gaming":
            result = doctor_gaming(data)

        elif self.mode == "slow":
            result = doctor_slow_pc(data)

        elif self.mode == "storage":
            result = doctor_storage(data)

        else:
            result = doctor_full(data)

        self.finished.emit(result)


# =========================================================
# UI COMPONENTS
# =========================================================

class DoctorButton(QPushButton):
    def __init__(self, title, subtitle):
        super().__init__()

        self.setText(
            f"{title}\n{subtitle}"
        )

        self.setObjectName("DoctorButton")

        self.setMinimumHeight(85)


class ResultCard(QFrame):
    def __init__(self):
        super().__init__()

        self.setObjectName("ResultCard")

        layout = QVBoxLayout(self)

        self.title = QLabel("Doctor Result")
        self.title.setObjectName("ResultTitle")

        self.score = QLabel("--")
        self.score.setObjectName("ResultScore")

        self.details = QLabel("")
        self.details.setWordWrap(True)
        self.details.setObjectName("ResultDetails")

        layout.addWidget(self.title)
        layout.addWidget(self.score)
        layout.addWidget(self.details)


# =========================================================
# MAIN WINDOW
# =========================================================

class OpenFixWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle(
            f"OpenFix AI v{APP_VERSION}"
        )

        self.resize(1100, 800)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        self.setCentralWidget(scroll)

        root = QWidget()
        scroll.setWidget(root)

        layout = QVBoxLayout(root)

        layout.setContentsMargins(
            30, 25, 30, 35
        )

        layout.setSpacing(18)

        header = QLabel("OpenFix AI")
        header.setObjectName("Header")

        subtitle = QLabel(
            "Choose a Doctor Mode to diagnose your PC."
        )
        subtitle.setObjectName("Subtitle")

        version = QLabel(
            f"Doctor Engine v{APP_VERSION}"
        )
        version.setObjectName("Version")

        layout.addWidget(header)
        layout.addWidget(subtitle)
        layout.addWidget(version)

        # Doctor buttons
        row1 = QHBoxLayout()

        self.internet_btn = DoctorButton(
            "Internet Doctor",
            "Ping, DNS, packet loss, gateway"
        )

        self.gaming_btn = DoctorButton(
            "Gaming Doctor",
            "CPU, RAM, GPU, network"
        )

        row1.addWidget(self.internet_btn)
        row1.addWidget(self.gaming_btn)

        layout.addLayout(row1)

        row2 = QHBoxLayout()

        self.slow_btn = DoctorButton(
            "Slow PC Doctor",
            "Find common performance problems"
        )

        self.storage_btn = DoctorButton(
            "Storage Doctor",
            "Check low disk space"
        )

        row2.addWidget(self.slow_btn)
        row2.addWidget(self.storage_btn)

        layout.addLayout(row2)

        self.full_btn = DoctorButton(
            "Full System Scan",
            "Run all Doctors"
        )

        layout.addWidget(self.full_btn)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()

        layout.addWidget(self.progress)

        self.result_card = ResultCard()
        layout.addWidget(self.result_card)

        footer = QLabel(
            "OpenFix AI • Read-only diagnostic mode"
        )
        footer.setObjectName("Footer")

        layout.addWidget(footer)

        self.internet_btn.clicked.connect(
            lambda: self.start_doctor("internet")
        )

        self.gaming_btn.clicked.connect(
            lambda: self.start_doctor("gaming")
        )

        self.slow_btn.clicked.connect(
            lambda: self.start_doctor("slow")
        )

        self.storage_btn.clicked.connect(
            lambda: self.start_doctor("storage")
        )

        self.full_btn.clicked.connect(
            lambda: self.start_doctor("full")
        )

        self.apply_style()

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

            #DoctorButton {
                background: white;
                border: 1px solid #e5e7eb;
                border-radius: 14px;
                padding: 16px;
                text-align: left;
                font-size: 15px;
                font-weight: 600;
                color: #111827;
            }

            #DoctorButton:hover {
                background: #f9fafb;
                border: 1px solid #9ca3af;
            }

            #DoctorButton:disabled {
                color: #9ca3af;
            }

            #ResultCard {
                background: white;
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

    def set_buttons_enabled(self, enabled):
        self.internet_btn.setEnabled(enabled)
        self.gaming_btn.setEnabled(enabled)
        self.slow_btn.setEnabled(enabled)
        self.storage_btn.setEnabled(enabled)
        self.full_btn.setEnabled(enabled)

    def start_doctor(self, mode):
        self.set_buttons_enabled(False)
        self.progress.show()

        self.result_card.title.setText(
            "Scanning..."
        )
        self.result_card.score.setText("--")
        self.result_card.details.setText(
            "Collecting system information."
        )

        self.worker = DoctorWorker(mode)

        self.worker.finished.connect(
            self.doctor_complete
        )

        self.worker.start()

    def doctor_complete(self, result):
        self.progress.hide()
        self.set_buttons_enabled(True)

        self.result_card.title.setText(
            result["title"]
        )

        self.result_card.score.setText(
            f'{result["score"]}/100'
        )

        lines = []

        for item in result["findings"]:
            lines.append(
                f"• {item}"
            )

        self.result_card.details.setText(
            "\n".join(lines)
        )


# =========================================================
# START
# =========================================================

if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = OpenFixWindow()
    window.show()

    sys.exit(app.exec())