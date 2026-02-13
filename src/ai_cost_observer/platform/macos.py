"""macOS-specific: get the foreground (active) application name."""

from __future__ import annotations

import subprocess

from loguru import logger


def _get_active_app_appkit() -> str | None:
    """Get active app via NSWorkspace (requires pyobjc-framework-Cocoa)."""
    try:
        from AppKit import NSWorkspace

        active = NSWorkspace.sharedWorkspace().activeApplication()
        if active:
            return active.get("NSApplicationName", None)
    except ImportError:
        return None
    except Exception:
        logger.opt(exception=True).debug("AppKit active app lookup failed")
    return None


def _get_active_app_osascript() -> str | None:
    """Fallback: get active app via osascript."""
    try:
        result = subprocess.run(
            [
                "osascript",
                "-e",
                'tell application "System Events" to get name of first'
                " application process whose frontmost is true",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    except Exception:
        logger.opt(exception=True).debug("osascript active app lookup failed")
    return None


def get_active_app_macos() -> str | None:
    """Get the name of the foreground app on macOS. Tries AppKit first, falls back to osascript."""
    name = _get_active_app_appkit()
    if name:
        return name
    return _get_active_app_osascript()
