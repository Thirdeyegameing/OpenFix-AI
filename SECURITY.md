# OpenFix AI Security Policy

OpenFix AI v1.0.0 is intentionally designed as a **local, read-only diagnostic application**.

## Security boundaries

OpenFix v1.0 does not intentionally:

- request Administrator elevation;
- edit the Windows Registry;
- install, remove, or update drivers;
- start, stop, disable, or reconfigure Windows services;
- modify network settings;
- delete user files;
- run automatic repair commands;
- upload diagnostic scans;
- use Cloud AI, OpenAI API, or external AI APIs.

PowerShell diagnostics pass through a centralized read-only command guard as defense in depth. This guard is not a substitute for code review, so changes to diagnostic commands should also be reviewed and covered by tests.

## Local data

OpenFix writes rotating application logs locally. Common user-home paths and MAC-address patterns are redacted by the logger. Raw Windows Event messages are used transiently for local classification but are not copied into analyzed result objects intended for display/sharing.

OpenFix v1.0 does not persist a scan-history database.

## Connectivity checks

Internet Doctor performs ordinary DNS, TCP-connectivity, and ICMP tests against fixed diagnostic targets. These are network reachability checks and are not telemetry or AI requests.

## Reporting a security issue

Do not post secrets, tokens, passwords, or personally identifying diagnostic data in a public issue. If a security concern could expose user data or allow system modification, disclose only the minimum reproduction details needed until a private reporting channel is available.
