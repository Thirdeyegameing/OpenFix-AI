from openfix.core.helpers import make_result
from openfix.diagnostics.events import analyze_event_logs


def create_event_result(package):
    analysis = analyze_event_logs(package)

    if not analysis["available"]:
        return make_result(
            "Windows Event Doctor",
            None,
            ["Windows Event data could not be read."],
            [],
            ["Run the scan again. If it repeats, check OpenFix logs."],
            "No health score was produced because Event Log data was unavailable. Missing data is not treated as a fault.",
            coverage=0,
            extra={"event_analysis": analysis},
        )

    score = 100
    facts = [
        f"Windows events checked: {analysis['total']}.",
        f"Relevant events: {analysis['relevant_events']}.",
        f"Ignored background events: {analysis['ignored_noise']}.",
    ]
    issues, actions = [], []
    primary = None
    why = None

    if analysis["hardware_errors"]:
        count = analysis["hardware_errors"]
        score -= min(45, count * 25)
        issues.append(f"{count} serious hardware-related event(s) were recorded.")
        actions.append("Use dedicated hardware diagnostics before changing Windows settings.")
        primary = "Windows recorded possible hardware errors."
        why = "Serious hardware-level errors deserve higher priority because they may indicate instability below the application level."

    if analysis["hardware_warnings"]:
        count = analysis["hardware_warnings"]
        score -= min(8, count * 2)
        facts.append(f"Corrected hardware warning(s): {count}.")

    if analysis["storage_errors"]:
        count = analysis["storage_errors"]
        score -= min(35, count * 15)
        issues.append(f"{count} important storage-related event(s) were recorded.")
        actions.append("Back up important files and check drive health.")
        if primary is None:
            primary = "Windows recorded storage-related errors."
            why = "Storage errors can affect file reliability, application loading and Windows stability."

    if analysis["shutdown_errors"]:
        count = analysis["shutdown_errors"]
        score -= min(30, count * 15)
        issues.append(f"{count} unexpected shutdown event(s) were detected.")
        actions.append("Check recent crashes, temperatures and power stability.")
        if primary is None:
            primary = "Unexpected shutdown events were recorded."
            why = "Unexpected shutdowns can be related to crashes, power problems or temperature issues."

    if analysis["gpu_errors"]:
        count = analysis["gpu_errors"]
        score -= min(25, count * 10)
        issues.append(f"{count} graphics-related error event(s) were detected.")
        actions.append("Check graphics stability if display problems or crashes are occurring.")
        if primary is None:
            primary = "Windows recorded graphics-related errors."
            why = "Graphics errors can be related to drivers, GPU stability or display crashes."

    if analysis["app_crashes"]:
        count = analysis["app_crashes"]
        score -= min(15, count * 5)
        issues.append(f"{count} application crash event(s) were detected.")
        actions.append("Identify the application that crashed before changing drivers or Windows.")

    if analysis["generic_errors"]:
        score -= min(5, analysis["generic_errors"])
        facts.append(f"Other relevant Windows errors: {analysis['generic_errors']}.")

    if analysis["important"]:
        facts.append("Important recent events:")
        for event in analysis["important"][:5]:
            timestamp = event.get("time_created") or "time unavailable"
            facts.append(
                f"[{event['category']}] {event['provider']} (Event ID {event['id']}, {timestamp})"
            )

    if analysis.get("correlations"):
        facts.append("Possible event relationships:")
        for correlation in analysis["correlations"][:3]:
            facts.append(
                f"{correlation['description']} ({correlation['seconds_apart']} seconds apart; correlation only, not proof of cause)."
            )

    return make_result(
        "Windows Event Doctor",
        score,
        facts,
        issues,
        actions,
        "Windows can contain harmless warnings and errors even when the PC is working normally. OpenFix emphasizes relevant events instead of raw error counts.",
        coverage=100,
        primary_issue=primary,
        why_it_matters=why,
        target_doctor="events" if issues else None,
        extra={"event_analysis": analysis},
    )
