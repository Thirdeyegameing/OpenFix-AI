from openfix.core.helpers import make_result
from openfix.diagnostics.collector import internet_coverage

def doctor_internet(data):
    network = data["network"]
    score = 100
    facts, issues, actions = [], [], []
    primary = None
    why = None

    if network["ping_tested"]:
        if network["internet"]:
            facts.append("Internet connection is reachable.")
        else:
            score -= 45
            issues.append("OpenFix could not reach the internet.")
            actions.append("Check the router, Wi-Fi connection or Ethernet cable.")
            primary = "Internet connection could not be confirmed."
            why = "Without a working connection, online games, websites and cloud services may not work."
    else:
        facts.append("Internet reachability test could not be performed.")

    if network["dns_tested"]:
        if network["dns_ok"]:
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

    ping = network["ping"]
    if ping is None:
        if network["ping_tested"]:
            facts.append("Response time could not be measured from the ping replies.")
    elif ping < 80:
        facts.append(f"Internet response time looks good: {ping} ms.")
    elif ping < 150:
        score -= 10
        issues.append(f"Network delay is higher than ideal ({ping} ms).")
    else:
        score -= 25
        issues.append(f"Network delay is very high ({ping} ms).")
        actions.append("Check Wi-Fi quality, background downloads and ISP conditions.")
        if primary is None:
            primary = "Internet response time is very high."
            why = "High response delay can cause noticeable lag in online games, calls and remote applications."

    loss = network["packet_loss"]
    if loss is None:
        if network["ping_tested"]:
            facts.append("Packet loss could not be measured from the ping output.")
    elif loss == 0:
        facts.append("No packet loss was detected.")
    elif loss < 3:
        score -= 3
        facts.append(f"Packet loss: {loss}%.")
    elif loss < 10:
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

    adapter = network["adapter"]
    if adapter["available"]:
        facts.append(f"Active adapter: {adapter['name']}.")
        facts.append(f"Adapter speed: {adapter['link_speed']}.")

    return make_result(
        "Internet Doctor",
        score,
        facts,
        issues,
        actions,
        "Ping measures response delay. Packet loss measures network data that did not arrive.",
        coverage=internet_coverage(data),
        primary_issue=primary,
        why_it_matters=why,
        target_doctor="internet" if issues else None,
    )
