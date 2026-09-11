from openfix.core.logger import default_log_dir


def test_default_log_dir_has_logs_leaf():
    value = default_log_dir()
    assert value.name == "logs"
    assert any(part.lower() in {"openfix", ".openfix"} for part in value.parts)
