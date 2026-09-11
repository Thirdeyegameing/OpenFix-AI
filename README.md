# OpenFix AI

OpenFix AI is an open-source Windows diagnostic and troubleshooting tool designed to help everyday users understand possible PC problems in clear language.

**Current development version: v0.5.2-dev12 — Reliability Gate**

OpenFix is local-first and read-only. Smart Doctor uses built-in local diagnostic rules; it does not use Cloud AI, OpenAI API, or external AI APIs.

## Current Features

- Modern system health dashboard
- Full System Scan
- Local Smart Doctor
- Internet Doctor
- Gaming Doctor
- Slow PC Doctor
- Storage Doctor
- Windows Event Doctor
- CPU and RAM usage checks
- GPU information, driver detection, and temperature where supported
- Active network adapter, gateway, DNS, connectivity, ping, and packet-loss checks
- Multi-drive storage checks with adaptive thresholds
- Windows Event Log filtering and classification
- Top RAM application grouping
- Scan coverage and unavailable-data handling
- Primary issue and prioritized recommendations
- Local rotating diagnostic logs

## Reliability Principles

- Missing information is **not** counted as healthy.
- If there is not enough data to calculate a score, OpenFix shows **N/A / UNAVAILABLE** instead of 100/100.
- Internet connectivity and ICMP ping are separate checks.
- A blocked ping does not automatically mean the internet is offline.
- Windows Event Log noise is filtered before important events are prioritized.
- Scores are estimates and are not hardware failure verdicts.

## Safety & Privacy

- No Cloud AI
- No OpenAI API
- No external AI API
- No automatic Registry changes
- No automatic driver removal
- No automatic Windows service changes
- Read-only diagnostics

Internet Doctor performs normal connectivity tests such as DNS, TCP connection checks, and ping. These are standard network diagnostics, not AI services.

## Requirements

- Windows 10 or Windows 11
- Python **3.10+**
- PySide6
- psutil
- PowerShell / Windows CIM access for Windows-specific diagnostics

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Run OpenFix:

```bash
python main.py
```

## Development Tests

Install development requirements:

```bash
python -m pip install -r requirements-dev.txt
```

Run the regression suite:

```bash
pytest -q
```

GitHub Actions also runs the test suite on Windows across Python 3.10–3.13.

## Project Structure

```text
OpenFix-AI/
├─ main.py
├─ openfix/
│  ├─ core/
│  ├─ diagnostics/
│  ├─ doctors/
│  └─ ui/
├─ tests/
├─ .github/workflows/
├─ requirements.txt
├─ requirements-dev.txt
├─ DEVELOPMENT.md
└─ README.md
```

## Roadmap

- [x] v0.1 — Basic CPU, RAM, disk and internet diagnostics
- [x] v0.2 — GPU, network, multiple drives and process diagnostics
- [x] v0.3 — Doctor Mode
- [x] v0.4 — Windows Event diagnostics
- [x] v0.5 — Local Smart Doctor and modern diagnostic dashboard
- [x] v0.5.2-dev12 — Reliability Gate and production diagnostic foundation
- [ ] v0.5.2-dev13 — Accuracy Expansion
- [ ] v0.6 — Diagnostic report export
- [ ] v0.7 — Carefully designed safe repair tools
- [ ] v1.0 — First stable Windows release

## Planned Accuracy Expansion

Future development may include:

- Physical SSD/HDD health information
- Event timeline correlation
- Scan history and comparison
- More detailed hardware availability checks
- Improved diagnostic context without sending data to Cloud AI

## License

OpenFix AI is released under the MIT License. See `LICENSE` in the repository.
