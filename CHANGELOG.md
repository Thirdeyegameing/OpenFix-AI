# Changelog

## v1.0.0 — First Stable Release

OpenFix AI v1.0.0 promotes the Reliability Gate foundation into the first stable source release.

### Reliability and safety

- Stable version contract set to `1.0.0`.
- Central read-only PowerShell guard blocks common mutating and remote-request cmdlets.
- PowerShell runner no longer uses ExecutionPolicy bypass and runs non-interactively without `shell=True`.
- No automatic Administrator elevation.
- No Cloud AI, OpenAI API, external AI API, telemetry, or scan upload.
- Local rotating logs now redact common user-home paths and MAC-address patterns.
- Network diagnostics no longer collect MAC addresses.
- Raw Windows Event messages are omitted from analyzed/shareable result objects.

### Diagnostics

- Added read-only Windows physical-disk health and operational-status collection when supported.
- Storage Doctor can surface explicit Windows physical-disk Warning/Unhealthy states conservatively.
- Added conservative Event Log time correlation for selected related event categories.
- Event correlation never claims causation and does not add duplicate score penalties by itself.
- Smart Doctor can prioritize explicit physical-storage warnings and correlated events.
- Existing Internet, Gaming, Slow PC, Storage, Event, Smart Doctor, Full Scan, coverage, and unavailable-data logic retained and hardened.

### Release quality

- Expanded regression and safety tests.
- Stable README, SECURITY policy, release notes, license, and project metadata.
- GitHub Actions continues compile + regression testing on Windows.

## v0.5.2-dev12 — Reliability Gate

- Correct unavailable-score behavior.
- Mode-specific diagnostic collectors.
- Structured network diagnostics.
- Improved Event Log filtering and classification.
- Adaptive storage-space scoring.
- Local rotating logs.
- Modular production foundation and CI.
