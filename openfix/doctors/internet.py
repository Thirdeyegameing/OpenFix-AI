from openfix import config
from openfix.core.helpers import make_result
from openfix.diagnostics.collector import internet_coverage


def doctor_internet(data):
    network = data["network"]
    coverage = internet_coverage(data)
    if coverage <= 0:
        return make_result(
            "Internet Doctor",
            None,
            ["Network diagnostic information could not be collected."],
            [],
            ["Run the scan again. If it repeats, check OpenFix logs."],
            "No health score was produced because the network checks were unavailable.",
            coverage=0,
        )

    score = 100
    facts, issues, actions = [], [], []
    primary = None
    why = None

    online = network.get("online")
    if network.get("connectivity_tested"):
        if online is True:
            facts.append("External internet connectivity is working.")
        elif online is False:
            score -= 35
            issues.append("External internet connectivity could not be confirmed.")
            actions.append("Check the router, Wi-Fi connection or Ethernet cable.")
            primary = "Internet connectivity could not be confirmed."
            why = "Websites, online games and updates may not work until the connection is restored."
        else:
            facts.append("Internet connectivity result is inconclusive.")
    else:
        facts.append("Internet connectivity test could not be performed.")

    if network.get("dns_tested"):
        if network.get("dns_ok"):
            facts.append("Website name lookup (DNS) is working.")
        else:
            score -= 20
            issues.append("Website name lookup may not be working correctly.")
            actions.append("Check DNS settings before resetting the whole network.")
            if primary is None:
                primary = "DNS may not be working correctly."
                why = "DNS problems can make websites fail to open even when the connection itself is active."
    else:
        facts.append("DNS test could not be performed.")

    ping = network.get("ping")
    loss = network.get("packet_loss")
    icmp = network.get("icmp_reachable")

    if network.get("ping_tested"):
        if icmp is False and online is True:
            facts.append("ICMP ping did not receive replies, but internet connectivity is working.")
            facts.append("This can happen when a firewall, VPN or network blocks ping traffic.")
        elif ping is None:
            facts.append("Ping response time could not be measured.")
        elif ping < config.PING_GOOD_MS:
            facts.append(f"Internet response time looks good: {ping} ms.")
        elif ping < config.PING_HIGH_MS:
            score -= 10
            issues.append(f"Network delay is higher than ideal ({ping} ms).")
        else:
            score -= 25
            issues.append(f"Network delay is very high ({ping} ms).")
            actions.append("Check Wi-Fi quality, background downloads and ISP conditions.")
            if primary is None:
                primary = "Internet response time is very high."
                why = "High response delay can cause noticeable lag in online games, calls and remote applications."

        # Packet loss is only meaningful when ICMP is actually returning replies.
        if icmp is True and loss is not None:
            if loss == 0:
                facts.append("No packet loss was detected.")
            elif loss < config.PACKET_LOSS_WARN:
                score -= 3
                facts.append(f"Packet loss: {loss}%.")
            elif loss < config.PACKET_LOSS_HEAVY:
                score -= 15
                issues.append(f"Some network data is being lost ({loss}%).")
                actions.append("Check Wi-Fi signal, cable quality and router stability.")
                primary = "The network connection is losing data packets."
                why = "Packet loss can cause game lag, voice cut-outs and unstable connections even when ping looks normal."
            else:
                score -= 30
                issues.append(f"Heavy packet loss was detected ({loss}%).")
                actions.append("Check the local network connection before changing Windows settings.")
                primary = "Heavy packet loss was detected."
                why = "Heavy packet loss usually affects connection stability more than raw download speed."
    else:
        facts.append("ICMP ping test could not be performed.")

    adapter = network.get("adapter", {})
    if adapter.get("available"):
        facts.append(f"Active adapter: {adapter.get('name', 'Unknown')}.")
        facts.append(f"Adapter speed: {adapter.get('link_speed', 'Not available')}.")
    if network.get("gateway") not in (None, "", "Not available"):
        facts.append(f"Default gateway: {network['gateway']}.")

    return make_result(
        "Internet Doctor",
        score,
        facts,
        issues,
        actions,
        "Connectivity and ICMP ping are separate checks. A blocked ping does not automatically mean the internet is offline.",
        coverage=coverage,
        primary_issue=primary,
        why_it_matters=why,
        target_doctor="internet" if issues else None,
    )
