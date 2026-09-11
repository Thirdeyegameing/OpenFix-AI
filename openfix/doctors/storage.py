from openfix.core.helpers import make_result
from openfix.core.scoring import disk_space_state
from openfix.diagnostics.collector import storage_coverage


def doctor_storage(data):
    disks = data.get("disks", [])
    coverage = storage_coverage(data)
    if not disks:
        return make_result(
            "Storage Doctor",
            None,
            ["Drive information could not be read."],
            [],
            ["Run the scan again. If it repeats, check OpenFix logs."],
            "Missing drive information is not treated as a healthy result or as a hardware fault.",
            coverage=0,
        )

    score = 100
    facts, issues, actions = [], [], []
    primary = None
    why = None

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

    return make_result(
        "Storage Doctor",
        score,
        facts,
        issues,
        actions,
        "This scan checks free-space conditions. Physical SSD/HDD health is planned for a later diagnostic expansion.",
        coverage=coverage,
        primary_issue=primary,
        why_it_matters=why,
        target_doctor="storage" if issues else None,
    )
