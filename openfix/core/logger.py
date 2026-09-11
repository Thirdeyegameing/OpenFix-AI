import logging
import os
import re
import uuid
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from openfix.config import APP_NAME, LOG_BACKUP_COUNT, LOG_MAX_BYTES

_LOGGER = None
_MAC_RE = re.compile(r"(?i)\b(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}\b")


class PrivacyFormatter(logging.Formatter):
    """Redact common local identifiers before writing diagnostic logs."""

    def format(self, record: logging.LogRecord) -> str:
        text = super().format(record)
        try:
            home = str(Path.home())
            if home:
                text = text.replace(home, "%USERPROFILE%")
                text = text.replace(home.replace("\\", "/"), "%USERPROFILE%")
        except Exception:
            pass

        username = os.environ.get("USERNAME") or os.environ.get("USER")
        if username and len(username) >= 3:
            # Only redact path-style username occurrences to avoid replacing
            # unrelated words that happen to match a short username.
            text = re.sub(
                rf"(?i)(?<=\\Users\\){re.escape(username)}(?=\\)",
                "%USERNAME%",
                text,
            )
            text = re.sub(
                rf"(?i)(?<=/Users/){re.escape(username)}(?=/)",
                "%USERNAME%",
                text,
            )

        return _MAC_RE.sub("<MAC_REDACTED>", text)


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
    logger.handlers.clear()

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
        PrivacyFormatter(
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
