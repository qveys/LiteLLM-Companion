"""Extended desktop detector tests — foreground, cmdline fallback, AccessDenied."""

from __future__ import annotations

from unittest.mock import MagicMock, Mock, patch

import psutil
import pytest

from ai_cost_observer.config import AppConfig
from ai_cost_observer.detectors.desktop import DesktopDetector


def _make_config(apps):
    config = AppConfig()
    config.ai_apps = apps
    return config


def _make_telemetry():
    tm = MagicMock()
    tm.app_running = MagicMock()
    tm.app_active_duration = MagicMock()
    tm.app_estimated_cost = MagicMock()
    tm.app_cpu_usage = MagicMock()
    tm.app_memory_usage = MagicMock()
    return tm


def _fake_process(pid, name, cmdline=None, cpu=5.0, mem_mb=100):
    proc = MagicMock()
    proc.info = {"pid": pid, "name": name, "cmdline": cmdline or []}
    proc.cpu_percent.return_value = cpu
    proc.memory_info.return_value = Mock(rss=int(mem_mb * 1024 * 1024))
    return proc


class TestDesktopForegroundDetection:
    """Test foreground app detection and active duration tracking."""

    def test_foreground_app_tracks_duration(self, mocker):
        """When an AI app is in the foreground, active duration is tracked."""
        apps = [
            {
                "name": "ChatGPT",
                "process_names": {"macos": ["ChatGPT"], "windows": ["ChatGPT.exe"]},
                "category": "chat",
                "cost_per_hour": 0.50,
            }
        ]
        config = _make_config(apps)
        telemetry = _make_telemetry()
        detector = DesktopDetector(config, telemetry)

        procs = [_fake_process(100, "ChatGPT")]
        mocker.patch("psutil.process_iter", return_value=procs)
        mocker.patch(
            "ai_cost_observer.detectors.desktop.get_foreground_app",
            return_value="ChatGPT",
        )

        # First scan: detects app, sets initial state
        detector.scan()
        telemetry.app_running.add.assert_called_once_with(
            1, {"app.name": "ChatGPT", "app.category": "chat"}
        )
        # No duration yet (first scan, last_scan_time was 0)
        telemetry.app_active_duration.add.assert_not_called()

        # Second scan: now duration should be tracked
        telemetry.app_running.add.reset_mock()
        detector.scan()
        # Running state doesn't change so no add call for running
        telemetry.app_running.add.assert_not_called()
        # But active duration should be tracked
        telemetry.app_active_duration.add.assert_called_once()

    def test_non_foreground_app_no_duration(self, mocker):
        """When an AI app is running but not in foreground, no duration is tracked."""
        apps = [
            {
                "name": "ChatGPT",
                "process_names": {"macos": ["ChatGPT"], "windows": ["ChatGPT.exe"]},
                "category": "chat",
                "cost_per_hour": 0.50,
            }
        ]
        config = _make_config(apps)
        telemetry = _make_telemetry()
        detector = DesktopDetector(config, telemetry)

        procs = [_fake_process(100, "ChatGPT")]
        mocker.patch("psutil.process_iter", return_value=procs)
        mocker.patch(
            "ai_cost_observer.detectors.desktop.get_foreground_app",
            return_value="SomeOtherApp",
        )

        detector.scan()
        detector.scan()

        telemetry.app_active_duration.add.assert_not_called()


class TestDesktopCmdlineFallback:
    """Test cmdline_patterns fallback for process matching."""

    def test_cmdline_fallback_detects_interpreted_app(self, mocker):
        """Apps running as interpreted scripts (e.g. electron) match via cmdline."""
        apps = [
            {
                "name": "Cursor",
                "process_names": {"macos": ["Cursor"], "windows": ["Cursor.exe"]},
                "cmdline_patterns": ["cursor"],
                "category": "code",
                "cost_per_hour": 1.0,
            }
        ]
        config = _make_config(apps)
        telemetry = _make_telemetry()
        detector = DesktopDetector(config, telemetry)

        # The process name is "Electron" but cmdline contains "cursor"
        procs = [_fake_process(200, "Electron", ["/usr/bin/electron", "--app=/opt/cursor"])]
        mocker.patch("psutil.process_iter", return_value=procs)
        mocker.patch(
            "ai_cost_observer.detectors.desktop.get_foreground_app",
            return_value=None,
        )

        detector.scan()

        telemetry.app_running.add.assert_called_once_with(
            1, {"app.name": "Cursor", "app.category": "code"}
        )


class TestDesktopAccessDenied:
    """Test handling of psutil access errors."""

    def test_access_denied_no_crash(self, mocker):
        """psutil.AccessDenied during process scanning does not crash."""
        apps = [
            {
                "name": "TestApp",
                "process_names": {"macos": ["TestApp"], "windows": ["TestApp.exe"]},
                "category": "chat",
                "cost_per_hour": 0.50,
            }
        ]
        config = _make_config(apps)
        telemetry = _make_telemetry()
        detector = DesktopDetector(config, telemetry)

        # Create a process that raises AccessDenied
        bad_proc = MagicMock()
        bad_proc.info = {"pid": 300, "name": "TestApp", "cmdline": []}
        bad_proc.cpu_percent.side_effect = psutil.AccessDenied(300)
        bad_proc.memory_info.side_effect = psutil.AccessDenied(300)

        mocker.patch("psutil.process_iter", return_value=[bad_proc])
        mocker.patch(
            "ai_cost_observer.detectors.desktop.get_foreground_app",
            return_value=None,
        )

        detector.scan()  # Should not raise

        # App was still detected as running
        telemetry.app_running.add.assert_called_once_with(
            1, {"app.name": "TestApp", "app.category": "chat"}
        )

    def test_no_such_process_during_scan(self, mocker):
        """psutil.NoSuchProcess during iteration is handled gracefully."""
        apps = [
            {
                "name": "TestApp",
                "process_names": {"macos": ["TestApp"], "windows": ["TestApp.exe"]},
                "category": "chat",
                "cost_per_hour": 0.50,
            }
        ]
        config = _make_config(apps)
        telemetry = _make_telemetry()
        detector = DesktopDetector(config, telemetry)

        # Process that disappears mid-scan
        disappearing_proc = MagicMock()
        disappearing_proc.info.__getitem__ = MagicMock(
            side_effect=psutil.NoSuchProcess(999)
        )

        mocker.patch("psutil.process_iter", return_value=[disappearing_proc])
        mocker.patch(
            "ai_cost_observer.detectors.desktop.get_foreground_app",
            return_value=None,
        )

        detector.scan()  # Should not raise

    def test_zombie_process_handled(self, mocker):
        """psutil.ZombieProcess is handled gracefully."""
        apps = [
            {
                "name": "TestApp",
                "process_names": {"macos": ["TestApp"], "windows": ["TestApp.exe"]},
                "category": "chat",
                "cost_per_hour": 0.50,
            }
        ]
        config = _make_config(apps)
        telemetry = _make_telemetry()
        detector = DesktopDetector(config, telemetry)

        zombie_proc = MagicMock()
        zombie_proc.info.__getitem__ = MagicMock(
            side_effect=psutil.ZombieProcess(888)
        )

        mocker.patch("psutil.process_iter", return_value=[zombie_proc])
        mocker.patch(
            "ai_cost_observer.detectors.desktop.get_foreground_app",
            return_value=None,
        )

        detector.scan()  # Should not raise
