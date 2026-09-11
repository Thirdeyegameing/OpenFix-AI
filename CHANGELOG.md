# Changelog

## v0.5.2-dev12 — Reliability Gate

- Added unavailable/N/A diagnostic scores when data cannot be evaluated.
- Fixed Full Scan fallback that could previously produce 100/100 with zero usable coverage.
- Separated internet connectivity from ICMP ping reachability.
- Added structured PowerShell ping measurements.
- Added focused per-Doctor data collectors.
- Added safe scan-thread lifecycle handling.
- Added central thresholds and adaptive storage scoring.
- Improved Windows Event provider classification and WHEA handling.
- Preserved Event Log timestamps for future correlation.
- Added rotating LocalAppData logging.
- Improved GPU temperature-unavailable presentation.
- Grouped RAM processes by application name.
- Added pytest project configuration and Windows GitHub Actions CI.
- Expanded regression suite to 34 tests.
