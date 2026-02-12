"""OS-dispatch for getting the foreground application name."""

from __future__ import annotations

import platform


def get_foreground_app() -> str | None:
    """Return the name of the current foreground app, or None if unknown."""
    system = platform.system()
    if system == "Darwin":
        from ai_cost_observer.platform.macos import get_active_app_macos

        return get_active_app_macos()
    elif system == "Windows":
        from ai_cost_observer.platform.windows import get_active_app_windows

        return get_active_app_windows()
    return None
