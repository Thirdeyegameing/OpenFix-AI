from pathlib import Path

import pytest

from openfix.core.powershell import UnsafePowerShellCommand, validate_read_only_powershell


def test_read_only_get_command_is_allowed():
    validate_read_only_powershell("Get-CimInstance Win32_OperatingSystem | Select-Object Caption")


@pytest.mark.parametrize(
    "command",
    [
        "Set-ItemProperty -Path HKCU:\\Software\\X -Name A -Value 1",
        "Remove-Item C:\\Temp\\x.txt",
        "Disable-NetAdapter -Name Wi-Fi",
        "Restart-Service Spooler",
        "Start-Process powershell -Verb RunAs",
        "Invoke-WebRequest https://example.com",
        "reg.exe add HKCU\\Software\\X /v A /d 1",
        "netsh interface ip reset",
        "shutdown.exe /r /t 0",
    ],
)
def test_mutating_or_remote_powershell_is_blocked(command):
    with pytest.raises(UnsafePowerShellCommand):
        validate_read_only_powershell(command)


def test_runtime_sources_do_not_request_admin_elevation():
    root = Path(__file__).resolve().parents[1] / "openfix"
    source = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in root.rglob("*.py"))
    forbidden = ("ShellExecuteW", "runas", "-Verb RunAs", "IsUserAnAdmin")
    for token in forbidden:
        assert token not in source


def test_runtime_has_no_cloud_ai_sdk_imports():
    root = Path(__file__).resolve().parents[1] / "openfix"
    source = "\n".join(path.read_text(encoding="utf-8", errors="ignore").lower() for path in root.rglob("*.py"))
    for token in ("import openai", "from openai", "import anthropic", "from anthropic", "import google.generativeai"):
        assert token not in source


def test_no_shell_true_in_runtime():
    root = Path(__file__).resolve().parents[1] / "openfix"
    source = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in root.rglob("*.py"))
    assert "shell=True" not in source


def test_run_powershell_rejects_mutation_before_execution(monkeypatch):
    import subprocess
    from openfix.core import powershell

    called = {"value": False}

    def fake_run(*args, **kwargs):
        called["value"] = True
        raise AssertionError("subprocess should not be reached")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = powershell.run_powershell("Remove-Item C:\\Temp\\x.txt")
    assert result["ok"] is False
    assert called["value"] is False
