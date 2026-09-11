from unittest.mock import patch

from openfix.diagnostics import network


def test_structured_ping_result():
    fake = {"ok": True, "stdout": '{"Success":true,"Sent":4,"Received":4,"AverageMs":22,"PacketLoss":0}', "stderr": ""}
    with patch.object(network, "run_powershell", return_value=fake):
        result = network.test_ping()
    assert result["tested"] is True
    assert result["reachable"] is True
    assert result["ping"] == 22
    assert result["packet_loss"] == 0


def test_structured_ping_no_replies_is_still_tested():
    fake = {"ok": True, "stdout": '{"Success":true,"Sent":4,"Received":0,"AverageMs":null,"PacketLoss":100}', "stderr": ""}
    with patch.object(network, "run_powershell", return_value=fake):
        result = network.test_ping()
    assert result["tested"] is True
    assert result["reachable"] is False
    assert result["packet_loss"] == 100
