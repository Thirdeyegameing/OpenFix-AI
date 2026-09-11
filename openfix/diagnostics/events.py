import json

from openfix.config import EVENT_LOOKBACK_HOURS, EVENT_MAX_EVENTS
from openfix.core.helpers import safe_int
from openfix.core.powershell import run_powershell


CORRECTED_WHEA_IDS = {17, 19}
SERIOUS_WHEA_IDS = {1, 18, 20, 46, 47}


def scan_event_logs():
    result = run_powershell(
        rf"""
        try {{
            $start = (Get-Date).AddHours(-{EVENT_LOOKBACK_HOURS})
            $events =
            Get-WinEvent -FilterHashtable @{{
                LogName=@('System','Application')
                Level=@(1,2,3)
                StartTime=$start
            }} -MaxEvents {EVENT_MAX_EVENTS} -ErrorAction SilentlyContinue |
            Select-Object TimeCreated, LogName, ProviderName, Id, LevelDisplayName, Message

            [PSCustomObject]@{{
                Success = $true
                Events = @($events)
            }} | ConvertTo-Json -Depth 5 -Compress
        }}
        catch {{
            [PSCustomObject]@{{
                Success = $false
                Events = @()
            }} | ConvertTo-Json -Depth 5 -Compress
        }}
        """,
        timeout=18,
    )

    package = {"available": False, "events": []}
    if not result["stdout"]:
        return package

    try:
        data = json.loads(result["stdout"])
        package["available"] = bool(data.get("Success"))
        raw_events = data.get("Events") or []
        if isinstance(raw_events, dict):
            raw_events = [raw_events]

        for item in raw_events:
            if not isinstance(item, dict):
                continue
            message = str(item.get("Message") or "").replace("\r", " ").replace("\n", " ")
            if len(message) > 350:
                message = message[:350] + "..."
            timestamp = item.get("TimeCreated")
            package["events"].append(
                {
                    "time_created": str(timestamp) if timestamp is not None else None,
                    "log_name": item.get("LogName") or "Unknown",
                    "provider": item.get("ProviderName") or "Unknown",
                    "id": safe_int(item.get("Id")),
                    "level": item.get("LevelDisplayName") or "Unknown",
                    "message": message,
                }
            )
    except Exception:
        pass

    return package


def analyze_event_logs(package):
    analysis = {
        "available": bool(package.get("available")),
        "total": len(package.get("events", [])),
        "critical": 0,
        "errors": 0,
        "warnings": 0,
        "relevant_events": 0,
        "hardware_errors": 0,
        "hardware_warnings": 0,
        "storage_errors": 0,
        "shutdown_errors": 0,
        "gpu_errors": 0,
        "app_crashes": 0,
        "generic_errors": 0,
        "ignored_noise": 0,
        "important": [],
    }

    for event in package.get("events", []):
        provider = str(event.get("provider") or "").lower()
        level = str(event.get("level") or "").lower()
        message = str(event.get("message") or "").lower()
        event_id = safe_int(event.get("id"))

        if "critical" in level:
            analysis["critical"] += 1
        elif "error" in level:
            analysis["errors"] += 1
        elif "warning" in level:
            analysis["warnings"] += 1

        # Common Windows background noise with low troubleshooting value.
        if "microsoft-windows-capi2" in provider:
            analysis["ignored_noise"] += 1
            continue
        if "distributedcom" in provider and event_id == 10016:
            analysis["ignored_noise"] += 1
            continue

        category = None
        serious = False

        if "whea" in provider:
            if event_id in CORRECTED_WHEA_IDS:
                analysis["hardware_warnings"] += 1
                category = "Corrected Hardware Warning"
            elif event_id in SERIOUS_WHEA_IDS or "fatal" in message or "uncorrected" in message:
                analysis["hardware_errors"] += 1
                category = "Hardware"
                serious = True
            elif "error" in level or "critical" in level:
                analysis["hardware_errors"] += 1
                category = "Hardware"
                serious = True
            else:
                analysis["hardware_warnings"] += 1
                category = "Hardware Warning"

        elif "kernel-power" in provider and event_id == 41:
            analysis["shutdown_errors"] += 1
            category = "Unexpected Shutdown"
            serious = True

        elif "eventlog" in provider and event_id == 6008:
            analysis["shutdown_errors"] += 1
            category = "Unexpected Shutdown"
            serious = True

        elif any(token in provider for token in ("nvlddmkm", "amdwddmg", "dxgkrnl")) and (
            "error" in level or "critical" in level
        ):
            analysis["gpu_errors"] += 1
            category = "Graphics"
            serious = True

        elif provider == "display" and ("error" in level or "critical" in level):
            analysis["gpu_errors"] += 1
            category = "Graphics"
            serious = True

        elif any(
            token in provider
            for token in ("disk", "ntfs", "storahci", "stornvme", "volmgr", "volsnap")
        ) and ("error" in level or "critical" in level):
            analysis["storage_errors"] += 1
            category = "Storage"
            serious = True

        elif "application error" in provider and event_id == 1000 and (
            "error" in level or "critical" in level
        ):
            analysis["app_crashes"] += 1
            category = "Application Crash"
            serious = True

        elif "error" in level or "critical" in level:
            analysis["generic_errors"] += 1
            category = "Windows"
            serious = True

        if category:
            analysis["relevant_events"] += 1
            if len(analysis["important"]) < 10:
                analysis["important"].append({**event, "category": category, "serious": serious})

    return analysis
