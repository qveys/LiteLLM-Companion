"""Tests for CLI detector cmdline matching fallback."""

from unittest.mock import MagicMock, patch

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
    tm.set_running_cli = MagicMock()
    tm.cli_active_duration = MagicMock()
    tm.cli_estimated_cost = MagicMock()
    return tm


def _fake_process(pid, name, cmdline=None):
    proc = MagicMock()
    proc.info = {"pid": pid, "name": name, "cmdline": cmdline or []}
    return proc


class TestCLIDetectorCmdlineMatching:
    """Test that CLI detector falls back to cmdline matching for interpreted scripts."""

    def test_match_by_process_name(self):
        """Standard match by process name still works."""
        tools = [
            {
                "name": "claude-code",
                "process_names": {"macos": ["claude"], "windows": ["claude.exe"]},
                "command_patterns": ["claude"],
                "category": "code",
                "cost_per_hour": 1.0,
            }
        ]
        config = _make_config(tools)
        telemetry = _make_telemetry()
        detector = CLIDetector(config, telemetry)

        procs = [_fake_process(100, "claude", ["/usr/local/bin/claude"])]
        with patch("psutil.process_iter", return_value=procs):
            detector.scan()

        # Bug H1: check snapshot
        snapshot = telemetry.set_running_cli.call_args[0][0]
        assert "claude-code" in snapshot

    def test_match_by_cmdline_pattern(self):
        """Processes running as 'node' should match via cmdline_patterns."""
        tools = [
            {
                "name": "gemini-cli",
                "process_names": {"macos": ["gemini"], "windows": ["gemini.cmd"]},
                "cmdline_patterns": ["gemini"],
                "command_patterns": ["gemini"],
                "category": "code",
                "cost_per_hour": 0.80,
            }
        ]
        config = _make_config(tools)
        telemetry = _make_telemetry()
        detector = CLIDetector(config, telemetry)

        # Simulates: node /usr/local/bin/gemini --args
        procs = [
            _fake_process(200, "node", ["node", "/usr/local/bin/gemini", "--interactive"])
        ]
        with patch("psutil.process_iter", return_value=procs):
            detector.scan()

        # Bug H1: check snapshot
        snapshot = telemetry.set_running_cli.call_args[0][0]
        assert "gemini-cli" in snapshot

    def test_no_match_when_cmdline_doesnt_contain_pattern(self):
        """Random node processes should not match."""
        tools = [
            {
                "name": "gemini-cli",
                "process_names": {"macos": ["gemini"], "windows": ["gemini.cmd"]},
                "cmdline_patterns": ["gemini"],
                "category": "code",
                "cost_per_hour": 0.80,
            }
        ]
        config = _make_config(tools)
        telemetry = _make_telemetry()
        detector = CLIDetector(config, telemetry)

        procs = [_fake_process(300, "node", ["node", "/usr/local/bin/webpack", "--watch"])]
        with patch("psutil.process_iter", return_value=procs):
            detector.scan()

        # Bug H1: check snapshot is empty
        snapshot = telemetry.set_running_cli.call_args[0][0]
        assert "gemini-cli" not in snapshot

    def test_process_name_match_takes_priority(self):
        """If both process name and cmdline match, process name wins (no double count)."""
        tools = [
            {
                "name": "claude-code",
                "process_names": {"macos": ["claude"], "windows": ["claude.exe"]},
                "cmdline_patterns": ["claude"],
                "category": "code",
                "cost_per_hour": 1.0,
            }
        ]
        config = _make_config(tools)
        telemetry = _make_telemetry()
        detector = CLIDetector(config, telemetry)

        procs = [_fake_process(400, "claude", ["/usr/local/bin/claude", "chat"])]
        with patch("psutil.process_iter", return_value=procs):
            detector.scan()

        # Bug H1: should appear exactly once in snapshot
        snapshot = telemetry.set_running_cli.call_args[0][0]
        assert len(snapshot) == 1
        assert "claude-code" in snapshot

    def test_vibe_detected_via_cmdline(self):
        """Vibe running as Python should be detected via cmdline."""
        tools = [
            {
                "name": "vibe",
                "process_names": {"macos": ["vibe"], "windows": ["vibe.exe"]},
                "cmdline_patterns": ["vibe"],
                "category": "code",
                "cost_per_hour": 0.60,
            }
        ]
        config = _make_config(tools)
        telemetry = _make_telemetry()
        detector = CLIDetector(config, telemetry)

        procs = [_fake_process(500, "Python", ["python3", "-m", "vibe", "run"])]
        with patch("psutil.process_iter", return_value=procs):
            detector.scan()

        # Bug H1: check snapshot
        snapshot = telemetry.set_running_cli.call_args[0][0]
        assert "vibe" in snapshot

    def test_empty_cmdline_no_crash(self):
        """Processes with empty or None cmdline should not crash."""
        tools = [
            {
                "name": "gemini-cli",
                "process_names": {"macos": ["gemini"], "windows": ["gemini.cmd"]},
                "cmdline_patterns": ["gemini"],
                "category": "code",
                "cost_per_hour": 0.80,
            }
        ]
        config = _make_config(tools)
        telemetry = _make_telemetry()
        detector = CLIDetector(config, telemetry)

        procs = [
            _fake_process(600, "node", None),
            _fake_process(601, "node", []),
        ]
        with patch("psutil.process_iter", return_value=procs):
            detector.scan()  # Should not raise

        # Bug H1: check snapshot is empty
        snapshot = telemetry.set_running_cli.call_args[0][0]
        assert len(snapshot) == 0
