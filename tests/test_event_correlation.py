from openfix.diagnostics.events import analyze_event_logs, correlate_events


def event(category, timestamp, provider="X", event_id=1):
    return {
        "category": category,
        "time_created": timestamp,
        "provider": provider,
        "id": event_id,
        "level": "Error",
        "serious": True,
    }


def test_graphics_shutdown_nearby_are_correlated():
    items = [
        event("Graphics", "2026-09-12T00:00:00+00:00"),
        event("Unexpected Shutdown", "2026-09-12T00:03:00+00:00"),
    ]
    result = correlate_events(items, window_minutes=5)
    assert result
    assert result[0]["route"] == "gaming"
    assert result[0]["confidence"] == "possible"


def test_far_apart_events_are_not_correlated():
    items = [
        event("Graphics", "2026-09-12T00:00:00+00:00"),
        event("Unexpected Shutdown", "2026-09-12T00:20:00+00:00"),
    ]
    assert correlate_events(items, window_minutes=5) == []


def test_analysis_omits_raw_event_message_from_important_output():
    package = {
        "available": True,
        "events": [
            {
                "provider": "Application Error",
                "id": 1000,
                "level": "Error",
                "message": "C:\\Users\\PrivateName\\secret-file.txt",
                "time_created": "2026-09-12T00:00:00+00:00",
                "log_name": "Application",
            }
        ],
    }
    result = analyze_event_logs(package)
    assert result["important"]
    assert "message" not in result["important"][0]
