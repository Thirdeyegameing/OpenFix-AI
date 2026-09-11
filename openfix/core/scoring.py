from openfix import config


def disk_space_state(drive):
    """Return ('critical'|'low'|'good'|'ignored', free_gb, free_percent)."""
    free_gb = float(drive.get("free") or 0) / (1024 ** 3)
    free_percent = 100 - float(drive.get("percent") or 0)

    if not drive.get("scored", True):
        return "ignored", free_gb, free_percent

    if drive.get("is_system"):
        critical = (
            free_gb < config.SYSTEM_DISK_CRITICAL_GB
            or (
                free_percent < config.SYSTEM_DISK_CRITICAL_PERCENT
                and free_gb < config.SYSTEM_DISK_PERCENT_GB_CAP
            )
        )
        low = (
            free_gb < config.SYSTEM_DISK_LOW_GB
            or (
                free_percent < config.SYSTEM_DISK_LOW_PERCENT
                and free_gb < config.SYSTEM_DISK_LOW_PERCENT_GB_CAP
            )
        )
    else:
        critical = (
            free_gb < config.DATA_DISK_CRITICAL_GB
            or (
                free_percent < config.DATA_DISK_CRITICAL_PERCENT
                and free_gb < config.DATA_DISK_PERCENT_GB_CAP
            )
        )
        low = (
            free_gb < config.DATA_DISK_LOW_GB
            or (
                free_percent < config.DATA_DISK_LOW_PERCENT
                and free_gb < config.DATA_DISK_LOW_PERCENT_GB_CAP
            )
        )

    if critical:
        return "critical", free_gb, free_percent
    if low:
        return "low", free_gb, free_percent
    return "good", free_gb, free_percent
