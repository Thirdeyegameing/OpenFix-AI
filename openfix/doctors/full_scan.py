from openfix.core.helpers import make_result
from openfix.diagnostics.collector import smart_coverage
from openfix.doctors.internet import doctor_internet
from openfix.doctors.gaming import doctor_gaming
from openfix.doctors.slow_pc import doctor_slow_pc
from openfix.doctors.storage import doctor_storage
from openfix.doctors.events import create_event_result
from openfix.doctors.smart import doctor_smart

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

    weighted_total = 0
    weight_total = 0
    healthy = 0
    attention = 0
    unavailable = 0
    facts = []

    for name, result, weight, route in independent:
        coverage = result.get("coverage") or 0
        if coverage <= 0:
            unavailable += 1
            facts.append(f"{name}: unavailable.")
            continue

        weighted_total += result["score"] * weight
        weight_total += weight
        facts.append(f"{name}: {result['score']}/100.")

        if result["score"] >= 90:
            healthy += 1
        else:
            attention += 1

    overall = round(weighted_total / weight_total) if weight_total > 0 else 100
    coverage = smart_coverage(data, event_analysis)
    facts.append(f"Local Smart Doctor: {smart['score']}/100.")
    facts.append(f"Scan coverage: {coverage}%.")

    primary_issue = smart.get("primary_issue")
    why_it_matters = smart.get("why_it_matters")
    target_doctor = smart.get("target_doctor")

    if primary_issue is None and attention > 0:
        available_results = [item for item in independent if (item[1].get("coverage") or 0) > 0]
        if available_results:
            lowest = min(available_results, key=lambda item: item[1]["score"])
            primary_issue = f"{lowest[0]} has the lowest diagnostic score."
            why_it_matters = "This area currently deserves more attention than the other available diagnostic areas."
            target_doctor = lowest[3]

    return make_result(
        "Full System Scan",
        overall,
        facts,
        smart["issues"][:5],
        smart["actions"][:6],
        "The overall score uses independent diagnostic areas. Missing information is not counted as healthy and is not treated as a hardware fault.",
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
            "smart_score": smart["score"],
        },
    )
