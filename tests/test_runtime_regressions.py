import unittest
from unittest.mock import patch

from openfix.diagnostics.system import find_system_drive
from openfix.diagnostics import network


class RuntimeRegressionTests(unittest.TestCase):
    def test_find_system_drive_does_not_raise_name_error(self):
        drives = [
            {"device": "C:\\", "free": 1, "percent": 50},
            {"device": "D:\\", "free": 1, "percent": 50},
        ]
        with patch.dict("os.environ", {"SystemDrive": "C:"}, clear=False):
            result = find_system_drive(drives)
        self.assertEqual(result["device"], "C:\\")

    def test_active_adapter_json_parser_has_json_available(self):
        fake = {
            "ok": True,
            "stdout": '{"Name":"Wi-Fi","InterfaceDescription":"Test Adapter","LinkSpeed":"1 Gbps","MacAddress":"00-00-00-00-00-00","ifIndex":1}',
            "stderr": "",
        }
        with patch.object(network, "run_powershell", return_value=fake):
            adapter = network.get_active_adapter()
        self.assertTrue(adapter["available"])
        self.assertEqual(adapter["name"], "Wi-Fi")


if __name__ == "__main__":
    unittest.main()
