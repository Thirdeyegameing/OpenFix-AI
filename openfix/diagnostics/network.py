import json
import re
import socket

from openfix import config
from openfix.core.helpers import safe_int
from openfix.core.powershell import run_powershell


def get_network_snapshot():
    result = run_powershell(
        r"""
        try {
            $routes = Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue |
                Where-Object { $_.NextHop -ne '0.0.0.0' }

            $ranked = foreach ($route in $routes) {
                $iface = Get-NetIPInterface -InterfaceIndex $route.InterfaceIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue
                $ifMetric = if ($iface) { [int]$iface.InterfaceMetric } else { 9999 }
                [PSCustomObject]@{
                    Route = $route
                    EffectiveMetric = ([int]$route.RouteMetric + $ifMetric)
                    InterfaceMetric = $ifMetric
                }
            }

            $best = $ranked | Sort-Object EffectiveMetric | Select-Object -First 1
            if (-not $best) {
                [PSCustomObject]@{ Success=$false } | ConvertTo-Json -Compress
                exit
            }

            $route = $best.Route
            $adapter = Get-NetAdapter -InterfaceIndex $route.InterfaceIndex -ErrorAction SilentlyContinue
            $dnsObj = Get-DnsClientServerAddress -InterfaceIndex $route.InterfaceIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue
            $dns = @()
            if ($dnsObj) { $dns = @($dnsObj.ServerAddresses) }

            [PSCustomObject]@{
                Success = $true
                Name = $adapter.Name
                InterfaceDescription = $adapter.InterfaceDescription
                LinkSpeed = $adapter.LinkSpeed
                InterfaceIndex = $route.InterfaceIndex
                Gateway = $route.NextHop
                RouteMetric = [int]$route.RouteMetric
                InterfaceMetric = [int]$best.InterfaceMetric
                EffectiveMetric = [int]$best.EffectiveMetric
                DnsServers = $dns
            } | ConvertTo-Json -Depth 4 -Compress
        }
        catch {
            [PSCustomObject]@{ Success=$false } | ConvertTo-Json -Compress
        }
        """,
        timeout=12,
    )

    snapshot = {
        "available": False,
        "name": "Not available",
        "description": "Not available",
        "link_speed": "Not available",
        "mac": None,
        "interface_index": None,
        "gateway": "Not available",
        "dns_servers": [],
        "route_metric": None,
        "interface_metric": None,
        "effective_metric": None,
    }

    if not result["stdout"]:
        return snapshot

    try:
        data = json.loads(result["stdout"])
        if data.get("Success") is False:
            return snapshot
        if data.get("Success") is None and not data.get("Name"):
            return snapshot
        dns = data.get("DnsServers") or []
        if isinstance(dns, str):
            dns = [dns]
        snapshot.update(
            {
                "available": True,
                "name": data.get("Name") or "Not available",
                "description": data.get("InterfaceDescription") or "Not available",
                "link_speed": data.get("LinkSpeed") or "Not available",
                "mac": None,
                "interface_index": data.get("InterfaceIndex"),
                "gateway": data.get("Gateway") or "Not available",
                "dns_servers": [str(item) for item in dns if item],
                "route_metric": data.get("RouteMetric"),
                "interface_metric": data.get("InterfaceMetric"),
                "effective_metric": data.get("EffectiveMetric"),
            }
        )
    except Exception:
        pass
    return snapshot


def test_dns():
    try:
        socket.getaddrinfo(config.NETWORK_DNS_TEST_HOST, 443, type=socket.SOCK_STREAM)
        return {"tested": True, "ok": True}
    except socket.gaierror:
        return {"tested": True, "ok": False}
    except Exception:
        return {"tested": False, "ok": None}


def test_tcp_connectivity(timeout=3.0):
    # Plain TCP connectivity check; no HTTP/API data is sent.
    targets = config.NETWORK_TCP_TARGETS
    attempted = False
    for host, port in targets:
        try:
            attempted = True
            with socket.create_connection((host, port), timeout=timeout):
                return {"tested": True, "ok": True, "target": f"{host}:{port}"}
        except OSError:
            continue
        except Exception:
            continue
    return {"tested": attempted, "ok": False if attempted else None, "target": None}


