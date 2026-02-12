"""Windows-specific: get the foreground (active) application name."""

from __future__ import annotations

from loguru import logger


def get_active_app_windows() -> str | None:
    """Get the name of the foreground app on Windows via win32gui + psutil."""
    try:
        import psutil
        import win32gui
        import win32process

        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return None
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        if pid <= 0:
            return None
        proc = psutil.Process(pid)
        return proc.name()
    except ImportError:
        logger.debug("pywin32 not available — Windows active window detection disabled")
        return None
    except Exception:
        logger.opt(exception=True).debug("Windows active app lookup failed")
        return None
