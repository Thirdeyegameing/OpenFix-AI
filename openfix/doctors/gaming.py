from openfix import config
from openfix.core.helpers import make_result
from openfix.diagnostics.collector import gaming_coverage


def doctor_gaming(data):
    coverage = gaming_coverage(data)
    if coverage <= 0:
        return make_result(
            "Gaming Doctor",
            None,
            ["Gaming diagnostic signals could not be collected."],
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
    ram = data.get("memory", {}).get("percent")
    gpu = data.get("gpu", {})
    network = data.get("network", {})

    if cpu is not None:
        facts.append(f"CPU usage: {cpu:.0f}%.")
        if cpu >= config.CPU_CRITICAL:
            score -= 25
            issues.append("CPU usage is extremely high.")
            actions.append("Check Task Manager for applications using a lot of CPU while the game is running.")
            primary = "CPU usage is extremely high."
            why = "Very high CPU usage can cause stuttering, frame-time spikes and slow background tasks."
        elif cpu >= config.CPU_HIGH:
            score -= 12
            issues.append("CPU usage is high.")
            actions.append("Close unnecessary CPU-heavy applications before playing.")

    if ram is not None:
        facts.append(f"RAM usage: {ram:.0f}%.")
        if ram >= config.RAM_CRITICAL:
            score -= 25
            issues.append("RAM usage is extremely high.")
            actions.append("Close unnecessary RAM-heavy applications before playing.")
            if primary is None:
                primary = "RAM usage is extremely high."
                why = "When RAM is nearly full, Windows may rely more heavily on the page file and games can stutter."
        elif ram >= config.RAM_HIGH:
            score -= 12
            issues.append("RAM usage is high.")
            actions.append("Reduce unnecessary background applications before launching the game.")

    if gpu.get("available"):
        facts.append(f"Graphics device: {gpu.get('name', 'Unknown')}.")

    temperature = gpu.get("temperature")
    if gpu.get("available") and temperature is None:
        facts.append("GPU detected, but temperature sensor data is not available on this system.")
    elif temperature is not None:
        facts.append(f"GPU temperature: {temperature:.0f}°C.")
        if temperature >= config.GPU_HOT_C:
            score -= 30
            issues.append("GPU temperature is dangerously high.")
            actions.append("Check GPU cooling, fans, dust and case airflow.")
            primary = "GPU temperature is dangerously high."
            why = "Excessive GPU temperature can cause thermal throttling, crashes and reduced performance."
        elif temperature >= config.GPU_WARM_C:
            score -= 12
            issues.append("GPU temperature is higher than ideal.")
            actions.append("Check case airflow and GPU cooling if this temperature persists during gaming.")

    loss = network.get("packet_loss")
    if network.get("icmp_reachable") is True and loss is not None and loss >= config.PACKET_LOSS_WARN:
        score -= 15
        issues.append("Network instability may cause online-game lag.")
        actions.append("Check the network connection before lowering graphics settings.")
        if primary is None:
            primary = "Network instability may affect online games."
            why = "Packet loss can cause rubber-banding and delayed actions even when FPS is high."

    return make_result(
        "Gaming Doctor",
        score,
        facts,
        issues,
        actions,
        "This scan checks common system conditions. It does not currently measure in-game FPS or frame time.",
        coverage=coverage,
        primary_issue=primary,
        why_it_matters=why,
        target_doctor="gaming" if issues else None,
    )
