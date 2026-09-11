from openfix import config
from openfix.core.helpers import format_bytes, make_result
from openfix.core.scoring import disk_space_state
from openfix.diagnostics.collector import storage_coverage
from openfix.diagnostics.storage_health import physical_disk_state


def doctor_storage(data):
    disks = data.get("disks", [])
    physical = data.get("physical_storage", {})
    coverage = storage_coverage(data)

    if not disks and not physical.get("available"):
        return make_result(
            "Storage Doctor",
            None,
            ["Storage diagnostic information could not be read."],
            [],
            ["Run the scan again. If it repeats, check OpenFix logs."],
            "Missing storage information is not treated as a healthy result or as a hardware fault.",
            coverage=0,
        )

    score = 100
    facts, issues, actions = [], [], []
    primary = None
    why = None

    # Logical-volume free-space checks.
    for drive in disks:
        state, free_gb, free_percent = disk_space_state(drive)
        drive_type = drive.get("drive_type", "unknown")
        label = "Windows drive" if drive.get("is_system") else drive_type.title()
        facts.append(
            f"{drive['device']} ({label}) has {free_gb:.1f} GB free ({free_percent:.0f}% free)."
        )

        if state == "ignored":
            facts.append(f"{drive['device']} is not included in the PC storage health score.")
            continue
        if state == "critical":
            score -= 28
            issues.append(f"{drive['device']} is critically low on free space.")
            actions.append(f"Free space on {drive['device']} before large updates or installations.")
            if primary is None:
                primary = f"{drive['device']} is critically low on free space."
                why = "Critically low free space can interfere with updates, temporary files and application performance."
        elif state == "low":
            score -= 12
            issues.append(f"{drive['device']} is getting low on free space.")
            actions.append(f"Consider freeing some space on {drive['device']}.")
            if primary is None:
                primary = f"{drive['device']} is getting low on free space."
                why = "Keeping some free storage space helps Windows and applications work more reliably."

    # Read-only physical-disk health reported by Windows Storage APIs.
    if physical.get("available"):
        facts.append(f"Physical disks reported by Windows: {len(physical.get('disks', []))}.")
        for disk in physical.get("disks", []):
            state = physical_disk_state(disk)
            size_text = format_bytes(disk.get("size")) if disk.get("size") else "size unavailable"
            media = disk.get("media_type") or "Unknown"
            bus = disk.get("bus_type") or "Unknown"
            health = disk.get("health_status") or "Unknown"
            ops = ", ".join(disk.get("operational_status", [])) or "Unknown"
            facts.append(
                f"{disk.get('name', 'Physical disk')} — {media}, {bus}, {size_text}; Windows health: {health}; operational status: {ops}."
            )
            if disk.get("temperature") is not None:
                facts.append(
                    f"{disk.get('name', 'Physical disk')} temperature: {disk['temperature']:.0f}°C (reported by Windows)."
                )

            if state == "unhealthy":
                score -= config.PHYSICAL_DISK_UNHEALTHY_PENALTY
                issues.append(
                    f"Windows reports {disk.get('name', 'a physical disk')} as unhealthy or not operating normally."
                )
                actions.insert(0, "Back up important files before doing deeper storage troubleshooting.")
                actions.append("Confirm the drive condition with the SSD/HDD manufacturer's diagnostic tool.")
                primary = "Windows reports a physical storage device as unhealthy."
                why = "An explicit unhealthy physical-disk status has higher priority because it may affect data reliability."
            elif state == "warning":
                score -= config.PHYSICAL_DISK_WARNING_PENALTY
                issues.append(
                    f"Windows reports a warning/degraded state for {disk.get('name', 'a physical disk')}."
                )
                actions.append("Back up important files and confirm the drive condition with a dedicated diagnostic tool.")
                if primary is None:
                    primary = "Windows reports a warning for a physical storage device."
                    why = "A Windows storage warning deserves follow-up, but OpenFix does not treat it as proof that the drive has failed."
    elif physical.get("tested"):
        facts.append("Physical SSD/HDD health status is not available from Windows on this system.")
    else:
        facts.append("Physical SSD/HDD health check could not be performed.")

    score = max(0, min(100, score))
    return make_result(
        "Storage Doctor",
        score,
        facts,
        issues,
        actions,
        "Storage Doctor combines free-space checks with read-only Windows physical-disk status when available. Unsupported health data is never assumed to be healthy or faulty.",
        coverage=coverage,
        primary_issue=primary,
        why_it_matters=why,
        target_doctor="storage" if issues else None,
        extra={"physical_storage": physical},
    )
