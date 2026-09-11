import unittest
from openfix.diagnostics.events import analyze_event_logs


class EventClassificationTests(unittest.TestCase):
    def test_dcom_10016_is_noise(self):
        package = {
            "available": True,
            "events": [{
                "provider": "DistributedCOM",
                "id": 10016,
                "level": "Error",
                "message": "permission warning",
            }],
        }
        result = analyze_event_logs(package)
        self.assertEqual(result["ignored_noise"], 1)
        self.assertEqual(result["generic_errors"], 0)

    def test_whea_is_hardware(self):
        package = {
            "available": True,
            "events": [{
                "provider": "Microsoft-Windows-WHEA-Logger",
                "id": 18,
                "level": "Error",
                "message": "A fatal hardware error has occurred.",
            }],
        }
        result = analyze_event_logs(package)
        self.assertEqual(result["hardware_errors"], 1)


if __name__ == "__main__":
    unittest.main()
