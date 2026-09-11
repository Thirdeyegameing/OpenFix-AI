from openfix.core.helpers import make_result
from openfix.diagnostics.collector import gaming_coverage

def doctor_gaming(data):
    score = 100
    facts, issues, actions = [], [], []
    primary = None
    why = None

    cpu = data["cpu"]
    ram = data["memory"]["percent"]
    gpu = data["gpu"]
    network = data["network"]

    if cpu is not None:
        facts.append(f"CPU usage: {cpu:.0f}%.")
        if cpu >= 95:
            score -= 25
            issues.append("CPU usage is extremely high.")
            actions.append("Check Task Manager for applications using a lot of CPU while the game is running.")
            primary = "CPU usage is extremely high."
            why = "Very high CPU usage can cause stuttering, frame-time spikes and slow background tasks."
        elif cpu >= 85:
            score -= 12
            issues.append("CPU usage is high.")
            actions.append("Close unnecessary CPU-heavy applications before playing.")

    if ram is not None:
        facts.append(f"RAM usage: {ram:.0f}%.")
        if ram >= 95:
            score -= 25
            issues.append("RAM usage is extremely high.")
            actions.append("Close unnecessary RAM-heavy applications before playing.")
            if primary is None:
                primary = "RAM usage is extremely high."
                why = "When RAM is nearly full, Windows may rely more heavily on the page file and games can stutter."
        elif ram >= 85:
            score -= 12
            issues.append("RAM usage is high.")
            actions.append("Reduce unnecessary background applications before launching the game.")

    if gpu["available"]:
        facts.append(f"Graphics device: {gpu['name']}.")

    temperature = gpu["temperature"]
    if temperature is None:
        facts.append("GPU temperature sensor data is not available on this system.")
    else:
        facts.append(f"GPU temperature: {temperature:.0f}°C.")
        if temperature >= 90:
            score -= 30
            issues.append("GPU temperature is dangerously high.")
            actions.append("Check GPU cooling, fans, dust and case airflow.")
            primary = "GPU temperature is dangerously high."
            why = "Excessive GPU temperature can cause thermal throttling, crashes and reduced performance."
        elif temperature >= 83:
            score -= 12
            issues.append("GPU temperature is higher than ideal.")
            actions.append("Check case airflow and GPU cooling if this temperature persists during gaming.")

    loss = network["packet_loss"]
    if loss is not None and loss >= 3:
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
        coverage=gaming_coverage(data),
        primary_issue=primary,
        why_it_matters=why,
        target_doctor="gaming" if issues else None,
    )
