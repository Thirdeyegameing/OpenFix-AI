import json

from openfix.core.helpers import safe_float
from openfix.core.powershell import run_powershell


def _normalize_status(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    return [str(value)]


def scan_physical_disks():
    """Read physical-disk health information without modifying the system.

    Serial numbers and unique identifiers are intentionally not collected.
    Reliability counters are optional and are never interpreted as a hardware
    verdict unless Windows explicitly reports Warning/Unhealthy/Degraded.
    """
    result = run_powershell(
        r"""
        try {
            $items = @()
            $disks = @(Get-PhysicalDisk -ErrorAction SilentlyContinue)
            foreach ($disk in $disks) {
                $reliability = $null
                try {
                    $reliability = $disk | Get-StorageReliabilityCounter -ErrorAction SilentlyContinue
                }
                catch {
                    $reliability = $null
                }

                $temperature = $null
                $wear = $null
                $readErrors = $null
                $writeErrors = $null
                if ($reliability) {
                    $temperature = $reliability.Temperature
                    $wear = $reliability.Wear
                    $readErrors = $reliability.ReadErrorsTotal
                    $writeErrors = $reliability.WriteErrorsTotal
                }

                $items += [PSCustomObject]@{
                    FriendlyName = $disk.FriendlyName
                    HealthStatus = [string]$disk.HealthStatus
                    OperationalStatus = @($disk.OperationalStatus | ForEach-Object { [string]$_ })
                    MediaType = [string]$disk.MediaType
                    BusType = [string]$disk.BusType
                    Size = $disk.Size
                    Temperature = $temperature
                    Wear = $wear
                    ReadErrorsTotal = $readErrors
                    WriteErrorsTotal = $writeErrors
                }
            }

            [PSCustomObject]@{
                Success = $true
                Disks = @($items)
            } | ConvertTo-Json -Depth 6 -Compress
        }
        catch {
            [PSCustomObject]@{
                Success = $false
                Disks = @()
            } | ConvertTo-Json -Depth 4 -Compress
        }
        """,
        timeout=15,
    )

    package = {
        "tested": bool(result.get("stdout")),
        "available": False,
        "disks": [],
    }
    if not result.get("stdout"):
        return package

    try:
        data = json.loads(result["stdout"])
    except Exception:
        return package

    if not data.get("Success"):
        return package

    raw_disks = data.get("Disks") or []
    if isinstance(raw_disks, dict):
        raw_disks = [raw_disks]

    disks = []
    for item in raw_disks:
        if not isinstance(item, dict):
            continue
        temperature = safe_float(item.get("Temperature"))
        if temperature is not None and not (0 <= temperature <= 130):
            temperature = None
        wear = safe_float(item.get("Wear"))
        if wear is not None and not (0 <= wear <= 100):
            wear = None

        disks.append(
            {
                "name": str(item.get("FriendlyName") or "Physical disk"),
                "health_status": str(item.get("HealthStatus") or "Unknown"),
                "operational_status": _normalize_status(item.get("OperationalStatus")),
                "media_type": str(item.get("MediaType") or "Unknown"),
                "bus_type": str(item.get("BusType") or "Unknown"),
                "size": int(item.get("Size") or 0) or None,
                "temperature": temperature,
                "wear": wear,
                "read_errors_total": item.get("ReadErrorsTotal"),
                "write_errors_total": item.get("WriteErrorsTotal"),
            }
        )

    package["disks"] = disks
    package["available"] = bool(disks)
    return package


def physical_disk_state(disk):
    """Return healthy/warning/unhealthy/unknown using explicit Windows status."""
    health = str(disk.get("health_status") or "").strip().lower()
    operations = {
        str(item).strip().lower()
        for item in disk.get("operational_status", [])
        if item is not None
    }

    unhealthy_terms = {
        "unhealthy",
        "failed",
        "lost communication",
        "non-recoverable error",
        "stopped",
        "removed from pool",
    }
    warning_terms = {
        "warning",
        "degraded",
        "stressed",
        "predictive failure",
        "error",
        "no contact",
        "supporting entity in error",
    }

    if health == "unhealthy" or operations.intersection(unhealthy_terms):
        return "unhealthy"
    if health == "warning" or operations.intersection(warning_terms):
        return "warning"
    if health == "healthy" and (not operations or operations == {"ok"}):
        return "healthy"
    if health == "healthy" and "ok" in operations:
        return "healthy"
    return "unknown"
