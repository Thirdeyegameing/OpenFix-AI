from openfix.doctors.internet import doctor_internet


def base_network(**updates):
    value = {
        "adapter": {"available": True, "name": "Wi-Fi", "link_speed": "1 Gbps"},
        "gateway": "192.168.1.1",
        "dns_servers": ["1.1.1.1"],
        "dns_tested": True,
        "dns_ok": True,
        "tcp_tested": True,
        "tcp_ok": True,
        "connectivity_tested": True,
        "online": True,
        "connectivity_status": "online",
        "ping_tested": True,
        "icmp_reachable": True,
        "ping": 25,
        "packet_loss": 0,
        "internet": True,
    }
    value.update(updates)
    return value


def test_icmp_blocked_does_not_mark_internet_offline():
    data = {"network": base_network(icmp_reachable=False, ping=None, packet_loss=100)}
    result = doctor_internet(data)
    assert result["score"] >= 90
    assert not any("could not be confirmed" in issue.lower() for issue in result["issues"])


def test_real_offline_is_an_issue():
    data = {"network": base_network(online=False, tcp_ok=False, dns_ok=False, icmp_reachable=False, ping=None, packet_loss=100)}
    result = doctor_internet(data)
    assert result["score"] < 90
    assert result["issues"]


def test_packet_loss_penalized_only_when_icmp_replies_exist():
    blocked = doctor_internet({"network": base_network(icmp_reachable=False, ping=None, packet_loss=100)})
    lossy = doctor_internet({"network": base_network(icmp_reachable=True, packet_loss=50, ping=30)})
    assert lossy["score"] < blocked["score"]


def test_network_unavailable_has_no_score():
    network = base_network(
        adapter={"available": False, "name": "N/A", "link_speed": "N/A"},
        connectivity_tested=False,
        dns_tested=False,
        ping_tested=False,
        online=None,
        ping=None,
        packet_loss=None,
    )
    result = doctor_internet({"network": network})
    assert result["score"] is None
