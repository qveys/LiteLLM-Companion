"""Tests for the desktop app detector."""
import pytest
from unittest.mock import Mock, MagicMock
from pathlib import Path
from ai_cost_observer.config import AppConfig
from ai_cost_observer.detectors.desktop import DesktopDetector

@pytest.fixture
def mock_config(tmp_path: Path) -> AppConfig:
    """Provides a mock AppConfig for desktop detector testing."""
    config = AppConfig()
    config.state_dir = tmp_path / "state"
    config.ai_apps = [
        {
            "name": "Cool AI App",
            "process_names": {
                "macos": ["CoolAI", "CoolAIHelper"],
                "windows": ["CoolAI.exe"],
            },
            "cost_per_hour": 1.0,
        }
    ]
    return config

@pytest.fixture
def mock_telemetry() -> Mock:
    """Provides a mock TelemetryManager."""
    telemetry = Mock()
    telemetry.app_running = Mock()
    telemetry.app_running.add = Mock()
    # Add mocks for other metrics that will be called
    telemetry.app_active_duration = Mock()
    telemetry.app_active_duration.add = Mock()
    telemetry.app_estimated_cost = Mock()
    telemetry.app_estimated_cost.add = Mock()
    telemetry.app_cpu_usage = Mock()
    telemetry.app_cpu_usage.record = Mock()
    telemetry.app_memory_usage = Mock()
    telemetry.app_memory_usage.record = Mock()
    return telemetry

def create_mock_process(name: str, pid: int):
    """Factory for creating mock psutil.Process objects."""
    proc = MagicMock()
    proc.info = {"name": name, "pid": pid}
    proc.cpu_percent.return_value = 10.0
    # psutil memory_info returns a named tuple, mock that
    proc.memory_info.return_value = Mock(rss=200 * 1024 * 1024) # 200 MB
    return proc

def test_desktop_detector_state_changes(mock_config: AppConfig, mock_telemetry: Mock, mocker):
    """Test the stateful tracking of application start and stop."""
    # Mock active_window to return nothing, so we only test process running state
    mocker.patch("ai_cost_observer.detectors.desktop.get_foreground_app", return_value=None)
    
    detector = DesktopDetector(mock_config, mock_telemetry)

    # --- Scan 1: A new AI process appears ---
    mock_process_list = [create_mock_process("CoolAI", 123)]
    mocker.patch("psutil.process_iter", return_value=mock_process_list)
    
    detector.scan()
    
    # Assert that the 'app_running' counter was incremented by 1
    mock_telemetry.app_running.add.assert_called_once_with(1, {"app.name": "Cool AI App", "app.category": "unknown"})

    # --- Scan 2: The process is still running ---
    mock_telemetry.app_running.add.reset_mock() # Reset mock for the next assertion
    
    detector.scan()

    # Assert that the counter was NOT called again, as state hasn't changed
    mock_telemetry.app_running.add.assert_not_called()

    # --- Scan 3: The process disappears ---
    mocker.patch("psutil.process_iter", return_value=[]) # Empty process list
    
    detector.scan()

    # Assert that the 'app_running' counter was decremented by 1
    mock_telemetry.app_running.add.assert_called_once_with(-1, {"app.name": "Cool AI App", "app.category": "unknown"})