def test_ping():
    target = config.NETWORK_PING_TARGET
    result = run_powershell(
        rf"""
        try {{
            $sent = 4
            $replies = @(Test-Connection -ComputerName '{target}' -Count $sent -ErrorAction SilentlyContinue)
            $times = @()
            foreach ($reply in $replies) {{
                $value = $null
                if ($null -ne $reply.ResponseTime) {{ $value = [double]$reply.ResponseTime }}
                elseif ($null -ne $reply.Latency) {{ $value = [double]$reply.Latency }}
                if ($null -ne $value) {{ $times += $value }}
            }}
            $avg = $null
            if ($times.Count -gt 0) {{ $avg = [math]::Round((($times | Measure-Object -Average).Average)) }}
            $received = $replies.Count
            $loss = [math]::Round((($sent - $received) / $sent) * 100)
            [PSCustomObject]@{{
                Success = $true
                Sent = $sent
                Received = $received
                AverageMs = $avg
                PacketLoss = $loss
            }} | ConvertTo-Json -Compress
        }}
        catch {{
            [PSCustomObject]@{{ Success=$false }} | ConvertTo-Json -Compress
        }}
        """,
        timeout=14,
    )

    output = {
        "tested": False,
        "reachable": None,
        "ping": None,
        "packet_loss": None,
    }
    if not result["stdout"]:
        return output
    try:
        data = json.loads(result["stdout"])
        if not data.get("Success"):
            return output
        received = int(data.get("Received") or 0)
        output.update(
            {
                "tested": True,
                "reachable": received > 0,
                "ping": int(data["AverageMs"]) if data.get("AverageMs") is not None else None,
                "packet_loss": int(data["PacketLoss"]) if data.get("PacketLoss") is not None else None,
            }
        )
    except Exception:
        pass
    return output


def scan_network():
    snapshot = get_network_snapshot()
    dns = test_dns()
    tcp = test_tcp_connectivity()
    ping = test_ping()

    connectivity_tested = bool(tcp["tested"] or dns["tested"])
    if tcp.get("ok") is True or dns.get("ok") is True:
        online = True
        connectivity_status = "online"
    elif tcp.get("ok") is False and dns.get("ok") is False:
        online = False
        connectivity_status = "offline"
    else:
        online = None
        connectivity_status = "unknown"

    return {
        "adapter": {
            "available": snapshot["available"],
            "name": snapshot["name"],
            "description": snapshot["description"],
            "link_speed": snapshot["link_speed"],
            "mac": None,
            "interface_index": snapshot["interface_index"],
            "effective_metric": snapshot["effective_metric"],
        },
        "gateway": snapshot["gateway"],
        "dns_servers": snapshot["dns_servers"],
        "dns_tested": dns["tested"],
        "dns_ok": dns["ok"],
        "tcp_tested": tcp["tested"],
        "tcp_ok": tcp["ok"],
        "connectivity_tested": connectivity_tested,
        "online": online,
        "connectivity_status": connectivity_status,
        "ping_tested": ping["tested"],
        "icmp_reachable": ping["reachable"],
        "ping": ping["ping"],
        "packet_loss": ping["packet_loss"],
        # Backward-compatible alias for code/tests that still reference internet.
        "internet": online,
    }


# Compatibility helpers kept for tests and callers from earlier development builds.
def get_active_adapter():
    snapshot = get_network_snapshot()
    return {
        "available": snapshot["available"],
        "name": snapshot["name"],
        "description": snapshot["description"],
        "link_speed": snapshot["link_speed"],
        "mac": None,
        "interface_index": snapshot["interface_index"],
        "effective_metric": snapshot["effective_metric"],
    }


def get_default_gateway():
    return get_network_snapshot()["gateway"]


def get_dns_servers():
    return get_network_snapshot()["dns_servers"]


def parse_ping_output(output):
    """Legacy localized ping parser retained as a fallback/test utility.

    v1.0 uses structured PowerShell ping data for normal scans, so UI accuracy
    no longer depends on the Windows display language.
    """
    parsed = {"ping": None, "packet_loss": None}
    times = re.findall(r"(?:time|เวลา)\s*[=<]\s*(\d+)\s*ms", output, flags=re.IGNORECASE)
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
    return parsed
