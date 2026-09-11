# OpenFix AI

**Current version: v1.0.0 — First Stable Release**

OpenFix AI is an open-source Windows diagnostic and troubleshooting application for people who want a clearer explanation of what may be happening inside their PC.

> Scan the PC, measure what is available, identify possible problems, explain why they matter, and suggest safe next steps.

OpenFix AI is built around a **local-first, read-only, privacy-focused** design.

- No Cloud AI
- No OpenAI API
- No external AI API
- No telemetry or scan uploads
- No automatic Registry edits
- No automatic driver removal
- No automatic Windows service changes
- No automatic repair commands
- No Administrator elevation request by design

---

## What v1.0.0 Includes

### System Health Dashboard

The dashboard provides a local snapshot of:

- CPU usage
- RAM usage
- Windows drive free space
- Internet connectivity and latency
- GPU detection and temperature when available
- Windows Event status
- Windows version and build
- CPU model
- Installed / usable RAM
- GPU driver information
- PC uptime
- Active network adapter
- Top RAM-consuming applications
- Scan coverage
- Estimated System Health score

OpenFix separates **health** from **coverage**. Unsupported sensors or unavailable information do not automatically count as a fault.

### Full System Scan

Full System Scan combines independent diagnostic areas:

- Internet
- Gaming
- Slow PC
- Storage
- Windows Events

Local Smart Doctor analyzes the collected information but is not counted as a second independent health area, which helps avoid double-counting the same problem.

### Internet Doctor

Checks:

- Active network adapter
- Default route / gateway
- DNS resolution
- External TCP connectivity
- ICMP ping when available
- Response time
- Packet loss

Internet connectivity is evaluated separately from Ping. A firewall, VPN, or network policy can block ICMP while normal internet access still works.

### Gaming Doctor

Checks common conditions that may affect gaming:

- CPU pressure
- RAM pressure
- GPU detection
- GPU temperature when supported
- Network latency
- Packet loss

Gaming Doctor does not claim to measure in-game FPS or frame time.

### Slow PC Doctor

Checks:

- CPU usage
- RAM usage
- RAM-heavy applications
- Windows drive free space
- Current resource pressure

For the most useful result, run it while the PC actually feels slow.

### Storage Doctor

Checks:

- Windows system drive free space
- Local fixed-drive free space
- Drive classification
- Read-only Windows physical-disk health when available
- Physical-disk operational status
- Media type and bus type when Windows reports them
- Physical-disk temperature when Windows exposes it

OpenFix does **not** treat missing SMART / reliability data as proof that a drive is healthy or unhealthy. An explicit Windows `Warning`, `Unhealthy`, or degraded operational state is treated as a reason to investigate and back up important files, not as an absolute hardware verdict.

Serial numbers and unique physical-disk identifiers are intentionally not collected.

### Windows Event Doctor

Analyzes recent System and Application events while filtering common background noise.

Examples of higher-value categories include:

- Serious WHEA hardware errors
- Corrected WHEA warnings
- Kernel-Power Event ID 41
- EventLog Event ID 6008
- Storage-related errors
- Graphics-related errors
- Application Error Event ID 1000

Common low-value noise such as DistributedCOM 10016 and common CAPI2 events is filtered.

v1.0 can also identify **possible time-nearby relationships** between certain events, for example a graphics event occurring close to an unexpected shutdown. Correlation is shown as a possible relationship only; OpenFix does not claim that one event caused the other.

### Local Smart Doctor

Smart Doctor uses built-in local rules to combine measured facts and prioritize what deserves attention first.

Examples include:

- High RAM usage + one RAM-heavy application
- Low storage + storage-related Event Log errors
- Explicit physical-disk warning + storage events
- GPU error + high GPU temperature
- Good response time + packet loss
- Unexpected shutdown + nearby hardware/graphics/storage event

Recommendations are ordered as:

- **Do first**
- **Next**
- **Later**

Smart Doctor also provides:

- Primary Issue
- Why this matters
- Top Recommendations
- Possible Problems
- Detailed Scan Information

Smart Doctor is **not a cloud AI service**. It runs from local diagnostic rules in the OpenFix codebase.

---

## Safety Design

Safety is a release requirement, not an optional feature.

### Read-only PowerShell guard

OpenFix centralizes PowerShell execution behind a read-only safety guard. Common mutating command families such as `Set-*`, `Remove-*`, `Disable-*`, repair commands, Registry write commands, service modification commands, and remote web request cmdlets are blocked by the diagnostic runner.

The diagnostic scripts currently use read-only Windows queries such as CIM/WMI, Event Log reads, network reads, and connectivity tests.

### No automatic elevation

