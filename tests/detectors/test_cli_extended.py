"""Extended CLI detector tests — multiple instances, AccessDenied."""

from __future__ import annotations

from unittest.mock import MagicMock

import psutil

from ai_cost_observer.config import AppConfig
from ai_cost_observer.detectors.cli import CLIDetector


def _make_config(cli_tools):
    config = AppConfig()
    config.ai_cli_tools = cli_tools
    return config


def _make_telemetry():
    tm = MagicMock()
    tm.cli_running = MagicMock()
    tm.set_running_cli = MagicMock()
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
        """Multiple PIDs of the same CLI tool appear once in the snapshot."""
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

        # Bug H1: snapshot should contain Ollama exactly once
        snapshot = telemetry.set_running_cli.call_args[0][0]
        assert "Ollama" in snapshot
        assert len(snapshot) == 1

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

        # Bug H1: snapshot should contain both tools
        snapshot = telemetry.set_running_cli.call_args[0][0]
        assert len(snapshot) == 2
        assert "Ollama" in snapshot
        assert "claude-code" in snapshot


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

        # The good process should still be detected (Bug H1: check snapshot)
        snapshot = telemetry.set_running_cli.call_args[0][0]
        assert "Ollama" in snapshot

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
        vanishing_proc.info.__getitem__ = MagicMock(side_effect=psutil.NoSuchProcess(888))

        mocker.patch("psutil.process_iter", return_value=[vanishing_proc])

        detector.scan()  # Should not raise

        # Bug H1: snapshot should be empty (no valid processes)
        snapshot = telemetry.set_running_cli.call_args[0][0]
        assert len(snapshot) == 0


class TestCLIObservableGauge:
    """Bug H1: cli_running must use ObservableGauge to avoid drift on crash."""

    def test_running_tools_tracked_as_set(self, mocker):
        """CLIDetector tracks running tools as a set for ObservableGauge callback."""
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

        procs = [_fake_process(100, "ollama")]
        mocker.patch("psutil.process_iter", return_value=procs)

        detector.scan()

        # Detector must expose current running tools
        running = detector.running_tools
        assert "Ollama" in running

        # Tool stops
        mocker.patch("psutil.process_iter", return_value=[])
        detector.scan()

        running = detector.running_tools
        assert "Ollama" not in running

    def test_running_tools_no_add_calls(self, mocker):
        """CLIDetector must NOT call cli_running.add() anymore."""
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

        procs = [_fake_process(100, "ollama")]
        mocker.patch("psutil.process_iter", return_value=procs)

        detector.scan()

        # With ObservableGauge, detector should NOT call .add() on cli_running
        telemetry.cli_running.add.assert_not_called()
