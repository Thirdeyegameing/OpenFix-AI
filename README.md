# OpenFix AI

OpenFix AI is an open-source Windows diagnostic and troubleshooting application designed to help everyday users understand what may be happening inside their PC.

> Scan your PC, identify possible problems, explain the results clearly, and suggest safe next steps.

OpenFix AI follows a **local-first, privacy-focused, read-only diagnostic approach**.

---

## Current Version

**OpenFix AI v0.5.2-dev12 — Reliability Gate**

OpenFix AI is currently in active development.

The current development focus is diagnostic reliability, accuracy, safer error handling, cleaner architecture, automated testing, and a better experience for normal Windows users.

### Current status

- Modular Python project structure
- Read-only diagnostics
- Local Smart Doctor
- No Cloud AI
- No external AI APIs
- Improved diagnostic coverage handling
- Improved Windows Event analysis
- Improved Internet diagnostics
- Improved Storage diagnostics
- Local logging with log rotation
- Regression tests
- GitHub Actions / CI support

---

## Features

### System Diagnostics

- CPU usage monitoring
- CPU model detection
- RAM usage monitoring
- Installed / usable memory information
- Top RAM-consuming applications
- GPU detection
- Multi-GPU detection improvements
- GPU driver version detection
- GPU temperature support when available
- Windows version and build information
- PC uptime
- Active network adapter detection
- Drive and storage information

### System Health Dashboard

The Dashboard provides a quick overview of important PC health information.

Current dashboard areas include:

- CPU
- RAM
- Windows Drive
- Internet
- Graphics
- Windows Events
- System Information
- Top RAM Usage
- Scan Coverage
- Last Scan information
- Estimated System Health score

OpenFix distinguishes between:

- Healthy
- Needs attention
- Important
- Unavailable

Missing diagnostic information is not automatically treated as a PC fault.

---

## Doctor Modes

### Internet Doctor

Checks common network problems including:

- Internet connectivity
- DNS resolution
- Active network adapter
- Default gateway
- Network response time
- Packet loss
- Connection stability

Internet connectivity and ICMP/Ping availability are treated separately to reduce false positives.

A network may still be online even when Ping is blocked by a firewall, VPN, or network policy.

### Gaming Doctor

Checks common conditions that may affect gaming performance:

- CPU usage
- RAM usage
- GPU detection
- GPU temperature when available
- Network latency
- Packet loss
- Connection stability

Gaming Doctor currently does **not** measure in-game FPS or frame time.

### Slow PC Doctor

Checks common reasons a Windows PC may feel slow:

- High CPU usage
- High RAM usage
- RAM-heavy applications
- Low Windows drive space
- Current resource pressure

For better results, run Slow PC Doctor while the PC is actually experiencing slow performance.

### Storage Doctor

Checks:

- Windows system drive
- Local fixed drives
- Available storage space
- Free-space percentage
- Drive size
- Drive classification

Storage scoring uses different logic for system drives and data drives.

Removable, network, and other non-system drives are not treated the same as the Windows system drive.

Current Storage Doctor primarily evaluates storage capacity and available space. It does not yet guarantee the physical health of an SSD or HDD.

### Windows Event Doctor

Analyzes recent Windows Event Log information.

OpenFix currently looks for important categories such as:

- Hardware-related errors
- WHEA events
- Unexpected shutdowns
- Kernel-Power events
- Storage-related errors
- Graphics-related errors
- Application crashes
- Relevant Windows errors

Common background noise is filtered where possible, including:

- DistributedCOM Event ID 10016
- Common CAPI2 background events

OpenFix distinguishes between raw events, ignored background events, and relevant diagnostic events.

Windows Event Logs can contain warnings and errors even when a PC is working normally, so Event Log results should not be treated as proof of hardware failure.

---

## Local Smart Doctor

Local Smart Doctor combines diagnostic information and attempts to identify the most important issue to investigate first.

It can correlate information such as:

- High RAM usage + RAM-heavy application
- Low storage + storage-related Windows events
- GPU errors + high GPU temperature
- Good Ping + high packet loss
- Unexpected shutdowns + hardware or temperature signals
- Current resource pressure

Recommendations are prioritized using levels such as:

- **Do first**
- **Next**
- **Later**

Smart Doctor also provides:

- Primary Issue
- Why this matters
- Top Recommendations
- Possible Problems
- Detailed Scan Information

Smart Doctor uses built-in local diagnostic rules.

**It does not use Cloud AI.**

---

## Full System Scan

Full System Scan combines the main diagnostic areas into one health overview.

Current areas include:

- Internet
- Gaming
- Slow PC
- Storage
- Windows Events

Local Smart Doctor analyzes the collected information but is not counted as an additional independent health area.

This helps prevent the same problem from being counted twice in the overall score.

---

## Scan Coverage

OpenFix separates **Health Score** from **Diagnostic Coverage**.

This is important because missing information does not necessarily mean something is wrong.

Examples:

- GPU detected but temperature sensor unavailable
- Windows Event Log inaccessible
- Ping blocked by a firewall
- Hardware sensor unsupported

These situations can reduce diagnostic coverage without automatically reducing PC health.

If OpenFix does not have enough information to calculate a reliable score, the result can be shown as:

**N/A / UNAVAILABLE**

instead of incorrectly showing 100/100.

---

## Safety & Privacy

OpenFix AI is currently designed as a **read-only diagnostic application**.

OpenFix currently does not:

- Use Cloud AI
- Use OpenAI API
- Use external AI APIs
- Automatically edit the Windows Registry
- Automatically uninstall drivers
- Automatically disable Windows services
- Automatically change system settings
- Automatically repair Windows
- Automatically delete user files

Local diagnostic information is analyzed using built-in rules.

