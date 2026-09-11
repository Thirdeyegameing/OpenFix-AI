# OpenFix AI

OpenFix AI is an open-source Windows diagnostic and troubleshooting tool designed to help users understand what is wrong with their PC without needing advanced technical knowledge.

The goal is simple:

> Scan your PC, identify possible problems, and explain them in a way normal users can understand.

---

## Current Version

**OpenFix AI v0.2**

OpenFix AI is currently in early development.

At this stage, the application focuses on **read-only diagnostics** and does not make automatic changes to Windows.

---

## Features

OpenFix AI v0.2 can currently check:

- CPU usage
- RAM usage
- GPU information
- GPU driver version
- GPU temperature and usage on supported NVIDIA systems
- Storage usage for multiple drives
- Active network adapter
- Ethernet / Wi-Fi link speed
- Default gateway
- DNS servers
- Internet connectivity
- Ping
- Packet loss
- Top 5 applications using the most RAM
- Basic PC health score
- Detected issues
- Basic recommendations

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
- [ ] v0.4 - Windows Event Log diagnostics
- [ ] v0.5 - AI Doctor
- [ ] v0.6 - Diagnostic report export
- [ ] v0.7 - Safe repair tools
- [ ] v1.0 - First stable Windows release

## License
OpenFix AI is licensed under the MIT License.
See the LICENSE file for more information.

## Author

Created by **Thirdeyegameing**

OpenFix AI is currently under active development.
