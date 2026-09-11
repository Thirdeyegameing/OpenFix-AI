import json
import os
import re
import subprocess

from openfix.core.helpers import safe_int, safe_float
from openfix.core.powershell import run_powershell

def gpu_preference_score(item):
    name = str(item.get("name", "")).lower()
    score = 0
    dedicated_terms = (
        "geforce",
        "rtx",
        "gtx",
        "radeon rx",
        "intel arc",
        "quadro",
    )
    integrated_terms = (
        "radeon(tm) graphics",
        "intel(r) uhd",
        "intel uhd",
        "iris xe",
        "vega graphics",
    )

    if any(term in name for term in dedicated_terms):
        score += 100
    if any(term in name for term in integrated_terms):
        score -= 20

    vram = item.get("vram")
    if vram:
        score += min(int(vram / (1024 ** 3)) * 5, 40)

    if item.get("temperature") is not None:
        score += 5
    if item.get("usage") is not None:
        score += 3
    return score

def _normalize_gpu_name(name):
    return re.sub(r"[^a-z0-9]+", " ", str(name).lower()).strip()

def scan_gpu():
    controllers = []

    result = run_powershell(
        r"""
        Get-CimInstance Win32_VideoController |
        Select-Object Name, AdapterRAM, DriverVersion |
        ConvertTo-Json -Compress
        """,
        timeout=10,
    )

    if result["ok"] and result["stdout"]:
        try:
            data = json.loads(result["stdout"])
            if isinstance(data, dict):
                data = [data]
            for item in data:
                name = item.get("Name") or "Unknown GPU"
                if "microsoft basic" in name.lower():
                    continue
                controllers.append(
                    {
                        "name": name,
                        "vram": safe_int(item.get("AdapterRAM"), 0) or None,
                        "driver": item.get("DriverVersion") or "Unknown",
                        "usage": None,
                        "temperature": None,
                        "source": "Windows",
                    }
                )
        except Exception:
            controllers = []

    # Merge NVIDIA enhanced metrics without replacing the Windows GPU list.
    try:
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,utilization.gpu,temperature.gpu,driver_version",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            creationflags=creationflags,
            timeout=5,
        )

        if result.returncode == 0 and result.stdout.strip():
            for line in result.stdout.splitlines():
                parts = [part.strip() for part in line.split(",")]
                if len(parts) < 5:
                    continue
                nvidia = {
                    "name": parts[0],
                    "vram": safe_float(parts[1], 0) * 1024 * 1024,
                    "usage": safe_float(parts[2]),
                    "temperature": safe_float(parts[3]),
                    "driver": parts[4],
                    "source": "NVIDIA",
                }

                normalized = _normalize_gpu_name(nvidia["name"])
                match = None
                for item in controllers:
                    other = _normalize_gpu_name(item["name"])
                    if normalized in other or other in normalized:
                        match = item
                        break

                if match:
                    match.update(
                        {
                            "vram": nvidia["vram"] or match.get("vram"),
                            "usage": nvidia["usage"],
                            "temperature": nvidia["temperature"],
                            "driver": nvidia["driver"],
                            "source": "NVIDIA + Windows",
                        }
                    )
                else:
                    controllers.append(nvidia)
    except Exception:
        pass

    if not controllers:
        return {
            "available": False,
            "name": "Not available",
            "vram": None,
            "usage": None,
            "temperature": None,
            "driver": None,
            "gpu_count": 0,
            "all_gpus": [],
            "source": None,
        }

    # Remove duplicate names after merging.
    unique = []
    seen = set()
    for item in controllers:
        key = _normalize_gpu_name(item["name"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)

    preferred = max(unique, key=gpu_preference_score)
    return {
        "available": True,
        "name": preferred["name"],
        "vram": preferred.get("vram"),
        "usage": preferred.get("usage"),
        "temperature": preferred.get("temperature"),
        "driver": preferred.get("driver"),
        "gpu_count": len(unique),
        "all_gpus": [item["name"] for item in unique],
        "source": preferred.get("source"),
    }