### Network Tests

Internet Doctor may perform normal connectivity tests such as:

- DNS lookup
- Network adapter checks
- Gateway checks
- Connectivity tests
- Ping / latency checks

These are standard network diagnostic operations and are not AI services.

---

## Diagnostic Scores

OpenFix scores are **estimates**.

A low score does not prove that hardware is broken.

A score of 100 also does not guarantee that every component is perfectly healthy.

Important hardware problems should always be confirmed with dedicated hardware diagnostic tools before replacing components or making major system changes.

---

## Project Structure

OpenFix is organized as a modular Python project.

```text
OpenFix-AI/
│
├─ main.py
├─ requirements.txt
├─ README.md
├─ LICENSE
│
├─ openfix/
│  ├─ app.py
│  ├─ config.py
│  ├─ models.py
│  │
│  ├─ core/
│  │  ├─ scanner.py
│  │  ├─ logger.py
│  │  ├─ helpers.py
│  │  └─ powershell.py
│  │
│  ├─ diagnostics/
│  │  ├─ system.py
│  │  ├─ gpu.py
│  │  ├─ network.py
│  │  ├─ events.py
│  │  └─ collector.py
│  │
│  ├─ doctors/
│  │  ├─ internet.py
│  │  ├─ gaming.py
│  │  ├─ slow_pc.py
│  │  ├─ storage.py
│  │  ├─ events.py
│  │  ├─ smart.py
│  │  └─ full_scan.py
│  │
│  └─ ui/
│     ├─ main_window.py
│     ├─ widgets.py
│     └─ theme.py
│
└─ tests/
```

This structure makes OpenFix easier to test, maintain, and expand without keeping the entire application inside one large `main.py` file.

---

## Logging

OpenFix includes local diagnostic logging for development and troubleshooting.

On Windows, logs are stored locally under the OpenFix application data directory.

Logging uses rotation to prevent log files from growing indefinitely.

Logs are intended to help investigate application errors and failed scans.

---

## Testing

OpenFix includes regression tests for important diagnostic behavior.

Areas covered include:

- Network parsing
- Internet connectivity logic
- Diagnostic coverage
- Windows Event classification
- Event filtering
- Storage logic
- Failure conditions
- Smart Doctor behavior

The project also includes GitHub Actions configuration for automated testing.

---

## Requirements

OpenFix AI currently targets Windows.

Recommended environment:

- Windows 10 or Windows 11
- Python 3.10 or newer
- PySide6
- psutil
- Windows PowerShell

Some diagnostic information depends on hardware and driver support.

For example, GPU temperature information may not be available on every graphics device.

---

## Installation

Clone or download the repository.

Open a terminal inside the OpenFix-AI folder.

Install the required Python packages:

```bash
pip install -r requirements.txt
```

Then start OpenFix:

```bash
py main.py
```

or:

```bash
python main.py
```

---

## Development Roadmap

### Completed

- [x] v0.1 — Basic CPU, RAM, disk and internet diagnostics
- [x] v0.2 — GPU, network, drive and process diagnostics
- [x] v0.3 — Doctor Mode
- [x] v0.4 — Windows Event diagnostics
- [x] v0.5 — Local Smart Doctor
- [x] v0.5.2 — Major UI, diagnostic accuracy and architecture development
- [x] v0.5.2-dev11 — Production Foundation
- [x] v0.5.2-dev12 — Reliability Gate

### Planned

#### v0.5.2-dev13 — Accuracy Expansion

Planned areas include:

- Physical disk health information
- Better SSD / HDD diagnostics
- Windows Event timeline
- Event correlation
- Improved Smart Doctor correlation
- Local scan history
- Compare current scan with previous scan
- Improved application/process grouping
- Additional regression tests

#### v0.6 — Diagnostic Report Export

Planned report features:

- Export diagnostic reports
- Save scan summaries
- Easier sharing of diagnostic information
- Human-readable report formatting

#### v0.7 — Safe Repair Tools

Possible future repair features may include:

- Guided repair suggestions
- Safe network repair helpers
- Basic cleanup assistance
- Step-by-step repair actions
- Confirmation before changes
- Strong safety checks

Repair functionality will not be enabled until the safety model is considered reliable enough.

#### v1.0 — First Stable Release

Goals include:

- Stable diagnostic architecture
- Reliable scoring
- Better hardware coverage
- Polished UI
- Strong documentation
- Better automated testing
- Beginner-friendly troubleshooting
- Safe and predictable behavior

---

## Development Principles

### Local First

Diagnostic analysis should happen locally whenever possible.

### Read Only First

OpenFix should understand the PC before attempting to change it.

### Missing Data Is Not Failure

Unsupported sensors or inaccessible information should not automatically reduce the health score.

### Explain Results Clearly

Diagnostic information should be understandable by normal PC users.

### Avoid False Confidence

OpenFix should not claim that hardware is broken without enough evidence.

### Safety Before Automation

Automatic repair features should only be introduced when they can be implemented safely.

---

## Open Source

OpenFix AI is an open-source project.

Contributions, testing, bug reports, and ideas are welcome.

If you discover a bug, please provide as much information as possible, including:

- Windows version
- OpenFix version
- Diagnostic mode used
- Error message
- Relevant log information
- Steps to reproduce the problem

Please avoid including passwords, private personal information, or sensitive account information in bug reports.

---

## License

OpenFix AI is released under the **MIT License**.

See `LICENSE` for details.

---

## Author

**Thirdeyegameing**

OpenFix AI is an independent open-source project currently under active development.

---

## Disclaimer

OpenFix AI is a diagnostic and troubleshooting tool.

Its results are informational estimates and should not be considered a guarantee of hardware condition or system health.

Always back up important files before making major system changes or replacing hardware.
