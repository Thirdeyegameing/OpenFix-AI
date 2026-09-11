from openfix.config import SCORE_HEALTHY
from openfix.core.helpers import make_result
from openfix.diagnostics.collector import smart_coverage
from openfix.doctors.events import create_event_result
from openfix.doctors.gaming import doctor_gaming
from openfix.doctors.internet import doctor_internet
from openfix.doctors.slow_pc import doctor_slow_pc
from openfix.doctors.smart import doctor_smart
from openfix.doctors.storage import doctor_storage


def doctor_full(data, event_package):
    event_result = create_event_result(event_package)
    event_analysis = event_result["event_analysis"]

    internet = doctor_internet(data)
    gaming = doctor_gaming(data)
    slow = doctor_slow_pc(data)
    storage = doctor_storage(data)
    smart = doctor_smart(data, event_analysis)

    independent = [
        ("Internet", internet, 0.20, "internet"),
        ("Gaming", gaming, 0.15, "gaming"),
        ("Slow PC", slow, 0.15, "slow"),
        ("Storage", storage, 0.20, "storage"),
        ("Windows Events", event_result, 0.30, "events"),
    ]

    weighted_total = 0.0
    weight_total = 0.0
    healthy = 0
    attention = 0
    unavailable = 0
    facts = []

    for name, result, weight, route in independent:
        coverage = result.get("coverage") or 0
        score = result.get("score")
        if coverage <= 0 or score is None:
            unavailable += 1
            facts.append(f"{name}: unavailable.")
            continue

        weighted_total += score * weight
        weight_total += weight
        facts.append(f"{name}: {score}/100.")

        if score >= SCORE_HEALTHY:
            healthy += 1
        else:
            attention += 1

    overall = round(weighted_total / weight_total) if weight_total > 0 else None
    coverage = smart_coverage(data, event_analysis)
    smart_score = smart.get("score")
    facts.append(
        f"Local Smart Doctor: {smart_score}/100." if smart_score is not None else "Local Smart Doctor: unavailable."
    )
    facts.append(f"Scan coverage: {coverage}%.")

    primary_issue = smart.get("primary_issue")
    why_it_matters = smart.get("why_it_matters")
    target_doctor = smart.get("target_doctor")

    if primary_issue is None and attention > 0:
        available_results = [
            item
            for item in independent
            if (item[1].get("coverage") or 0) > 0 and item[1].get("score") is not None
        ]
        if available_results:
            lowest = min(available_results, key=lambda item: item[1]["score"])
            primary_issue = f"{lowest[0]} has the lowest diagnostic score."
            why_it_matters = "This area currently deserves more attention than the other available diagnostic areas."
            target_doctor = lowest[3]

    if overall is None:
        primary_issue = "Not enough diagnostic data was available to calculate a health score."
        why_it_matters = "OpenFix avoids showing 100/100 when the system could not actually be evaluated."
        target_doctor = None

    return make_result(
        "Full System Scan",
        overall,
        facts,
        smart.get("issues", [])[:5],
        smart.get("actions", [])[:6],
        "The overall score uses independent diagnostic areas. Unavailable information is excluded from scoring and is never counted as healthy.",
        coverage=coverage,
        primary_issue=primary_issue,
        why_it_matters=why_it_matters,
        target_doctor=target_doctor,
        healthy_areas=healthy,
        attention_areas=attention,
        unavailable_areas=unavailable,
        extra={
            "dashboard_data": data,
            "event_analysis": event_analysis,
            "smart_score": smart_score,
        },
    )
