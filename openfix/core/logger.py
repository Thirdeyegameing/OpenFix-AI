import logging
import os
import uuid
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from openfix.config import APP_NAME, LOG_BACKUP_COUNT, LOG_MAX_BYTES

_LOGGER = None


def new_session_id() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:8]


def default_log_dir() -> Path:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / "OpenFix" / "logs"
    return Path.home() / ".openfix" / "logs"


def setup_logging(base_dir: Path | None = None) -> logging.Logger:
    global _LOGGER
    if _LOGGER is not None:
        return _LOGGER

    logger = logging.getLogger("openfix")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    try:
        log_dir = Path(base_dir) if base_dir else default_log_dir()
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "openfix.log"
        handler = RotatingFileHandler(
            log_file,
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
    except Exception:
        fallback = Path.cwd() / "logs"
        fallback.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            fallback / "openfix.log",
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
        )

    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(handler)
    logger.info("logging_ready app=%s", APP_NAME)

    _LOGGER = logger
    return logger


def get_logger() -> logging.Logger:
    return setup_logging()
