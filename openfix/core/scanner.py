from PySide6.QtCore import QThread, Signal

from openfix.core.helpers import make_result
from openfix.core.logger import get_logger, new_session_id
from openfix.diagnostics.collector import collect_system_data
from openfix.diagnostics.events import scan_event_logs, analyze_event_logs
from openfix.doctors.internet import doctor_internet
from openfix.doctors.gaming import doctor_gaming
from openfix.doctors.slow_pc import doctor_slow_pc
from openfix.doctors.storage import doctor_storage
from openfix.doctors.events import create_event_result
from openfix.doctors.smart import doctor_smart
from openfix.doctors.full_scan import doctor_full


class ScanWorker(QThread):
    finished = Signal(dict)

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
            else:
                data = collect_system_data()
                if self.mode == "internet":
                    result = doctor_internet(data)
                elif self.mode == "gaming":
                    result = doctor_gaming(data)
                elif self.mode == "slow":
                    result = doctor_slow_pc(data)
                elif self.mode == "storage":
                    result = doctor_storage(data)
                elif self.mode == "smart":
                    package = scan_event_logs()
                    result = doctor_smart(data, analyze_event_logs(package))
                else:
                    result = doctor_full(data, scan_event_logs())

            result["session_id"] = self.session_id
            logger.info(
                "scan_complete session=%s mode=%s score=%s coverage=%s",
                self.session_id,
                self.mode,
                result.get("score"),
                result.get("coverage"),
            )
            self.finished.emit(result)
        except Exception as error:
            logger.exception("scan_error session=%s mode=%s", self.session_id, self.mode)
            self.finished.emit(
                make_result(
                    "Scan Error",
                    0,
                    [],
                    ["The diagnostic scan did not complete."],
                    ["Run the scan again. If it fails again, check logs/openfix.log for the recorded error."],
                    f"The scan could not finish normally. Internal error: {error}",
                    coverage=0,
                    extra={
                        "session_id": self.session_id,
                        "is_error": True,
                        "error_message": str(error),
                    },
                )
            )
