"""Shared test fixtures for ai_cost_observer tests."""
import logging
import os
import tempfile

import pytest
from unittest.mock import Mock, MagicMock

from loguru import logger

from ai_cost_observer.config import AppConfig


class _PropagateHandler(logging.Handler):
    """Route loguru logs back into stdlib logging for pytest caplog support."""

    def emit(self, record):
        logging.getLogger(record.name).handle(record)


@pytest.fixture(autouse=True)
def caplog_loguru(caplog):
    """Route loguru logs to pytest's caplog."""
    handler_id = logger.add(
        _PropagateHandler(),
        format="{message}",
        level="DEBUG",
    )
    with caplog.at_level(logging.DEBUG):
        yield
    logger.remove(handler_id)


@pytest.fixture
def mock_telemetry():
    """Full mock of TelemetryManager with all metric instruments."""
    telemetry = Mock()
    # UpDownCounters
    telemetry.app_running = Mock()
    telemetry.app_running.add = Mock()
    telemetry.cli_running = Mock()
    telemetry.cli_running.add = Mock()
    # Counters
    telemetry.app_active_duration = Mock()
    telemetry.app_active_duration.add = Mock()
    telemetry.app_estimated_cost = Mock()
    telemetry.app_estimated_cost.add = Mock()
    telemetry.cli_active_duration = Mock()
    telemetry.cli_active_duration.add = Mock()
    telemetry.cli_estimated_cost = Mock()
    telemetry.cli_estimated_cost.add = Mock()
    telemetry.cli_command_count = Mock()
    telemetry.cli_command_count.add = Mock()
    telemetry.browser_domain_active_duration = Mock()
    telemetry.browser_domain_active_duration.add = Mock()
    telemetry.browser_domain_visit_count = Mock()
    telemetry.browser_domain_visit_count.add = Mock()
    telemetry.browser_domain_estimated_cost = Mock()
    telemetry.browser_domain_estimated_cost.add = Mock()
    telemetry.tokens_input_total = Mock()
    telemetry.tokens_input_total.add = Mock()
    telemetry.tokens_output_total = Mock()
    telemetry.tokens_output_total.add = Mock()
    telemetry.tokens_cost_usd_total = Mock()
    telemetry.tokens_cost_usd_total.add = Mock()
    telemetry.prompt_count_total = Mock()
    telemetry.prompt_count_total.add = Mock()
    # Gauges (Bug C3: was Histogram)
    telemetry.app_cpu_usage = Mock()
    telemetry.app_cpu_usage.set = Mock()
    telemetry.app_memory_usage = Mock()
    telemetry.app_memory_usage.set = Mock()
    return telemetry


@pytest.fixture
def mock_config(tmp_path):
    """Standard AppConfig for testing."""
    config = AppConfig()
    config.scan_interval_seconds = 15
    config.otel_endpoint = "http://localhost:4317"
    config.otel_bearer_token = "test-token"
    config.host_name = "test-host"
    config.state_dir = tmp_path / "state"
    config.state_dir.mkdir(parents=True, exist_ok=True)
    return config


@pytest.fixture
def sample_ai_config():
    """Minimal ai_config dict for detector tests."""
    return {
        "ai_apps": [
            {
                "name": "TestApp",
                "process_names": {
                    "macos": ["TestApp"],
                    "windows": ["TestApp.exe"],
                },
                "category": "chat",
                "cost_per_hour": 0.50,
            }
        ],
        "ai_domains": [
            {
                "domain": "test.ai",
                "name": "Test AI",
                "category": "chat",
                "cost_per_hour": 0.30,
            }
        ],
        "ai_cli_tools": [
            {
                "name": "test-cli",
                "process_names": {"macos": ["test-cli"], "windows": ["test-cli.exe"]},
                "command_patterns": ["test-cli"],
                "category": "code",
                "cost_per_hour": 0.40,
            }
        ],
    }


@pytest.fixture
def temp_dir():
    """Provide a temporary directory that's cleaned up after test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir
