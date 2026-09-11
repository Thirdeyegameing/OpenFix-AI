from openfix.core.helpers import make_result
from openfix.diagnostics.events import analyze_event_logs

def create_event_result(package):
    analysis = analyze_event_logs(package)

    if not analysis["available"]:
        return make_result(
            "Windows Event Doctor",
            100,
            [],
            [],
            [],
            "Windows Event data could not be read. The score was not reduced because missing data is not a fault.",
            coverage=0,
            extra={"event_analysis": analysis},
        )

    score = 100
    facts = [
        f"Windows events checked: {analysis['total']}.",
        f"Errors recorded: {analysis['errors']}.",
        f"Warnings recorded: {analysis['warnings']}.",
    ]
    issues, actions = [], []
    primary = None
    why = None

    if analysis["ignored_noise"]:
        facts.append(f"Common background events ignored: {analysis['ignored_noise']}.")

    if analysis["hardware_errors"]:
        count = analysis["hardware_errors"]
        score -= min(45, count * 25)
        issues.append(f"{count} possible hardware error event(s) were recorded.")
        actions.append("Use dedicated hardware diagnostics before changing Windows settings.")
        primary = "Windows recorded possible hardware errors."
        why = "Hardware-level errors deserve higher priority because they may indicate instability below the application level."

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
        facts.append(f"Other Windows errors: {analysis['generic_errors']}.")

    if analysis["important"]:
        facts.append("Important recent events:")
        for event in analysis["important"][:5]:
            facts.append(f"[{event['category']}] {event['provider']} (Event ID {event['id']})")

    return make_result(
        "Windows Event Doctor",
        score,
        facts,
        issues,
        actions,
        "Windows can contain harmless warnings and errors even when the PC is working normally.",
        coverage=100,
        primary_issue=primary,
        why_it_matters=why,
        target_doctor="events" if issues else None,
        extra={"event_analysis": analysis},
    )
