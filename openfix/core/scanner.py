from PySide6.QtCore import QThread, Signal

from openfix.core.helpers import make_result
from openfix.core.logger import get_logger, new_session_id
from openfix.diagnostics.collector import (
    collect_gaming_data,
    collect_internet_data,
    collect_slow_pc_data,
    collect_storage_data,
    collect_system_data,
)
from openfix.diagnostics.events import analyze_event_logs, scan_event_logs
from openfix.doctors.events import create_event_result
from openfix.doctors.full_scan import doctor_full
from openfix.doctors.gaming import doctor_gaming
from openfix.doctors.internet import doctor_internet
from openfix.doctors.slow_pc import doctor_slow_pc
from openfix.doctors.smart import doctor_smart
from openfix.doctors.storage import doctor_storage


class ScanWorker(QThread):
    result_ready = Signal(dict)

    def __init__(self, mode):
        super().__init__()
        self.mode = mode
        self.session_id = new_session_id()

    def run(self):
        logger = get_logger()
        logger.info("scan_start session=%s mode=%s", self.session_id, self.mode)
        try:
            if self.mode == "events":
                result = create_event_result(scan_event_logs())
            elif self.mode == "internet":
                result = doctor_internet(collect_internet_data())
            elif self.mode == "gaming":
                result = doctor_gaming(collect_gaming_data())
            elif self.mode == "slow":
                result = doctor_slow_pc(collect_slow_pc_data())
            elif self.mode == "storage":
                result = doctor_storage(collect_storage_data())
            elif self.mode == "smart":
                data = collect_system_data()
                package = scan_event_logs()
                result = doctor_smart(data, analyze_event_logs(package))
            else:
                data = collect_system_data()
                result = doctor_full(data, scan_event_logs())

            result["session_id"] = self.session_id
            logger.info(
                "scan_complete session=%s mode=%s score=%s coverage=%s",
                self.session_id,
                self.mode,
                result.get("score"),
                result.get("coverage"),
            )
            self.result_ready.emit(result)
        except Exception as error:
            logger.exception("scan_error session=%s mode=%s", self.session_id, self.mode)
            self.result_ready.emit(
                make_result(
                    "Scan Error",
                    None,
                    [],
                    ["The diagnostic scan did not complete."],
                    ["Run the scan again. If it fails again, open the OpenFix log for the recorded error."],
                    f"The scan could not finish normally. Internal error: {error}",
                    coverage=0,
                    extra={
                        "session_id": self.session_id,
                        "is_error": True,
                        "error_message": str(error),
                    },
                )
            )
