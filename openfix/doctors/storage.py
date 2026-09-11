from openfix.core.helpers import make_result
from openfix.diagnostics.collector import storage_coverage

def doctor_storage(data):
    disks = data["disks"]
    if not disks:
        return make_result(
            "Storage Doctor",
            100,
            [],
            [],
            [],
            "Drive information could not be read. Missing information was not treated as a fault.",
            coverage=0,
        )

    score = 100
    facts, issues, actions = [], [], []
    primary = None
    why = None

    for drive in disks:
        free_gb = drive["free"] / (1024 ** 3)
        free_percent = 100 - drive["percent"]
        facts.append(f"{drive['device']} has {free_gb:.1f} GB free ({free_percent:.0f}% free).")

        if free_gb < 5 or free_percent < 3:
            score -= 28
            issues.append(f"{drive['device']} is critically low on free space.")
            actions.append(f"Free space on {drive['device']} before large updates or installations.")
            if primary is None:
                primary = f"{drive['device']} is critically low on free space."
                why = "Critically low free space can interfere with updates, temporary files and application performance."
        elif free_gb < 15 or free_percent < 8:
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
        "This checks available space only. It does not prove whether an SSD or HDD is physically healthy.",
        coverage=storage_coverage(data),
        primary_issue=primary,
        why_it_matters=why,
        target_doctor="storage" if issues else None,
    )
