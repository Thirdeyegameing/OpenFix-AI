# OpenFix AI Development

Current development version: **v0.5.2-dev12 — Reliability Gate**

OpenFix is a local-first, read-only Windows diagnostics project. dev12 focuses on correctness, failure handling, test coverage, and a production-ready diagnostic foundation rather than adding more Doctor modes.

## What changed in dev12

### Reliability

- A diagnostic area with no usable data now reports **N/A / UNAVAILABLE** instead of a misleading 100/100 score.
- Full Scan excludes unavailable areas from weighted scoring and never counts them as healthy.
- Scan worker output now uses `result_ready` instead of shadowing `QThread.finished`.
- Closing the window while a scan is running is blocked safely until the worker finishes.
- Logging moved to `%LOCALAPPDATA%/OpenFix/logs` on Windows with rotating log files and a local fallback.

### Focused collectors

Doctor scans now collect only what they need:

- Internet Doctor → network only
- Gaming Doctor → CPU, RAM, GPU, network
- Slow PC Doctor → CPU, RAM, processes, system drive
- Storage Doctor → drives only
- Smart Doctor / Full Scan → full system snapshot
- Windows Event Doctor → Event Logs only

This reduces scan time and limits unrelated failure points.

### Network accuracy

- Internet connectivity is separate from ICMP ping.
- A blocked ping no longer automatically means the internet is offline.
- External connectivity uses ordinary TCP/DNS checks; no AI or external diagnostic API is used.
- Active adapter, gateway, DNS, and route metrics are collected from one route snapshot.
- Default-route selection accounts for route metric + interface metric.
- Ping uses structured PowerShell output so normal scans do not depend on Windows display language.

### Windows Event accuracy

- Event timestamps are preserved for future correlation work.
- DCOM 10016 and CAPI2 noise remain filtered.
- Event ID 6008 now requires the EventLog provider.
- Application crash ID 1000 now requires the Application Error provider.
- Corrected WHEA warnings are separated from more serious WHEA errors.
- UI-facing facts emphasize relevant events instead of raw error counts.

### Storage accuracy

- System/fixed drives affect storage health; removable/network/optical drives do not reduce PC health score.
- Storage thresholds use both free GB and free percentage so very large drives are not warned solely because the percentage is low.
- System drive and data drive thresholds are treated differently.

### UI meaning

- `TEMP N/A` means the GPU was detected but temperature data is unavailable; the whole GPU is no longer shown as unavailable.
- Dashboard wording now says **System Snapshot** instead of implying live monitoring.
- Installed RAM and usable RAM are distinguished where physical-memory data is available.
- Top RAM display groups processes by application name.

## Architecture

- `openfix/core/` — shared result, logging, scoring, PowerShell, scan worker
- `openfix/diagnostics/` — raw Windows/system measurements and focused collectors
- `openfix/doctors/` — interpretation and scoring rules
- `openfix/ui/` — PySide6 user interface
- `openfix/models.py` — shared diagnostic result and status models
- `tests/` — regression tests
- `.github/workflows/tests.yml` — Windows CI test matrix

## Test status

Development package validation:

- Python compile check: passed
- Regression tests: **34 passed**
- `pytest -q` is configured through `pytest.ini`
- GitHub Actions tests Python 3.10–3.13 on Windows after push

PySide6 GUI runtime still needs a real Windows launch test because the build environment used to prepare this package does not include PySide6.

## Safety rules

- No Cloud AI
- No OpenAI API
- No external AI API
- No automatic Registry edits
- No automatic driver removal
- No automatic service changes
- Missing data is not treated as hardware failure
- Scores are estimates, not hardware verdicts
