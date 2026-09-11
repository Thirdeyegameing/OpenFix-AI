import json
import re
from datetime import datetime, timezone

from openfix.config import (
    EVENT_CORRELATION_WINDOW_MINUTES,
    EVENT_LOOKBACK_HOURS,
    EVENT_MAX_EVENTS,
)
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
                    # Message is kept in memory only for classification. OpenFix does
                    # not persist raw Event Log messages into scan history/telemetry.
                    "message": message,
                }
            )
    except Exception:
        pass

    return package


def _parse_event_time(value):
    if not value:
        return None
    text = str(value).strip()

    # Windows PowerShell 5 may serialize DateTime as /Date(1234567890000)/.
    match = re.search(r"/Date\(([-+]?\d+)(?:[-+]\d+)?\)/", text)
    if match:
        try:
            return datetime.fromtimestamp(int(match.group(1)) / 1000, tz=timezone.utc)
        except Exception:
            return None

    # PowerShell 7 and some JSON paths produce ISO timestamps.
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        pass

    # Common display fallback if a provider/plugin changes serialization.
    for fmt in ("%Y-%m-%d %H:%M:%S", "%m/%d/%Y %H:%M:%S", "%d/%m/%Y %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except Exception:
            continue
    return None


def _classify_event(event):
    provider = str(event.get("provider") or "").lower()
    level = str(event.get("level") or "").lower()
    message = str(event.get("message") or "").lower()
    event_id = safe_int(event.get("id"))

    if "microsoft-windows-capi2" in provider:
        return "ignored", False
    if "distributedcom" in provider and event_id == 10016:
        return "ignored", False

    if "whea" in provider:
        if event_id in CORRECTED_WHEA_IDS:
            return "Corrected Hardware Warning", False
        if event_id in SERIOUS_WHEA_IDS or "fatal" in message or "uncorrected" in message:
            return "Hardware", True
        if "error" in level or "critical" in level:
            return "Hardware", True
        return "Hardware Warning", False

    if "kernel-power" in provider and event_id == 41:
        return "Unexpected Shutdown", True

    if "eventlog" in provider and event_id == 6008:
        return "Unexpected Shutdown", True

    if any(token in provider for token in ("nvlddmkm", "amdwddmg", "dxgkrnl")) and (
        "error" in level or "critical" in level
    ):
        return "Graphics", True

    if provider == "display" and ("error" in level or "critical" in level):
        return "Graphics", True

    if any(
        token in provider
        for token in ("disk", "ntfs", "storahci", "stornvme", "volmgr", "volsnap")
    ) and ("error" in level or "critical" in level):
        return "Storage", True

    if "application error" in provider and event_id == 1000 and (
        "error" in level or "critical" in level
    ):
        return "Application Crash", True

    if "error" in level or "critical" in level:
        return "Windows", True

    return None, False


def correlate_events(important, window_minutes=EVENT_CORRELATION_WINDOW_MINUTES):
    """Find conservative time-nearby event pairs without claiming causation."""
    parsed = []
    for event in important:
        dt = _parse_event_time(event.get("time_created"))
        if dt is not None:
            parsed.append((dt, event))
    parsed.sort(key=lambda item: item[0])

    correlations = []
    seen = set()
    useful_pairs = {
        frozenset(("Hardware", "Unexpected Shutdown")): (
            "A hardware-related event occurred close to an unexpected shutdown.",
            "events",
        ),
        frozenset(("Graphics", "Unexpected Shutdown")): (
            "A graphics-related event occurred close to an unexpected shutdown.",
            "gaming",
        ),
        frozenset(("Storage", "Unexpected Shutdown")): (
            "A storage-related event occurred close to an unexpected shutdown.",
            "storage",
        ),
        frozenset(("Graphics", "Application Crash")): (
            "A graphics-related event occurred close to an application crash.",
            "gaming",
        ),
    }

    max_seconds = max(1, int(window_minutes)) * 60
    for index, (left_time, left) in enumerate(parsed):
        for right_time, right in parsed[index + 1 :]:
            delta = (right_time - left_time).total_seconds()
            if delta > max_seconds:
                break
            pair = frozenset((left.get("category"), right.get("category")))
            if pair not in useful_pairs:
                continue
            description, route = useful_pairs[pair]
            key = (tuple(sorted(pair)), round(delta))
            if key in seen:
                continue
            seen.add(key)
            correlations.append(
                {
                    "description": description,
                    "route": route,
                    "seconds_apart": int(delta),
                    "categories": sorted(pair),
                    "confidence": "possible",
                }
            )
            if len(correlations) >= 5:
                return correlations
    return correlations


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
        "correlations": [],
    }

    for event in package.get("events", []):
        level = str(event.get("level") or "").lower()
        if "critical" in level:
            analysis["critical"] += 1
        elif "error" in level:
            analysis["errors"] += 1
        elif "warning" in level:
            analysis["warnings"] += 1

        category, serious = _classify_event(event)
        if category == "ignored":
            analysis["ignored_noise"] += 1
            continue
        if not category:
            continue

        if category in ("Corrected Hardware Warning", "Hardware Warning"):
            analysis["hardware_warnings"] += 1
        elif category == "Hardware":
            analysis["hardware_errors"] += 1
        elif category == "Unexpected Shutdown":
            analysis["shutdown_errors"] += 1
        elif category == "Graphics":
            analysis["gpu_errors"] += 1
        elif category == "Storage":
            analysis["storage_errors"] += 1
        elif category == "Application Crash":
            analysis["app_crashes"] += 1
        elif category == "Windows":
            analysis["generic_errors"] += 1

        analysis["relevant_events"] += 1
        if len(analysis["important"]) < 10:
            # Raw message is deliberately omitted from the analyzed output. The
            # category/provider/id/timestamp are enough for the UI and safer to
            # share in bug reports.
            analysis["important"].append(
                {
                    "time_created": event.get("time_created"),
                    "log_name": event.get("log_name"),
                    "provider": event.get("provider"),
                    "id": event.get("id"),
                    "level": event.get("level"),
                    "category": category,
                    "serious": serious,
                }
            )

    analysis["correlations"] = correlate_events(analysis["important"])
    return analysis
