import os
import json
import re
import socket
import subprocess

from openfix.core.helpers import safe_int
from openfix.core.powershell import run_powershell

def get_active_adapter():
    result = run_powershell(
        r"""
        $route =
        Get-NetRoute -DestinationPrefix "0.0.0.0/0" -ErrorAction SilentlyContinue |
        Where-Object {$_.NextHop -ne "0.0.0.0"} |
        Sort-Object RouteMetric |
        Select-Object -First 1

        if ($route) {
            Get-NetAdapter -InterfaceIndex $route.InterfaceIndex -ErrorAction SilentlyContinue |
            Select-Object Name, InterfaceDescription, LinkSpeed, MacAddress, ifIndex |
            ConvertTo-Json -Compress
        }
        """,
        timeout=10,
    )

    adapter = {
        "available": False,
        "name": "Not available",
        "description": "Not available",
        "link_speed": "Not available",
        "mac": "Not available",
        "interface_index": None,
    }

    if result["ok"] and result["stdout"]:
        try:
            data = json.loads(result["stdout"])
            adapter.update(
                {
                    "available": True,
                    "name": data.get("Name") or "Not available",
                    "description": data.get("InterfaceDescription") or "Not available",
                    "link_speed": data.get("LinkSpeed") or "Not available",
                    "mac": data.get("MacAddress") or "Not available",
                    "interface_index": data.get("ifIndex"),
                }
            )
        except Exception:
            pass
    return adapter

def get_default_gateway():
    result = run_powershell(
        r"""
        Get-NetRoute -DestinationPrefix "0.0.0.0/0" -ErrorAction SilentlyContinue |
        Where-Object {$_.NextHop -ne "0.0.0.0"} |
        Sort-Object RouteMetric |
        Select-Object -First 1 -ExpandProperty NextHop
        """,
        timeout=10,
    )
    if result["ok"] and result["stdout"]:
        return result["stdout"]
    return "Not available"

def get_dns_servers():
    result = run_powershell(
        r"""
        Get-DnsClientServerAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object {$_.ServerAddresses.Count -gt 0} |
        Select-Object -ExpandProperty ServerAddresses |
        Select-Object -Unique
        """,
        timeout=10,
    )
    if not result["ok"]:
        return []
    return [line.strip() for line in result["stdout"].splitlines() if line.strip()]

def test_dns():
    try:
        socket.gethostbyname("cloudflare.com")
        return {"tested": True, "ok": True}
    except socket.gaierror:
        return {"tested": True, "ok": False}
    except Exception:
        return {"tested": False, "ok": None}

def parse_ping_output(output):
    parsed = {"ping": None, "packet_loss": None}

    times = re.findall(
        r"(?:time|เวลา)\s*[=<]\s*(\d+)\s*ms",
        output,
        flags=re.IGNORECASE,
    )
    values = [safe_int(item) for item in times]
    if values:
        parsed["ping"] = round(sum(values) / len(values))
    elif re.search(r"(?:time|เวลา)\s*<\s*1\s*ms", output, flags=re.IGNORECASE):
        parsed["ping"] = 1

    patterns = [
        r"(\d{1,3})%\s*loss",
        r"lost\s*=\s*\d+\s*\((\d{1,3})%",
        r"สูญหาย\s*=\s*\d+\s*\((\d{1,3})%",
    ]

    for pattern in patterns:
        match = re.search(pattern, output, flags=re.IGNORECASE)
        if match:
            value = safe_int(match.group(1))
            if 0 <= value <= 100:
                parsed["packet_loss"] = value
                break

    if parsed["packet_loss"] is None:
        percentages = [safe_int(item) for item in re.findall(r"(\d{1,3})\s*%", output)]
        percentages = [value for value in percentages if 0 <= value <= 100]
        if percentages:
            parsed["packet_loss"] = percentages[-1]

    return parsed

def test_ping():
    output = {
        "tested": False,
        "internet": None,
        "ping": None,
        "packet_loss": None,
    }

    try:
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        process = subprocess.run(
            ["ping", "-n", "4", "-w", "2000", "1.1.1.1"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            creationflags=creationflags,
            timeout=12,
        )
        output["tested"] = True
        parsed = parse_ping_output(process.stdout)
        output["internet"] = process.returncode == 0
        output["ping"] = parsed["ping"]
        output["packet_loss"] = parsed["packet_loss"]
    except Exception:
        pass

    return output

def scan_network():
    ping = test_ping()
    dns = test_dns()
    return {
        "adapter": get_active_adapter(),
        "gateway": get_default_gateway(),
        "dns_servers": get_dns_servers(),
        "dns_tested": dns["tested"],
        "dns_ok": dns["ok"],
        "ping_tested": ping["tested"],
        "internet": ping["internet"],
        "ping": ping["ping"],
        "packet_loss": ping["packet_loss"],
    }

