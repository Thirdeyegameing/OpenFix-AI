# OpenFix AI Development Foundation

Current development version: **v0.5.2-dev11**

This version begins the production-oriented project structure. The application remains local-first and read-only.

## Architecture

- `openfix/core/` — shared helpers, PowerShell execution, scan worker, logging
- `openfix/diagnostics/` — raw Windows/system measurements
- `openfix/doctors/` — interpretation and scoring rules
- `openfix/ui/` — PySide6 user interface
- `openfix/models.py` — shared status/result model definitions for future migration
- `tests/` — regression tests for parsers and classification rules

## Safety rules

- No Cloud AI
- No OpenAI API
- No external AI API
- No automatic Registry edits
- No automatic driver removal
- No automatic service changes
- Missing data is not treated as hardware failure
- Scores are estimates, not hardware verdicts


## Hotfix 2
- Fixed a runtime NameError in `find_system_drive()` caused by a missing `os` import.
- Fixed a latent missing `json` import in network adapter parsing.
- Scan failures now display `SCAN FAILED` instead of a misleading 100/100 healthy score.
- Full Scan summary exits the scanning state when an internal scan error occurs.
- Added regression tests for both missing-import paths.
