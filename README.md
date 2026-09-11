# OpenFix AI

OpenFix AI is an open-source Windows diagnostic and troubleshooting tool designed to help everyday users understand what may be happening inside their PC.

The goal is simple:

> Scan your PC, identify possible problems, explain the results clearly, and suggest safe next steps.

OpenFix AI is designed around a **local-first and privacy-focused approach**.

- No Cloud AI
- No external AI API
- No automatic Registry changes
- No automatic driver removal
- No automatic Windows service changes

Diagnostic analysis is performed locally on the user's PC.

---

## v0.5.2 Development

OpenFix AI v0.5.2 is currently focused on improving diagnostic accuracy, usability and the overall user experience.

### Completed in v0.5.2 development

- Modern sidebar-based interface
- Redesigned system dashboard
- System Health summary
- CPU, RAM, storage, internet, GPU and Windows Event status cards
- Local Smart Doctor improvements
- Smarter issue correlation
- Prioritized recommendations
- Scan Coverage
- Partial Scan detection
- Last Scan time
- Top RAM Usage
- GPU driver information
- Windows build information
- PC uptime
- Expandable System Information section
- Expandable Top RAM Usage section
- Modern Help, Simple Terms and Safety dialogs
- Improved network diagnostics
- Improved Event Log filtering
- Improved multi-GPU handling
- Reduced false-positive warnings
- Improved scoring logic

## Current Version

**OpenFix AI v0.5.2-dev7**

OpenFix AI is currently in active early development.

The application focuses on **local, read-only Windows diagnostics** designed to help normal users understand possible PC problems without requiring advanced technical knowledge.

Current highlights include:

- Modern system health dashboard
- Local Smart Doctor
- Internet diagnostics
- Gaming diagnostics
- Slow PC diagnostics
- Storage diagnostics
- Windows Event Log analysis
- CPU, RAM, GPU and network monitoring
- System information
- Top RAM usage monitoring
- Scan coverage and partial scan detection
- Prioritized recommendations
- Expandable dashboard sections
- Simple explanations for technical terms
- Safety and privacy guidance

OpenFix AI does **not** use Cloud AI or external AI APIs.

Diagnostic analysis is performed locally using built-in rules.

OpenFix AI currently operates in **read-only diagnostic mode** and does not automatically modify Windows settings, drivers, Registry entries or services.

---

## Features

OpenFix AI v0.5.2-dev7 currently includes:

### Core Diagnostics
- CPU usage monitoring
- RAM usage monitoring
- GPU information
- GPU driver version detection
- GPU temperature support on compatible systems
- Storage usage for multiple drives
- Windows drive free space checks
- Active network adapter detection
- Ethernet / Wi-Fi link information
- Default gateway detection
- DNS detection
- Internet connectivity check
- Ping / response time check
- Packet loss check
- Windows Event Log diagnostics

### Doctor Modes
- Internet Doctor
- Gaming Doctor
- Slow PC Doctor
- Storage Doctor
- Windows Event Doctor
- Full System Scan

### Smart Analysis
- Local Smart Doctor analysis
- Measured facts display
- Estimated analysis
- Possible problem detection
- Prioritized recommendations
- Scan coverage summary
- Partial scan awareness
- Last scan tracking

### Dashboard and Monitoring
- System Health dashboard
- CPU status card
- RAM status card
- Internet status card
- Graphics status card
- Windows drive status card
- Windows event status card
- Top RAM usage monitoring
- System information panel
- PC uptime display
- Installed RAM display
- Windows version display
- Network adapter display

### Usability
- Expandable / collapsible dashboard sections
- Quick Guide window
- Simple Terms window
- Safety & Privacy window
- Cleaner modern UI
- Read-only diagnostic mode

### Safety
- No Cloud AI
- No external API integration
- No automatic Registry edits
- No automatic driver removal
- No automatic Windows service changes
- No automatic system changes

---

## Screenshot

OpenFix AI currently uses a simple dashboard designed to make system information easier to understand.

A screenshot will be added here soon.

---

## Planned Features

Future versions are planned to include:

### Gaming Doctor

Diagnose common gaming problems such as:

- FPS drops
- Stuttering
- High GPU usage
- High CPU usage
- High temperatures
- RAM pressure
- Low disk space
- Background applications
- Network latency
- Packet loss

### Internet Doctor

Check common network problems such as:

- Slow connection
- High ping
- Packet loss
- DNS problems
- Gateway connectivity
- Ethernet link speed
- Network adapter problems

### Slow PC Doctor

Analyze possible causes of a slow Windows PC.

### Storage Doctor

Help users understand:

- Low disk space
- Large drives
- Storage usage
- Possible cleanup opportunities

### AI Doctor

A future AI-powered assistant that will explain diagnostic results using real system information collected by OpenFix AI.

The AI will not simply guess.

It will analyze actual diagnostic data collected from the user's computer.

---

## Safety

OpenFix AI is currently designed as a **read-only diagnostic tool**.

Version 0.2 does not:

- Delete files
- Modify the Windows Registry
- Disable Windows services
- Change drivers
- Change network settings
- Modify system configuration automatically

Future repair features will be designed with confirmation prompts and safety controls.

---

## Requirements

OpenFix AI currently requires:

- Windows
- Python 3
- PySide6
- psutil

Install dependencies with:

```bash
pip install PySide6 psutil
```
If the pip command does not work, try:

```bash
py -m pip install PySide6 psutil
```

## Running OpenFix AI
Download or clone this repository.

Then run:

```bash
python main.py
```
or:

```bash
py main.py
```

Then click:

> SCAN MY PC

OpenFix AI will scan your system and display the results.

## Project Roadmap

- [x] v0.1 - Basic CPU, RAM, disk and internet diagnostics
- [x] v0.2 - GPU, network details, multiple drives, process monitoring and issue detection
- [x] v0.3 - Doctor Mode
- [x] v0.4 - Windows Event Log diagnostics
- [x] v0.5 - Local Smart Doctor and diagnostic analysis
- [ ] v0.6 - Diagnostic report export
- [ ] v0.7 - Safe repair tools
- [ ] v1.0 - First stable Windows release

## License
OpenFix AI is licensed under the MIT License.
See the LICENSE file for more information.

## Author

Created by **Thirdeyegameing**

OpenFix AI is currently under active development.
