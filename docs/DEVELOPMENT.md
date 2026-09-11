# OpenFix AI Development Notes

Current stable version: **v1.0.0**

OpenFix is a local-first, read-only Windows diagnostics project. The first stable release prioritizes correctness, conservative wording, privacy, and failure safety over automatic repair features.

## Engineering rules

1. Missing data is not a hardware failure.
2. A diagnostic failure must never become a 100/100 health result.
3. Smart Doctor must not double-count one underlying problem across multiple correlated signals.
4. No Cloud AI or external AI API may be introduced into the diagnostic path.
5. No telemetry or scan upload.
6. No automatic privilege elevation.
7. PowerShell diagnostic commands must remain read-only and pass the centralized safety guard.
8. New diagnostic claims require regression tests.
9. Event correlation is evidence of timing only, never proof of causation.
10. Unsupported sensor/health data must be shown as unavailable, not healthy.

## Stable release scope

v1.0 includes Dashboard, Full System Scan, Internet Doctor, Gaming Doctor, Slow PC Doctor, Storage Doctor, Windows Event Doctor, Local Smart Doctor, physical-disk status when Windows exposes it, structured network checks, local rotating logs, safety tests, and Windows CI.

Automatic repair tools are outside the v1.0 scope.
