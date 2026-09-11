import json

from openfix.core.helpers import safe_int
from openfix.core.powershell import run_powershell

def scan_event_logs():
    result = run_powershell(
        r"""
        try {
            $start = (Get-Date).AddHours(-24)
            $events =
            Get-WinEvent -FilterHashtable @{
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
        """,
        timeout=15,
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
            package["events"].append(
                {
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
        "available": package["available"],
        "total": len(package["events"]),
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

    for event in package["events"]:
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

        # Frequent Windows background noise with low diagnostic value.
        if "microsoft-windows-capi2" in provider:
            analysis["ignored_noise"] += 1
            continue
        if "distributedcom" in provider and event_id == 10016:
            analysis["ignored_noise"] += 1
            continue

        category = None

        if "whea" in provider or (
            "hardware error" in message
            and ("error" in level or "critical" in level)
        ):
            analysis["hardware_errors"] += 1
            category = "Hardware"

        elif ("kernel-power" in provider and event_id == 41) or event_id == 6008:
            analysis["shutdown_errors"] += 1
            category = "Unexpected Shutdown"

        elif any(token in provider for token in ("nvlddmkm", "amdwddmg", "dxgkrnl")) and (
            "error" in level or "critical" in level
        ):
            analysis["gpu_errors"] += 1
            category = "Graphics"

        elif provider == "display" and ("error" in level or "critical" in level):
            analysis["gpu_errors"] += 1
            category = "Graphics"

        elif any(
            token in provider
            for token in ("disk", "ntfs", "storahci", "stornvme", "volmgr", "volsnap")
        ) and ("error" in level or "critical" in level):
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

