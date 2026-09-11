# OpenFix AI v1.0.0 — First Stable Release

OpenFix AI v1.0.0 is the first stable source release of the project.

## Highlights

- Modern local PC health dashboard
- Full System Scan
- Internet, Gaming, Slow PC, Storage, and Windows Event Doctors
- Local Smart Doctor with prioritized recommendations
- Health Score separated from Scan Coverage
- Conservative handling of unavailable data
- Structured network connectivity tests
- Read-only physical-disk health/status when Windows exposes it
- Windows Event filtering and conservative time correlation
- Multi-GPU detection improvements
- Local rotating logs with basic privacy redaction
- Central read-only PowerShell safety guard
- Regression tests and Windows GitHub Actions CI

## Safety

v1.0 remains read-only. It does not automatically repair Windows, edit Registry values, remove drivers, change services, elevate to Administrator, upload scans, or use Cloud AI / external AI APIs.

## Important limitation

A diagnostic score is an estimate. OpenFix cannot certify that hardware is healthy or broken. Important findings should be confirmed with dedicated hardware/vendor diagnostics before replacing components.
