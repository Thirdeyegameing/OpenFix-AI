import json
import os
import platform
from datetime import datetime

import psutil

from openfix.core.helpers import format_uptime
from openfix.core.powershell import run_powershell

_DRIVE_TYPE_NAMES = {
    0: "unknown",
    1: "no_root",
    2: "removable",
    3: "fixed",
    4: "network",
    5: "optical",
    6: "ramdisk",
}


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


def get_installed_ram_bytes():
    result = run_powershell(
        r"""
        $sum = (Get-CimInstance Win32_PhysicalMemory -ErrorAction SilentlyContinue |
            Measure-Object -Property Capacity -Sum).Sum
        if ($sum) { $sum }
        """,
        timeout=8,
    )
    if result["ok"] and result["stdout"]:
        try:
            return int(float(result["stdout"].splitlines()[-1].strip()))
        except Exception:
            pass
    return None


def _get_drive_metadata():
    result = run_powershell(
        r"""
        Get-CimInstance Win32_LogicalDisk -ErrorAction SilentlyContinue |
        Select-Object DeviceID, DriveType, VolumeName |
        ConvertTo-Json -Compress
        """,
        timeout=8,
    )
    metadata = {}
    if not (result["ok"] and result["stdout"]):
        return metadata
    try:
        data = json.loads(result["stdout"])
        if isinstance(data, dict):
            data = [data]
        for item in data or []:
            device = str(item.get("DeviceID") or "").upper().rstrip("\\")
            if not device:
                continue
            drive_type = int(item.get("DriveType") or 0)
            metadata[device] = {
                "drive_type_code": drive_type,
                "drive_type": _DRIVE_TYPE_NAMES.get(drive_type, "unknown"),
                "volume_name": item.get("VolumeName") or "",
            }
    except Exception:
        return {}
    return metadata


def scan_disks():
    drives = []
    seen = set()
    metadata = _get_drive_metadata()
    system_drive = os.environ.get("SystemDrive", "C:").upper().rstrip("\\")

    try:
        partitions = psutil.disk_partitions(all=False)
    except Exception:
        partitions = []

    for partition in partitions:
        device = str(partition.device or "")
        normalized = device.upper().rstrip("\\")
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)

        try:
            usage = psutil.disk_usage(partition.mountpoint)
        except Exception:
            continue

        meta = metadata.get(normalized, {})
        drive_type = meta.get("drive_type", "unknown")
        is_system = normalized.startswith(system_drive)
        # Fixed local drives affect PC storage health. Removable/network/optical
        # drives are displayed but do not reduce the PC health score.
        scored = is_system or drive_type == "fixed"

        drives.append(
            {
                "device": device,
                "mountpoint": partition.mountpoint,
                "filesystem": partition.fstype,
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "percent": usage.percent,
                "drive_type": drive_type,
                "drive_type_code": meta.get("drive_type_code"),
                "volume_name": meta.get("volume_name", ""),
                "is_system": is_system,
                "scored": scored,
            }
        )
    return drives


def find_system_drive(disks):
    system_drive = os.environ.get("SystemDrive", "C:").upper().rstrip("\\")
    for drive in disks:
        device = str(drive.get("device", "")).upper().rstrip("\\")
        if device.startswith(system_drive):
            return drive
    return next((drive for drive in disks if drive.get("is_system")), None)


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


def group_process_memory(processes, limit=5):
    grouped = {}
    for item in processes:
        name = (item.get("name") or "Unknown").strip() or "Unknown"
        key = name.lower()
        if key not in grouped:
            grouped[key] = {"name": name, "memory": 0, "count": 0}
        grouped[key]["memory"] += int(item.get("memory") or 0)
        grouped[key]["count"] += 1
    values = sorted(grouped.values(), key=lambda item: item["memory"], reverse=True)
    return values[:limit]
