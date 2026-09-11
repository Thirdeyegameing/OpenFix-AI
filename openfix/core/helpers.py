from datetime import datetime

def clamp(value, minimum=0, maximum=100):
    return max(minimum, min(maximum, value))

def safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default

def safe_float(value, default=None):
    try:
        return float(value)
    except Exception:
        return default

def format_bytes(value):
    if value is None:
        return "Not available"
    try:
        value = float(value)
        if value >= 1024 ** 3:
            return f"{value / (1024 ** 3):.1f} GB"
        return f"{value / (1024 ** 2):.0f} MB"
    except Exception:
        return "Not available"

def format_uptime(seconds):
    if seconds is None:
        return "Not available"
    try:
        seconds = int(seconds)
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        minutes = (seconds % 3600) // 60
        if days > 0:
            return f"{days}d {hours}h"
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"
    except Exception:
        return "Not available"

def format_prioritized_actions(items, limit=7):
    if not items:
        return []

    unique = []
    seen = set()
    for priority, text in sorted(items, key=lambda item: item[0]):
        if text in seen:
            continue
        seen.add(text)
        unique.append((priority, text))

    formatted = []
    for index, (priority, text) in enumerate(unique[:limit]):
        if index == 0:
            prefix = "Do first"
        elif priority <= 2:
            prefix = "Next"
        else:
            prefix = "Later"
        formatted.append(f"{prefix}: {text}")
    return formatted

def make_result(
    title,
    score,
    facts=None,
    issues=None,
    actions=None,
    note="",
    coverage=None,
    primary_issue=None,
    why_it_matters=None,
    target_doctor=None,
    healthy_areas=None,
    attention_areas=None,
    unavailable_areas=None,
    extra=None,
):
    result = {
        "title": title,
        "score": clamp(int(score)),
        "facts": facts or [],
        "issues": issues or [],
        "actions": actions or [],
        "note": note,
        "coverage": coverage,
        "primary_issue": primary_issue,
        "why_it_matters": why_it_matters,
        "target_doctor": target_doctor,
        "healthy_areas": healthy_areas,
        "attention_areas": attention_areas,
        "unavailable_areas": unavailable_areas,
        "scan_time": datetime.now().strftime("%H:%M:%S"),
    }
    if extra:
        result.update(extra)
    return result

