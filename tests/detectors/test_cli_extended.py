"""Extended CLI detector tests — multiple instances, AccessDenied."""

from __future__ import annotations

from unittest.mock import MagicMock, Mock

import psutil
import pytest

from ai_cost_observer.config import AppConfig
from ai_cost_observer.detectors.cli import CLIDetector


def _make_config(cli_tools):
    config = AppConfig()
    config.ai_cli_tools = cli_tools
    return config


def _make_telemetry():
    tm = MagicMock()
    tm.cli_running = MagicMock()
    tm.cli_active_duration = MagicMock()
    tm.cli_estimated_cost = MagicMock()
    return tm


def _fake_process(pid, name, cmdline=None):
    proc = MagicMock()
    proc.info = {"pid": pid, "name": name, "cmdline": cmdline or []}
    return proc


class TestCLIMultipleInstances:
    """Test CLI detector with multiple instances of the same tool."""

    def test_multiple_pids_count_as_one_running(self, mocker):
        """Multiple PIDs of the same CLI tool only emit one +1 running event."""
        tools = [
            {
                "name": "Ollama",
                "process_names": {"macos": ["ollama"], "windows": ["ollama.exe"]},
                "category": "inference",
                "cost_per_hour": 0.50,
            }
        ]
        config = _make_config(tools)
        telemetry = _make_telemetry()
        detector = CLIDetector(config, telemetry)

        # Three ollama processes running simultaneously
        procs = [
            _fake_process(100, "ollama"),
            _fake_process(101, "ollama"),
            _fake_process(102, "ollama"),
        ]
        mocker.patch("psutil.process_iter", return_value=procs)

        detector.scan()

        # Should only call add(1, ...) once, not three times
        telemetry.cli_running.add.assert_called_once_with(
            1, {"cli.name": "Ollama", "cli.category": "inference"}
        )

    def test_multiple_different_tools(self, mocker):
        """Multiple different CLI tools are all detected."""
        tools = [
            {
                "name": "Ollama",
                "process_names": {"macos": ["ollama"], "windows": ["ollama.exe"]},
                "category": "inference",
                "cost_per_hour": 0.50,
            },
            {
                "name": "claude-code",
                "process_names": {"macos": ["claude"], "windows": ["claude.exe"]},
                "category": "code",
                "cost_per_hour": 1.00,
            },
        ]
        config = _make_config(tools)
        telemetry = _make_telemetry()
        detector = CLIDetector(config, telemetry)

        procs = [
            _fake_process(100, "ollama"),
            _fake_process(200, "claude"),
        ]
        mocker.patch("psutil.process_iter", return_value=procs)

        detector.scan()

        assert telemetry.cli_running.add.call_count == 2


class TestCLIAccessDenied:
    """Test CLI detector handling of psutil access errors."""

    def test_access_denied_skips_process(self, mocker):
        """psutil.AccessDenied during process scan skips the process."""
        tools = [
            {
                "name": "Ollama",
                "process_names": {"macos": ["ollama"], "windows": ["ollama.exe"]},
                "category": "inference",
                "cost_per_hour": 0.50,
            }
        ]
        config = _make_config(tools)
        telemetry = _make_telemetry()
        detector = CLIDetector(config, telemetry)

        # First process throws AccessDenied, second is valid
        bad_proc = MagicMock()
        bad_proc.info.__getitem__ = MagicMock(side_effect=psutil.AccessDenied(999))
        good_proc = _fake_process(200, "ollama")

        mocker.patch("psutil.process_iter", return_value=[bad_proc, good_proc])

        detector.scan()  # Should not raise

        # The good process should still be detected
        telemetry.cli_running.add.assert_called_once_with(
            1, {"cli.name": "Ollama", "cli.category": "inference"}
        )

    def test_no_such_process_graceful(self, mocker):
        """psutil.NoSuchProcess during iteration is handled gracefully."""
        tools = [
            {
                "name": "test-tool",
                "process_names": {"macos": ["test-tool"], "windows": ["test-tool.exe"]},
                "category": "code",
                "cost_per_hour": 0.50,
            }
        ]
        config = _make_config(tools)
        telemetry = _make_telemetry()
        detector = CLIDetector(config, telemetry)

        vanishing_proc = MagicMock()
        vanishing_proc.info.__getitem__ = MagicMock(
            side_effect=psutil.NoSuchProcess(888)
        )

        mocker.patch("psutil.process_iter", return_value=[vanishing_proc])

        detector.scan()  # Should not raise

        telemetry.cli_running.add.assert_not_called()
