from openfix.core.helpers import make_result, format_bytes
from openfix.diagnostics.collector import slow_pc_coverage

def doctor_slow_pc(data):
    score = 100
    facts, issues, actions = [], [], []
    primary = None
    why = None

    cpu = data["cpu"]
    memory = data["memory"]
    ram = memory["percent"]

    if cpu is not None:
        facts.append(f"CPU usage: {cpu:.0f}%.")
        if cpu >= 90:
            score -= 22
            issues.append("CPU usage is very high.")
            actions.append("Check Task Manager for applications using a lot of CPU.")
            primary = "CPU usage is very high."
            why = "High CPU load can make Windows and applications respond slowly."
        elif cpu >= 80:
            score -= 10
            issues.append("CPU usage is currently high.")
            actions.append("Close unnecessary CPU-heavy applications and scan again while the PC feels slow.")

    if ram is not None:
        facts.append(f"RAM usage: {ram:.0f}%.")
        if ram >= 95:
            score -= 28
            issues.append("Almost all available RAM is being used.")
            actions.append("Close unnecessary RAM-heavy applications and check the top RAM process first.")
            primary = "Almost all available RAM is being used."
            why = "Very high RAM usage can force Windows to use slower disk-based virtual memory."
        elif ram >= 85:
            score -= 15
            issues.append("RAM usage is high.")
            actions.append("Check which applications are using the most RAM and close unnecessary ones.")

    if data["processes"]:
        top = data["processes"][0]
        facts.append(f"Highest RAM usage: {top['name']} ({format_bytes(top['memory'])}).")
        if ram is not None and ram >= 85 and memory["total"]:
            share = top["memory"] / memory["total"] * 100
            if share >= 15:
                actions.insert(0, f"Check {top['name']} first because it is using {share:.1f}% of installed RAM.")

    drive = data["system_drive"]
    if drive:
        free_gb = drive["free"] / (1024 ** 3)
        free_percent = 100 - drive["percent"]
        facts.append(f"Windows drive free space: {free_gb:.1f} GB ({free_percent:.0f}% free).")
        if free_gb < 5 or free_percent < 3:
            score -= 20
            issues.append("The Windows drive is almost full.")
            actions.append("Free space on the Windows drive before doing deeper software troubleshooting.")
            if primary is None:
                primary = "The Windows drive is almost full."
                why = "Very low free space can interfere with Windows updates, temporary files and application performance."

    return make_result(
        "Slow PC Doctor",
        score,
        facts,
        issues,
        actions,
        "Run this Doctor while the PC actually feels slow for more useful results.",
        coverage=slow_pc_coverage(data),
        primary_issue=primary,
        why_it_matters=why,
        target_doctor="slow" if issues else None,
    )
