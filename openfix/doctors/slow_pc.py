from openfix import config
from openfix.core.helpers import format_bytes, make_result
from openfix.core.scoring import disk_space_state
from openfix.diagnostics.collector import slow_pc_coverage
from openfix.diagnostics.system import group_process_memory


def doctor_slow_pc(data):
    coverage = slow_pc_coverage(data)
    if coverage <= 0:
        return make_result(
            "Slow PC Doctor",
            None,
            ["Performance diagnostic signals could not be collected."],
            [],
            ["Run the scan again. If it repeats, check OpenFix logs."],
            "No health score was produced because the required checks were unavailable.",
            coverage=0,
        )

    score = 100
    facts, issues, actions = [], [], []
    primary = None
    why = None

    cpu = data.get("cpu")
    memory = data.get("memory", {})
    ram = memory.get("percent")

    if cpu is not None:
        facts.append(f"CPU usage: {cpu:.0f}%.")
        if cpu >= config.SLOW_CPU_CRITICAL:
            score -= 22
            issues.append("CPU usage is very high.")
            actions.append("Check Task Manager for applications using a lot of CPU.")
            primary = "CPU usage is very high."
            why = "High CPU load can make Windows and applications respond slowly."
        elif cpu >= config.SLOW_CPU_HIGH:
            score -= 10
            issues.append("CPU usage is currently high.")
            actions.append("Close unnecessary CPU-heavy applications and scan again while the PC feels slow.")

    if ram is not None:
        facts.append(f"RAM usage: {ram:.0f}%.")
        if ram >= config.RAM_CRITICAL:
            score -= 28
            issues.append("Almost all available RAM is being used.")
            actions.append("Close unnecessary RAM-heavy applications and check the top RAM application first.")
            primary = "Almost all available RAM is being used."
            why = "Very high RAM usage can force Windows to use slower disk-based virtual memory."
        elif ram >= config.RAM_HIGH:
            score -= 15
            issues.append("RAM usage is high.")
            actions.append("Check which applications are using the most RAM and close unnecessary ones.")

    grouped = group_process_memory(data.get("processes", []), limit=5)
    if grouped:
        top = grouped[0]
        suffix = f" across {top['count']} processes" if top["count"] > 1 else ""
        facts.append(f"Highest RAM application: {top['name']} ({format_bytes(top['memory'])}{suffix}).")
        if ram is not None and ram >= config.RAM_HIGH and memory.get("total"):
            share = top["memory"] / memory["total"] * 100
            if share >= 15:
                actions.insert(0, f"Check {top['name']} first because it is using {share:.1f}% of usable RAM.")

    drive = data.get("system_drive")
    if drive:
        state, free_gb, free_percent = disk_space_state(drive)
        facts.append(f"Windows drive free space: {free_gb:.1f} GB ({free_percent:.0f}% free).")
        if state == "critical":
            score -= 20
            issues.append("The Windows drive is almost full.")
            actions.append("Free space on the Windows drive before doing deeper software troubleshooting.")
            if primary is None:
                primary = "The Windows drive is almost full."
                why = "Very low free space can interfere with Windows updates, temporary files and application performance."
        elif state == "low":
            score -= 8
            issues.append("The Windows drive is getting low on free space.")
            actions.append("Consider freeing some space on the Windows drive.")

    return make_result(
        "Slow PC Doctor",
        score,
        facts,
        issues,
        actions,
        "Run this Doctor while the PC actually feels slow for more useful results.",
        coverage=coverage,
        primary_issue=primary,
        why_it_matters=why,
        target_doctor="slow" if issues else None,
    )
