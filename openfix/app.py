import sys
from PySide6.QtWidgets import QApplication

from openfix.config import APP_NAME, APP_VERSION
from openfix.core.logger import setup_logging
from openfix.ui.main_window import OpenFixWindow


def run_app() -> int:
    logger = setup_logging()
    logger.info("app_start name=%s version=%s", APP_NAME, APP_VERSION)
    app = QApplication(sys.argv)
    window = OpenFixWindow()
    window.show()
    exit_code = app.exec()
    logger.info("app_exit code=%s", exit_code)
    return exit_code
