"""Tests for active_window OS-dispatch logic."""

from unittest.mock import patch


class TestGetForegroundApp:
    """Test get_foreground_app dispatches correctly per platform."""

    @patch("platform.system", return_value="Linux")
    def test_unknown_os_returns_none(self, _mock_sys):
        from ai_cost_observer.detectors.active_window import get_foreground_app

        assert get_foreground_app() is None

    @patch("platform.system", return_value="Darwin")
    def test_darwin_calls_macos(self, _mock_sys):
        with patch(
            "ai_cost_observer.platform.macos.get_active_app_macos",
            return_value="Safari",
            create=True,
        ):
            from importlib import reload

            import ai_cost_observer.detectors.active_window as aw

            reload(aw)
            result = aw.get_foreground_app()
            assert result == "Safari"

    @patch("platform.system", return_value="Windows")
    def test_windows_calls_win32(self, _mock_sys):
        with patch(
            "ai_cost_observer.platform.windows.get_active_app_windows",
            return_value="notepad.exe",
            create=True,
        ):
            from importlib import reload

            import ai_cost_observer.detectors.active_window as aw

            reload(aw)
            result = aw.get_foreground_app()
            assert result == "notepad.exe"
