import unittest
from openfix.diagnostics.network import parse_ping_output


class PingParserTests(unittest.TestCase):
    def test_english_ping(self):
        output = """
Reply from 1.1.1.1: bytes=32 time=21ms TTL=57
Reply from 1.1.1.1: bytes=32 time=19ms TTL=57
Packets: Sent = 2, Received = 2, Lost = 0 (0% loss),
"""
        result = parse_ping_output(output)
        self.assertEqual(result["ping"], 20)
        self.assertEqual(result["packet_loss"], 0)

    def test_high_loss(self):
        output = "Packets: Sent = 4, Received = 2, Lost = 2 (50% loss)"
        result = parse_ping_output(output)
        self.assertEqual(result["packet_loss"], 50)


if __name__ == "__main__":
    unittest.main()
