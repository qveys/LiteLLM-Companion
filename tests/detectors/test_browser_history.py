"""Tests for the browser history parser."""
import pytest
import sqlite3
import time
from pathlib import Path
from unittest.mock import Mock
from ai_cost_observer.config import AppConfig
from ai_cost_observer.detectors.browser_history import BrowserHistoryParser, _CHROME_EPOCH_OFFSET

@pytest.fixture
def mock_config(tmp_path: Path) -> AppConfig:
    """Provides a mock AppConfig for browser history testing."""
    config = AppConfig()
    config.state_dir = tmp_path / "state"
    config.ai_domains = [
        {"name": "Test AI", "domain": "test-ai.com", "cost_per_hour": 4.0, "category": "test"},
    ]
    return config

@pytest.fixture
def mock_telemetry() -> Mock:
    """Provides a mock TelemetryManager."""
    telemetry = Mock()
    telemetry.browser_domain_visit_count = Mock()
    telemetry.browser_domain_visit_count.add = Mock()
    telemetry.browser_domain_active_duration = Mock()
    telemetry.browser_domain_active_duration.add = Mock()
    telemetry.browser_domain_estimated_cost = Mock()
    telemetry.browser_domain_estimated_cost.add = Mock()
    return telemetry

@pytest.fixture
def chrome_history_db(tmp_path: Path) -> Path:
    """Creates a mock Chrome history SQLite DB for testing."""
    db_path = tmp_path / "History"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create schema
    cursor.execute("CREATE TABLE urls (id INTEGER PRIMARY KEY, url TEXT, title TEXT)")
    cursor.execute("CREATE TABLE visits (id INTEGER PRIMARY KEY, url INTEGER, visit_time INTEGER, visit_duration INTEGER)")

    # Insert data
    now_unix = time.time()
    now_chrome = int((now_unix + _CHROME_EPOCH_OFFSET) * 1_000_000)
    
    # Session 1: two visits close together
    cursor.execute("INSERT INTO urls (id, url, title) VALUES (1, 'https://test-ai.com/chat', 'Test Chat')")
    cursor.execute(f"INSERT INTO visits (url, visit_time, visit_duration) VALUES (1, {now_chrome - 600 * 1_000_000}, 120 * 1_000_000)") # 10 mins ago, 120s duration
    cursor.execute(f"INSERT INTO visits (url, visit_time, visit_duration) VALUES (1, {now_chrome - 300 * 1_000_000}, 180 * 1_000_000)") # 5 mins ago, 180s duration
    
    # Session 2: one visit much later (or earlier, doesn't matter for test)
    cursor.execute("INSERT INTO urls (id, url, title) VALUES (2, 'https://test-ai.com/chat/2', 'Test Chat 2')")
    cursor.execute(f"INSERT INTO visits (url, visit_time, visit_duration) VALUES (2, {now_chrome - 3600 * 1_000_000}, 60 * 1_000_000)") # 1 hour ago, 60s duration

    # Non-AI visit
    cursor.execute("INSERT INTO urls (id, url, title) VALUES (3, 'https://example.com', 'Example')")
    cursor.execute(f"INSERT INTO visits (url, visit_time, visit_duration) VALUES (3, {now_chrome - 100 * 1_000_000}, 30 * 1_000_000)")

    conn.commit()
    conn.close()
    return db_path

def test_browser_history_parsing_and_sessioning(mock_config: AppConfig, mock_telemetry: Mock, chrome_history_db: Path, mocker):
    """Test full flow: parsing, grouping, session estimation."""
    parser = BrowserHistoryParser(mock_config, mock_telemetry)
    # Set the 'since' to be far in the past to read all our test entries
    parser._default_since = time.time() - 2 * 3600  # 2 hours ago

    # Override browser discovery to only return our Chrome DB
    parser._get_browsers = lambda: [("chrome", chrome_history_db, parser._parse_chromium)]

    parser.scan()

    # --- Assertions ---
    # We expect 3 visits to test-ai.com domains
    mock_telemetry.browser_domain_visit_count.add.assert_called_once()
    visit_count_args = mock_telemetry.browser_domain_visit_count.add.call_args
    assert visit_count_args.args[0] == 3
    assert visit_count_args.args[1]["ai.domain"] == "test-ai.com"

    # Check duration estimation. Two sessions are expected.
    # Session 1: (ts_last - ts_first) + 300s = ((-300) - (-600)) + 300 = 300 + 300 = 600s
    # Session 2: (ts_last - ts_first) + 300s = ((-3600) - (-3600)) + 300 = 0 + 300 = 300s
    # Total = 900s
    mock_telemetry.browser_domain_active_duration.add.assert_called_once()
    duration_args = mock_telemetry.browser_domain_active_duration.add.call_args
    assert duration_args.args[0] == pytest.approx(900.0)
    assert duration_args.args[1]["ai.domain"] == "test-ai.com"

    # Check cost estimation
    # Cost = cost_per_hour * (duration / 3600) = 4.0 * (900 / 3600) = 4.0 * 0.25 = 1.0
    mock_telemetry.browser_domain_estimated_cost.add.assert_called_once()
    cost_args = mock_telemetry.browser_domain_estimated_cost.add.call_args
    assert cost_args.args[0] == pytest.approx(1.0)
    assert cost_args.args[1]["ai.domain"] == "test-ai.com"
