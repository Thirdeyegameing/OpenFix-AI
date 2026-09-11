import os
import re
import subprocess
from typing import Iterable


class UnsafePowerShellCommand(ValueError):
    """Raised when an internal diagnostic script contains a mutating command."""


# OpenFix v1.0 intentionally keeps all PowerShell diagnostics read-only.
# The guard is a defense-in-depth measure so future code cannot accidentally
# add common mutating cmdlets without failing loudly during tests/runtime.
_FORBIDDEN_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE | re.MULTILINE)
    for pattern in (
        r"\bSet-[A-Za-z0-9_-]+\b",
        r"\bRemove-[A-Za-z0-9_-]+\b",
        r"\bNew-[A-Za-z0-9_-]+\b",
        r"\bClear-[A-Za-z0-9_-]+\b",
        r"\bDisable-[A-Za-z0-9_-]+\b",
        r"\bEnable-[A-Za-z0-9_-]+\b",
        r"\bStop-[A-Za-z0-9_-]+\b",
        r"\bRestart-[A-Za-z0-9_-]+\b",
        r"\bRepair-[A-Za-z0-9_-]+\b",
        r"\bFormat-[A-Za-z0-9_-]+\b",
        r"\bInitialize-[A-Za-z0-9_-]+\b",
        r"\bUpdate-[A-Za-z0-9_-]+\b",
        r"\bInstall-[A-Za-z0-9_-]+\b",
        r"\bUninstall-[A-Za-z0-9_-]+\b",
        r"\bRename-[A-Za-z0-9_-]+\b",
        r"\bMove-[A-Za-z0-9_-]+\b",
        r"\bCopy-[A-Za-z0-9_-]+\b",
        r"\bAdd-Content\b",
        r"\bSet-Content\b",
        r"\bOut-File\b",
        r"\bExport-[A-Za-z0-9_-]+\b",
        r"\bInvoke-WebRequest\b",
        r"\bInvoke-RestMethod\b",
        r"\bStart-BitsTransfer\b",
        r"\bStart-Process\b",
        r"\breg(?:\.exe)?\s+(?:add|delete|import|restore|load|unload)\b",
        r"\bsc(?:\.exe)?\s+(?:config|create|delete|start|stop|failure)\b",
        r"\bnetsh\b[^\r\n]*(?:\bset\b|\breset\b|\bdelete\b|\badd\b)",
        r"\bshutdown(?:\.exe)?\b",
        r"\bbcdedit(?:\.exe)?\b",
        r"\bdiskpart(?:\.exe)?\b",
    )
)


def validate_read_only_powershell(command: str) -> None:
    if not isinstance(command, str) or not command.strip():
        raise ValueError("PowerShell command must be a non-empty string.")

    for pattern in _FORBIDDEN_PATTERNS:
        if pattern.search(command):
            raise UnsafePowerShellCommand(
                "OpenFix blocked an internal PowerShell command because it appears to modify the system."
            )


def read_only_patterns() -> Iterable[re.Pattern[str]]:
    """Exposed for regression tests; not intended as a public API."""
    return _FORBIDDEN_PATTERNS


def run_powershell(command: str, timeout: int | float = 15):
    try:
        validate_read_only_powershell(command)
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        result = subprocess.run(
            [
                "powershell",
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                command,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            creationflags=creationflags,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
            shell=False,
        )
        return {
            "ok": result.returncode == 0,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }
    except Exception as error:
        return {"ok": False, "stdout": "", "stderr": str(error)}
