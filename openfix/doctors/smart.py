from openfix.core.helpers import clamp, format_bytes, format_prioritized_actions, make_result
from openfix.diagnostics.collector import smart_coverage

def doctor_smart(data, event_analysis):
    facts, issues, recommended = [], [], []
    candidates = []

    # Each diagnostic family uses its strongest penalty only, reducing double punishment.
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

    cpu = data["cpu"]
    memory = data["memory"]
    ram = memory["percent"]
    gpu = data["gpu"]
    network = data["network"]

    if cpu is not None:
        facts.append(f"CPU usage: {cpu:.0f}%.")
        if cpu >= 95:
            set_penalty("resources", 20)
            issues.append("CPU usage is extremely high.")
            action(2, "Check which application is using the most CPU.")
            candidate(3, "CPU usage is extremely high.", "Very high CPU load can make Windows and applications feel slow and can contribute to game stuttering.", "slow")
        elif cpu >= 85:
            set_penalty("resources", 10)
            issues.append("CPU usage is high.")

    if ram is not None:
        facts.append(f"RAM usage: {ram:.0f}%.")
        if ram >= 95:
            set_penalty("resources", 25)
            issues.append("RAM usage is extremely high.")
            candidate(2, "RAM usage is extremely high.", "When RAM is almost full, Windows can rely more heavily on slower virtual memory.", "slow")
        elif ram >= 85:
            set_penalty("resources", 12)
            issues.append("RAM usage is high.")

    if data["processes"] and memory["total"]:
        top = data["processes"][0]
        percent = top["memory"] / memory["total"] * 100
        facts.append(f"Highest RAM usage: {top['name']} — {format_bytes(top['memory'])} ({percent:.1f}% of installed RAM).")
        if ram is not None and ram >= 85 and percent >= 15:
            action(0, f"Check {top['name']} first because it is using a large share of RAM.")

    low_storage = False
    critical_storage = False
    for drive in data["disks"]:
        free_gb = drive["free"] / (1024 ** 3)
        free_percent = 100 - drive["percent"]
        if free_gb < 5 or free_percent < 3:
            low_storage = True
            critical_storage = True
            set_penalty("storage", 25)
            issues.append(f"{drive['device']} is critically low on free space.")
            candidate(2, f"{drive['device']} is critically low on free space.", "Critically low free space can interfere with Windows updates, temporary files and application performance.", "storage")
        elif free_gb < 15 or free_percent < 8:
            low_storage = True
            set_penalty("storage", 10)
            issues.append(f"{drive['device']} is getting low on free space.")

    # Internet offline is explicitly handled again in dev9.
    if network["ping_tested"] and network["internet"] is False:
        set_penalty("network", 30)
        issues.append("OpenFix could not reach the internet.")
        action(1, "Check the router, Wi-Fi connection or Ethernet cable.")
        candidate(1, "Internet connection could not be confirmed.", "A disconnected network can affect online games, websites, updates and communication apps.", "internet")

    ping = network["ping"]
    loss = network["packet_loss"]
    if ping is not None:
        facts.append(f"Internet response time: {ping} ms.")
    if loss is not None:
        facts.append(f"Packet loss: {loss}%.")

    if loss is not None and loss >= 3 and ping is not None and ping < 80:
        set_penalty("network", 18)
        issues.append("Internet response speed is good, but the connection appears unstable.")
        action(1, "Check Wi-Fi signal, Ethernet cable and router stability.")
        candidate(2, "The network connection appears unstable.", "Packet loss can cause game lag, voice cut-outs and connection problems even when ping looks good.", "internet")
    elif loss is not None and loss >= 3:
        set_penalty("network", 18)
        issues.append("Packet loss may be causing an unstable internet connection.")
        candidate(2, "Packet loss was detected.", "Packet loss directly affects connection stability and can be more noticeable than raw download speed.", "internet")
    elif ping is not None and ping >= 150:
        set_penalty("network", 15)
        issues.append("Internet response time is very high.")

    hot_gpu = False
    if gpu["temperature"] is not None:
        temperature = gpu["temperature"]
        facts.append(f"GPU temperature: {temperature:.0f}°C.")
        if temperature >= 90:
            hot_gpu = True
            set_penalty("graphics", 25)
            issues.append("GPU temperature is dangerously high.")
            action(0, "Check GPU cooling, fans and case airflow.")
            candidate(1, "GPU temperature is dangerously high.", "Excessive GPU temperature can cause throttling, crashes and reduced gaming performance.", "gaming")
        elif temperature >= 83:
            hot_gpu = True
            set_penalty("graphics", 10)
            issues.append("GPU temperature is higher than ideal.")

    storage_event = event_analysis["storage_errors"] > 0
    gpu_event = event_analysis["gpu_errors"] > 0

    if event_analysis["hardware_errors"]:
        set_penalty("hardware", 30)
        issues.append("Windows recorded possible hardware errors.")
        action(0, "Run dedicated hardware diagnostics before changing Windows settings.")
        candidate(0, "Windows recorded possible hardware errors.", "Hardware-level errors have higher priority because they may indicate system instability below the software level.", "events")

    if storage_event:
        # Correlate with low space instead of stacking two separate storage penalties.
        set_penalty("storage", 35 if low_storage else 25)
        issues.append("Windows recorded important storage-related errors.")
        if low_storage:
            action(0, "Back up important files first because storage errors and low free space were detected together.")
            candidate(0, "Storage errors and low free space were detected together.", "The combination deserves priority because storage problems can affect both data reliability and Windows stability.", "storage")
        else:
            action(0, "Back up important files and check drive health.")
            candidate(0, "Windows recorded storage-related errors.", "Storage errors can affect file reliability and should be checked before less important performance issues.", "events")

    if event_analysis["shutdown_errors"]:
        set_penalty("shutdown", 20)
        issues.append("Unexpected shutdowns were recorded.")
        action(1, "Check temperatures, power stability and recent crash history.")
        candidate(1, "Unexpected shutdowns were recorded.", "Unexpected shutdowns may indicate crashes, temperature problems or power instability.", "events")

    if gpu_event:
        set_penalty("graphics", 35 if hot_gpu else 15)
        issues.append("Windows recorded graphics-related errors.")
        if hot_gpu:
            action(0, "Check GPU cooling first because graphics errors and high temperature were detected together.")
            candidate(0, "GPU errors and high GPU temperature were detected together.", "Cooling should be checked before assuming the problem is only a graphics driver.", "gaming")
        else:
            action(2, "Check graphics driver stability.")

    if event_analysis["app_crashes"]:
        set_penalty("apps", 8)
        issues.append("Application crashes were recorded.")
        action(4, "Identify which application crashed before reinstalling drivers or Windows.")

    if low_storage and cpu is not None and cpu < 70 and ram is not None and ram < 80:
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
        coverage=smart_coverage(data, event_analysis),
        primary_issue=primary_issue,
        why_it_matters=why_it_matters,
        target_doctor=target_doctor,
        extra={"penalty_groups": penalty_groups},
    )
