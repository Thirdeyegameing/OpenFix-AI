from openfix.diagnostics.events import analyze_event_logs


def pack(provider, event_id, level="Error", message="x", time_created="2026-09-12T00:00:00"):
    return {
        "available": True,
        "events": [{
            "provider": provider,
            "id": event_id,
            "level": level,
            "message": message,
            "time_created": time_created,
        }],
    }


def test_corrected_whea_is_warning_not_serious_error():
    result = analyze_event_logs(pack("Microsoft-Windows-WHEA-Logger", 17, "Warning", "Corrected hardware error"))
    assert result["hardware_warnings"] == 1
    assert result["hardware_errors"] == 0


def test_serious_whea_18_is_hardware_error():
    result = analyze_event_logs(pack("Microsoft-Windows-WHEA-Logger", 18, "Error", "fatal hardware error"))
    assert result["hardware_errors"] == 1


def test_6008_requires_eventlog_provider():
    result = analyze_event_logs(pack("SomeOtherProvider", 6008, "Error", "x"))
    assert result["shutdown_errors"] == 0
    assert result["generic_errors"] == 1


def test_6008_eventlog_is_shutdown():
    result = analyze_event_logs(pack("EventLog", 6008, "Error", "previous shutdown unexpected"))
    assert result["shutdown_errors"] == 1


def test_1000_requires_application_error_provider():
    result = analyze_event_logs(pack("OtherProvider", 1000, "Error", "x"))
    assert result["app_crashes"] == 0


def test_timestamp_survives_analysis():
    result = analyze_event_logs(pack("Application Error", 1000, "Error", "crash", "2026-09-12T00:01:02"))
    assert result["important"][0]["time_created"] == "2026-09-12T00:01:02"


def test_dcom_10016_not_relevant():
    result = analyze_event_logs(pack("DistributedCOM", 10016, "Error", "permission"))
    assert result["ignored_noise"] == 1
    assert result["relevant_events"] == 0
