import json
import os
import platform
from datetime import datetime
import psutil

from openfix.core.helpers import format_uptime
from openfix.core.powershell import run_powershell

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
    return platform.processor() or "Not available"

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
            data = json.loads(result["stdout"])
            return {
                "caption": data.get("Caption") or "Microsoft Windows",
                "version": data.get("Version") or "Unknown",
                "build": data.get("BuildNumber") or "Unknown",
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
        seconds = datetime.now().timestamp() - psutil.boot_time()
        return {"seconds": seconds, "text": format_uptime(seconds)}
    except Exception:
        return {"seconds": None, "text": "Not available"}

def scan_cpu():
    try:
        return psutil.cpu_percent(interval=1)
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