OpenFix does not request Administrator elevation. If Windows refuses access to a diagnostic source, OpenFix should report that information as unavailable rather than silently escalating privileges.

### No telemetry

OpenFix does not upload scan results, Event Log data, or hardware information to a server.

Normal Internet Doctor checks may contact fixed diagnostic targets for DNS, TCP connectivity, and ping. These are connectivity checks, not telemetry or AI services.

### Local logs only

Application logs are stored locally under the OpenFix application-data directory on Windows and use rotation to avoid unlimited growth.

The log formatter redacts common user-home paths and MAC-address patterns before writing log text. Raw Windows Event messages are not included in analyzed result objects shown for sharing.

### No background scan history in v1.0

OpenFix v1.0 does not persist a database of previous PC scans. This keeps the first stable release simpler and reduces unnecessary local data collection.

---

## Understanding Scores

OpenFix scores are **estimated diagnostic scores**, not hardware certification.

- A low score does not prove that hardware is broken.
- A score of 100 does not prove that every component is perfect.
- `UNAVAILABLE` means OpenFix did not have enough information to produce a reliable score.
- `PARTIAL` means useful data was collected, but some planned checks were unavailable.

Important hardware concerns should be confirmed with dedicated manufacturer or specialist diagnostic tools before replacing hardware.

---

## Requirements

- Windows 10 or Windows 11
- Python 3.10 or newer
- PySide6
- psutil
- Windows PowerShell

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Start OpenFix:

```bash
py main.py
```

or:

```bash
python main.py
```

`START_OPENFIX.bat` is also included for convenience on Windows.

---

## Project Structure

```text
OpenFix-AI/
│
├─ main.py
├─ START_OPENFIX.bat
├─ requirements.txt
├─ requirements-dev.txt
├─ pyproject.toml
├─ README.md
├─ CHANGELOG.md
├─ SECURITY.md
├─ RELEASE_NOTES_v1.0.0.md
├─ LICENSE
│
├─ openfix/
│  ├─ app.py
│  ├─ config.py
│  ├─ models.py
│  │
│  ├─ core/
│  │  ├─ helpers.py
│  │  ├─ logger.py
│  │  ├─ powershell.py
│  │  ├─ scanner.py
│  │  └─ scoring.py
│  │
│  ├─ diagnostics/
│  │  ├─ collector.py
│  │  ├─ events.py
│  │  ├─ gpu.py
│  │  ├─ network.py
│  │  ├─ storage_health.py
│  │  └─ system.py
│  │
│  ├─ doctors/
│  │  ├─ events.py
│  │  ├─ full_scan.py
│  │  ├─ gaming.py
│  │  ├─ internet.py
│  │  ├─ slow_pc.py
│  │  ├─ smart.py
│  │  └─ storage.py
│  │
│  └─ ui/
│     ├─ main_window.py
│     ├─ theme.py
│     └─ widgets.py
│
└─ tests/
```

---

## Testing and CI

The repository contains regression tests for areas including:

- Health / coverage behavior
- Unavailable scan handling
- Structured network checks
- Internet vs ICMP behavior
- Event classification
- Event correlation
- Storage scoring
- Physical-disk status interpretation
- Process grouping
- Local log privacy redaction
- Read-only PowerShell safety guard
- Stable release contract

GitHub Actions runs compile checks and regression tests on Windows with supported Python versions.

Run tests locally:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

---

## Privacy Notes for Bug Reports

If you report a bug, useful information includes:

- Windows version
- OpenFix version
- Doctor / scan mode used
- Error message
- Session ID
- Relevant local log lines
- Steps to reproduce

Before sharing logs publicly, review them yourself. OpenFix performs basic redaction, but no automated redaction system can guarantee removal of every piece of personal information.

Never include passwords, security codes, account tokens, or other secrets in a bug report.

---

## Roadmap After v1.0

The first stable release intentionally avoids automatic repairs. Future work may include better diagnostic coverage, report export, and carefully designed optional repair helpers, but only when the safety model is strong enough.

Planned directions may include:

- Improved physical-drive diagnostics
- Better hardware sensor coverage
- Optional local report export
- More diagnostic regression tests
- UI polish and accessibility
- Additional correlation rules with conservative wording

Automatic repair, Registry modification, driver removal, or service modification are **not** part of v1.0.

---

## Open Source

OpenFix AI is open source under the **MIT License**.

Contributions, testing, bug reports, and ideas are welcome.

---

## Author

**Thirdeyegameing**

OpenFix AI is an independent open-source project.

---

## Disclaimer

OpenFix AI is a diagnostic and troubleshooting tool. Its results are informational estimates and do not guarantee hardware condition or system health.

Back up important files before making major system changes or replacing hardware.
