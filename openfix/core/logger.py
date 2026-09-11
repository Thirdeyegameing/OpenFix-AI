import logging
from pathlib import Path
from datetime import datetime
import uuid

_LOGGER = None


def new_session_id() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:8]


def setup_logging(base_dir: Path | None = None) -> logging.Logger:
    global _LOGGER
    if _LOGGER is not None:
        return _LOGGER

    root = base_dir or Path.cwd()
    log_dir = root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "openfix.log"

    logger = logging.getLogger("openfix")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        handler = logging.FileHandler(log_file, encoding="utf-8")
        handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        logger.addHandler(handler)

    _LOGGER = logger
    return logger


def get_logger() -> logging.Logger:
    return setup_logging()
