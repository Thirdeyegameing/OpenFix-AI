import unittest
from openfix.diagnostics.collector import internet_coverage, slow_pc_coverage


class CoverageTests(unittest.TestCase):
    def test_failed_internet_test_is_still_covered(self):
        data = {
            "network": {
                "adapter": {"available": True},
                "ping_tested": True,
                "ping": None,
                "packet_loss": 100,
                "dns_tested": True,
            }
        }
        self.assertGreaterEqual(internet_coverage(data), 80)

    def test_slow_pc_does_not_require_gpu(self):
        data = {
            "cpu": 10,
            "memory": {"available": True},
            "processes": [{"name": "x"}],
            "system_drive": {"device": "C:"},
        }
        self.assertEqual(slow_pc_coverage(data), 100)


if __name__ == "__main__":
    unittest.main()
