import logging
from pathlib import Path

from openfix.core.logger import PrivacyFormatter


def test_privacy_formatter_redacts_home_path_and_mac():
    formatter = PrivacyFormatter("%(message)s")
    record = logging.LogRecord(
        name="openfix",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=f"path={Path.home()} mac=AA-BB-CC-DD-EE-FF",
        args=(),
        exc_info=None,
    )
    text = formatter.format(record)
    assert str(Path.home()) not in text
    assert "AA-BB-CC-DD-EE-FF" not in text
    assert "%USERPROFILE%" in text
    assert "<MAC_REDACTED>" in text
