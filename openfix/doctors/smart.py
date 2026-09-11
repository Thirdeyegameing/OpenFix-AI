from openfix import config
from openfix.core.helpers import clamp, format_bytes, format_prioritized_actions, make_result
from openfix.core.scoring import disk_space_state
from openfix.diagnostics.collector import smart_coverage
from openfix.diagnostics.system import group_process_memory
from openfix.diagnostics.storage_health import physical_disk_state


def doctor_smart(data, event_analysis):
    coverage = smart_coverage(data, event_analysis)
    if coverage <= 0:
        return make_result(
            "Local Smart Doctor",
            None,
            ["Smart analysis could not collect enough diagnostic data."],
            [],
            ["Run a Full System Scan again. If it repeats, check OpenFix logs."],
            "No Smart Doctor score was produced because the diagnostic inputs were unavailable.",
            coverage=0,
        )

    facts, issues, recommended = [], [], []
    candidates = []

    # Strongest penalty per diagnostic family only. This avoids punishing one
    # underlying problem multiple times when signals correlate.
    penalty_groups = {
        "resources": 0,
        "storage": 0,
        "network": 0,
        "graphics": 0,
        "hardware": 0,
        "shutdown": 0,
        "apps": 0,
    }

    def set_penalty(group, amount):
        penalty_groups[group] = max(penalty_groups[group], amount)

    def action(priority, text):
        recommended.append((priority, text))

    def candidate(priority, issue, why, doctor):
        candidates.append((priority, issue, why, doctor))

    cpu = data.get("cpu")
    memory = data.get("memory", {})
    ram = memory.get("percent")
    gpu = data.get("gpu", {})
    network = data.get("network", {})

    if cpu is not None:
        facts.append(f"CPU usage: {cpu:.0f}%.")
        if cpu >= config.CPU_CRITICAL:
            set_penalty("resources", 20)
            issues.append("CPU usage is extremely high.")
            action(2, "Check which application is using the most CPU.")
            candidate(
                3,
                "CPU usage is extremely high.",
                "Very high CPU load can make Windows and applications feel slow and can contribute to game stuttering.",
                "slow",
            )
        elif cpu >= config.CPU_HIGH:
            set_penalty("resources", 10)
            issues.append("CPU usage is high.")

    if ram is not None:
        facts.append(f"RAM usage: {ram:.0f}%.")
        if ram >= config.RAM_CRITICAL:
            set_penalty("resources", 25)
            issues.append("RAM usage is extremely high.")
            candidate(
                2,
                "RAM usage is extremely high.",
                "When RAM is almost full, Windows can rely more heavily on slower virtual memory.",
                "slow",
            )
        elif ram >= config.RAM_HIGH:
            set_penalty("resources", 12)
            issues.append("RAM usage is high.")

    grouped = group_process_memory(data.get("processes", []), limit=5)
    if grouped and memory.get("total"):
        top = grouped[0]
        percent = top["memory"] / memory["total"] * 100
        suffix = f" across {top['count']} processes" if top["count"] > 1 else ""
        facts.append(
            f"Highest RAM application: {top['name']} — {format_bytes(top['memory'])} ({percent:.1f}% of usable RAM{suffix})."
        )
        if ram is not None and ram >= config.RAM_HIGH and percent >= 15:
            action(0, f"Check {top['name']} first because it is using a large share of RAM.")

    low_storage = False
    critical_storage = False
    for drive in data.get("disks", []):
        state, free_gb, free_percent = disk_space_state(drive)
        if state == "ignored":
            continue
        if state == "critical":
            low_storage = True
            critical_storage = True
            set_penalty("storage", 25)
            issues.append(f"{drive['device']} is critically low on free space.")
            candidate(
                2,
                f"{drive['device']} is critically low on free space.",
                "Critically low free space can interfere with Windows updates, temporary files and application performance.",
                "storage",
            )
        elif state == "low":
            low_storage = True
            set_penalty("storage", 10)
            issues.append(f"{drive['device']} is getting low on free space.")

    physical = data.get("physical_storage", {})
    physical_problem = False
    if physical.get("available"):
        for disk in physical.get("disks", []):
            state = physical_disk_state(disk)
            if state == "unhealthy":
                physical_problem = True
                set_penalty("storage", max(config.PHYSICAL_DISK_UNHEALTHY_PENALTY, 35))
                issues.append(
                    f"Windows reports {disk.get('name', 'a physical disk')} as unhealthy or not operating normally."
                )
                action(0, "Back up important files before deeper storage troubleshooting.")
                action(1, "Confirm the drive condition with the SSD/HDD manufacturer's diagnostic tool.")
                candidate(
                    0,
                    "Windows reports a physical storage device as unhealthy.",
                    "An explicit unhealthy physical-disk status has high priority because it may affect data reliability.",
                    "storage",
                )
            elif state == "warning":
                physical_problem = True
                set_penalty("storage", max(config.PHYSICAL_DISK_WARNING_PENALTY, 18))
                issues.append(
                    f"Windows reports a warning/degraded state for {disk.get('name', 'a physical disk')}."
                )
                action(1, "Back up important files and confirm the drive condition with a dedicated diagnostic tool.")
                candidate(
                    1,
                    "Windows reports a warning for a physical storage device.",
                    "A storage warning deserves follow-up, but OpenFix does not treat it as proof that the drive has failed.",
                    "storage",
                )

    online = network.get("online")
    if network.get("connectivity_tested") and online is False:
        set_penalty("network", 30)
        issues.append("External internet connectivity could not be confirmed.")
        action(1, "Check the router, Wi-Fi connection or Ethernet cable.")
        candidate(
            1,
            "Internet connectivity could not be confirmed.",
            "A disconnected network can affect online games, websites, updates and communication apps.",
            "internet",
        )

    ping = network.get("ping")
    loss = network.get("packet_loss")
    if ping is not None:
        facts.append(f"Internet response time: {ping} ms.")
    if network.get("icmp_reachable") is True and loss is not None:
        facts.append(f"Packet loss: {loss}%.")

    if network.get("icmp_reachable") is True:
        if loss is not None and loss >= config.PACKET_LOSS_WARN and ping is not None and ping < config.PING_GOOD_MS:
            set_penalty("network", 18)
            issues.append("Internet response speed is good, but the connection appears unstable.")
            action(1, "Check Wi-Fi signal, Ethernet cable and router stability.")
            candidate(
                2,
                "The network connection appears unstable.",
                "Packet loss can cause game lag, voice cut-outs and connection problems even when ping looks good.",
                "internet",
            )
        elif loss is not None and loss >= config.PACKET_LOSS_WARN:
            set_penalty("network", 18)
            issues.append("Packet loss may be causing an unstable internet connection.")
            candidate(
                2,
                "Packet loss was detected.",
                "Packet loss directly affects connection stability and can be more noticeable than raw download speed.",
                "internet",
            )
        elif ping is not None and ping >= config.PING_HIGH_MS:
            set_penalty("network", 15)
            issues.append("Internet response time is very high.")
    elif network.get("ping_tested") and online is True:
        facts.append("ICMP ping is unavailable, but other connectivity checks confirm internet access.")

    hot_gpu = False
    if gpu.get("temperature") is not None:
        temperature = gpu["temperature"]
        facts.append(f"GPU temperature: {temperature:.0f}°C.")
        if temperature >= config.GPU_HOT_C:
            hot_gpu = True
            set_penalty("graphics", 25)
            issues.append("GPU temperature is dangerously high.")
            action(0, "Check GPU cooling, fans and case airflow.")
            candidate(
                1,
                "GPU temperature is dangerously high.",
                "Excessive GPU temperature can cause throttling, crashes and reduced gaming performance.",
                "gaming",
            )
        elif temperature >= config.GPU_WARM_C:
            hot_gpu = True
            set_penalty("graphics", 10)
            issues.append("GPU temperature is higher than ideal.")
    elif gpu.get("available"):
        facts.append("GPU detected, but temperature sensor data is unavailable.")

    storage_event = event_analysis.get("storage_errors", 0) > 0
    gpu_event = event_analysis.get("gpu_errors", 0) > 0

    if event_analysis.get("hardware_errors"):
        set_penalty("hardware", 30)
        issues.append("Windows recorded possible hardware errors.")
        action(0, "Run dedicated hardware diagnostics before changing Windows settings.")
        candidate(
            0,
            "Windows recorded possible hardware errors.",
            "Hardware-level errors have higher priority because they may indicate system instability below the software level.",
            "events",
        )

    if event_analysis.get("hardware_warnings"):
        facts.append(f"Windows recorded {event_analysis['hardware_warnings']} corrected hardware warning(s).")

    if storage_event:
        storage_penalty = 40 if physical_problem else (35 if low_storage else 25)
        set_penalty("storage", storage_penalty)
        issues.append("Windows recorded important storage-related errors.")
        if low_storage:
            action(0, "Back up important files first because storage errors and low free space were detected together.")
            candidate(
                0,
                "Storage errors and low free space were detected together.",
                "The combination deserves priority because storage problems can affect both data reliability and Windows stability.",
                "storage",
            )
        else:
            action(0, "Back up important files and check drive health.")
            candidate(
                0,
                "Windows recorded storage-related errors.",
                "Storage errors can affect file reliability and should be checked before less important performance issues.",
                "events",
            )

    if event_analysis.get("shutdown_errors"):
        set_penalty("shutdown", 20)
        issues.append("Unexpected shutdowns were recorded.")
        action(1, "Check temperatures, power stability and recent crash history.")
        candidate(
            1,
            "Unexpected shutdowns were recorded.",
            "Unexpected shutdowns may indicate crashes, temperature problems or power instability.",
            "events",
        )

    if gpu_event:
        set_penalty("graphics", 35 if hot_gpu else 15)
        issues.append("Windows recorded graphics-related errors.")
        if hot_gpu:
            action(0, "Check GPU cooling first because graphics errors and high temperature were detected together.")
            candidate(
                0,
                "GPU errors and high GPU temperature were detected together.",
                "Cooling should be checked before assuming the problem is only a graphics driver.",
                "gaming",
            )
        else:
            action(2, "Check graphics driver stability.")

    if event_analysis.get("app_crashes"):
        set_penalty("apps", 8)
        issues.append("Application crashes were recorded.")
        action(4, "Identify which application crashed before reinstalling drivers or Windows.")

    correlations = event_analysis.get("correlations") or []
    if correlations:
        for correlation in correlations[:3]:
            facts.append(
                f"Possible event relationship: {correlation['description']} "
                f"({correlation['seconds_apart']} seconds apart; correlation is not proof of cause)."
            )
        strongest = correlations[0]
        candidate(
            2,
            strongest["description"],
            "Two relevant Windows events occurred close together in time. OpenFix treats this as a possible relationship, not a confirmed cause.",
            strongest.get("route") or "events",
        )

    if low_storage and cpu is not None and cpu < config.RESOURCE_NORMAL_CPU_MAX and ram is not None and ram < config.RESOURCE_NORMAL_RAM_MAX:
        action(2, "Storage space is currently a more likely concern than CPU or RAM usage.")
    if critical_storage and not storage_event:
        action(1, "Free space on the nearly-full drive.")

    score = clamp(100 - sum(penalty_groups.values()))
    actions = format_prioritized_actions(recommended)

    primary_issue = None
    why_it_matters = None
    target_doctor = None
    if candidates:
        chosen = sorted(candidates, key=lambda item: item[0])[0]
        primary_issue, why_it_matters, target_doctor = chosen[1], chosen[2], chosen[3]

    return make_result(
        "Local Smart Doctor",
        score,
        facts,
        issues,
        actions,
        "Smart Doctor uses built-in local diagnostic rules. No Cloud AI or external AI API is used.",
        coverage=coverage,
        primary_issue=primary_issue,
        why_it_matters=why_it_matters,
        target_doctor=target_doctor,
        extra={"penalty_groups": penalty_groups},
    )
