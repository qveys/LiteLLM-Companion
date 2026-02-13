"""Tests for the CLI tool detector."""

from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest

from ai_cost_observer.config import AppConfig
from ai_cost_observer.detectors.cli import CLIDetector

# Note: In a larger test suite, fixtures and helpers would be moved to conftest.py
# For this exercise, we redefine them for clarity.


@pytest.fixture
def mock_cli_config(tmp_path: Path) -> AppConfig:
    """Provides a mock AppConfig for CLI detector testing."""
    config = AppConfig()
    config.state_dir = tmp_path / "state"
    config.ai_cli_tools = [
        {
            "name": "Ollama",
            "command_patterns": ["ollama"],
            "process_names": {
                "macos": ["ollama"],
                "windows": ["ollama.exe"],
            },
            "cost_per_hour": 0.5,
        }
    ]
    return config


@pytest.fixture
def mock_telemetry() -> Mock:
    """Provides a mock TelemetryManager."""
    telemetry = Mock()
    # ObservableGauge (Bug H1: was UpDownCounter)
    telemetry.cli_running = Mock()
    telemetry.set_running_cli = Mock()
    telemetry.cli_active_duration = Mock()
    telemetry.cli_active_duration.add = Mock()
    telemetry.cli_estimated_cost = Mock()
    telemetry.cli_estimated_cost.add = Mock()
    return telemetry


def create_mock_process(name: str, pid: int):
    """Factory for creating mock psutil.Process objects."""
    proc = MagicMock()
    proc.info = {"name": name, "pid": pid}
    proc.cpu_percent.return_value = 5.0
    proc.memory_info.return_value = Mock(rss=100 * 1024 * 1024)
    return proc


def test_cli_detector_state_changes(mock_cli_config: AppConfig, mock_telemetry: Mock, mocker):
    """Test the stateful tracking of CLI tool start and stop.

    Bug H1: Uses ObservableGauge via set_running_cli() instead of
    UpDownCounter .add(1)/.add(-1).
    """
    detector = CLIDetector(mock_cli_config, mock_telemetry)

    # --- Scan 1: A new AI CLI process appears ---
    mock_process_list = [create_mock_process("ollama", 456)]
    mocker.patch("psutil.process_iter", return_value=mock_process_list)

    detector.scan()

    # Verify running tools snapshot is pushed to telemetry
    mock_telemetry.set_running_cli.assert_called()
    snapshot = mock_telemetry.set_running_cli.call_args[0][0]
    assert "Ollama" in snapshot

    # --- Scan 2: The process is still running ---
    mock_telemetry.set_running_cli.reset_mock()

    detector.scan()

    # Snapshot still contains the tool
    snapshot = mock_telemetry.set_running_cli.call_args[0][0]
    assert "Ollama" in snapshot

    # --- Scan 3: The process disappears ---
    mocker.patch("psutil.process_iter", return_value=[])

    detector.scan()

    # Snapshot should be empty (tool stopped)
    snapshot = mock_telemetry.set_running_cli.call_args[0][0]
    assert "Ollama" not in snapshot
