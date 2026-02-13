"""Extended browser history tests — Firefox, Safari, Edge, Brave, DB locked handling."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from ai_cost_observer.config import AppConfig
from ai_cost_observer.detectors.browser_history import (
    _CHROME_EPOCH_OFFSET,
    BrowserHistoryParser,
)


@pytest.fixture
def browser_config(tmp_path: Path) -> AppConfig:
    """AppConfig with AI domains for browser history testing."""
    config = AppConfig()
    config.state_dir = tmp_path / "state"
    config.state_dir.mkdir(parents=True, exist_ok=True)
    config.ai_domains = [
        {"name": "ChatGPT", "domain": "chat.openai.com", "cost_per_hour": 4.0, "category": "chat"},
        {"name": "Claude", "domain": "claude.ai", "cost_per_hour": 3.0, "category": "chat"},
    ]
    return config


@pytest.fixture
def browser_telemetry() -> Mock:
    """Mock telemetry for browser history tests."""
    telemetry = Mock()
    telemetry.browser_domain_visit_count = Mock()
    telemetry.browser_domain_visit_count.add = Mock()
    telemetry.browser_domain_active_duration = Mock()
    telemetry.browser_domain_active_duration.add = Mock()
    telemetry.browser_domain_estimated_cost = Mock()
    telemetry.browser_domain_estimated_cost.add = Mock()
    return telemetry


def _create_firefox_db(db_path: Path, visits: list[tuple[str, int]]) -> None:
    """Create a Firefox-style places.sqlite database with given visits.

    Args:
        db_path: Path where the SQLite DB will be created.
        visits: List of (url, unix_timestamp_seconds) tuples.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE moz_places (id INTEGER PRIMARY KEY, url TEXT, title TEXT)")
    cursor.execute(
        "CREATE TABLE moz_historyvisits"
        " (id INTEGER PRIMARY KEY, place_id INTEGER, visit_date INTEGER)"
    )

    for idx, (url, ts_seconds) in enumerate(visits, start=1):
        # Firefox stores timestamps as microseconds since Unix epoch
        ff_ts = int(ts_seconds * 1_000_000)
        cursor.execute(
            "INSERT INTO moz_places (id, url, title) VALUES (?, ?, ?)", (idx, url, f"Title {idx}")
        )
        cursor.execute(
            "INSERT INTO moz_historyvisits (place_id, visit_date) VALUES (?, ?)", (idx, ff_ts)
        )

    conn.commit()
    conn.close()


def _create_safari_db(db_path: Path, visits: list[tuple[str, int]]) -> None:
    """Create a Safari-style History.db database with given visits.

    Args:
        db_path: Path where the SQLite DB will be created.
        visits: List of (url, unix_timestamp_seconds) tuples.
    """
    # Core Data epoch offset: seconds between 2001-01-01 and 1970-01-01
    core_data_offset = 978307200
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE history_items (id INTEGER PRIMARY KEY, url TEXT)")
    cursor.execute(
        "CREATE TABLE history_visits"
        " (id INTEGER PRIMARY KEY, history_item INTEGER, title TEXT, visit_time REAL)"
    )

    for idx, (url, ts_seconds) in enumerate(visits, start=1):
        safari_ts = ts_seconds - core_data_offset  # Convert Unix → Core Data
        cursor.execute("INSERT INTO history_items (id, url) VALUES (?, ?)", (idx, url))
        cursor.execute(
            "INSERT INTO history_visits (history_item, title, visit_time) VALUES (?, ?, ?)",
            (idx, f"Title {idx}", safari_ts),
        )

    conn.commit()
    conn.close()


def _create_chromium_db(db_path: Path, visits: list[tuple[str, int]]) -> None:
    """Create a Chromium-style History database with given visits.

    Args:
        db_path: Path where the SQLite DB will be created.
        visits: List of (url, unix_timestamp_seconds) tuples.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE urls (id INTEGER PRIMARY KEY, url TEXT, title TEXT)")
    cursor.execute(
        "CREATE TABLE visits"
        " (id INTEGER PRIMARY KEY, url INTEGER, visit_time INTEGER, visit_duration INTEGER)"
    )

    for idx, (url, ts_seconds) in enumerate(visits, start=1):
        chrome_ts = int((ts_seconds + _CHROME_EPOCH_OFFSET) * 1_000_000)
        cursor.execute(
            "INSERT INTO urls (id, url, title) VALUES (?, ?, ?)", (idx, url, f"Title {idx}")
        )
        cursor.execute(
            "INSERT INTO visits (url, visit_time, visit_duration) VALUES (?, ?, ?)",
            (idx, chrome_ts, 60_000_000),  # 60s duration
        )

    conn.commit()
    conn.close()


class TestFirefoxHistoryParsing:
    """Tests for Firefox history parsing (moz_places + moz_historyvisits schema)."""

    def test_firefox_visits_detected(self, browser_config, browser_telemetry, tmp_path):
        """Firefox visits to AI domains are correctly parsed and reported."""
        now = time.time()
        db_path = tmp_path / "places.sqlite"
        _create_firefox_db(
            db_path,
            [
                ("https://chat.openai.com/chat/1", int(now - 600)),
                ("https://chat.openai.com/chat/2", int(now - 300)),
                ("https://example.com", int(now - 200)),  # non-AI
            ],
        )

        parser = BrowserHistoryParser(browser_config, browser_telemetry)
        parser._default_since = now - 3600

        # Override browser discovery to only return our Firefox DB
        parser._get_browsers = lambda: [("firefox", db_path, parser._parse_firefox)]

        parser.scan()

        # Should report 2 visits to chat.openai.com
        browser_telemetry.browser_domain_visit_count.add.assert_called_once()
        args = browser_telemetry.browser_domain_visit_count.add.call_args
        assert args[0][0] == 2
        assert args[0][1]["ai.domain"] == "chat.openai.com"

    def test_firefox_empty_db(self, browser_config, browser_telemetry, tmp_path):
        """Firefox DB with no AI visits produces no metrics."""
        now = time.time()
        db_path = tmp_path / "places.sqlite"
        _create_firefox_db(
            db_path,
            [
                ("https://example.com", int(now - 600)),
            ],
        )

        parser = BrowserHistoryParser(browser_config, browser_telemetry)
        parser._default_since = now - 3600
        parser._get_browsers = lambda: [("firefox", db_path, parser._parse_firefox)]

        parser.scan()

        browser_telemetry.browser_domain_visit_count.add.assert_not_called()


class TestSafariHistoryParsing:
    """Tests for Safari history parsing (Core Data epoch timestamps)."""

    def test_safari_visits_detected(self, browser_config, browser_telemetry, tmp_path):
        """Safari visits with Core Data timestamps are correctly parsed."""
        now = time.time()
        db_path = tmp_path / "History.db"
        _create_safari_db(
            db_path,
            [
                ("https://claude.ai/chat/1", int(now - 500)),
                ("https://claude.ai/chat/2", int(now - 100)),
            ],
        )

        parser = BrowserHistoryParser(browser_config, browser_telemetry)
        parser._default_since = now - 3600
        parser._get_browsers = lambda: [("safari", db_path, parser._parse_safari)]

        parser.scan()

        browser_telemetry.browser_domain_visit_count.add.assert_called_once()
        args = browser_telemetry.browser_domain_visit_count.add.call_args
        assert args[0][0] == 2
        assert args[0][1]["ai.domain"] == "claude.ai"

    def test_safari_duration_estimation(self, browser_config, browser_telemetry, tmp_path):
        """Safari duration is estimated using session gap algorithm."""
        now = time.time()
        db_path = tmp_path / "History.db"
        # Two visits 100s apart (same session) => duration = (100 - 0) + 300 = 400
        _create_safari_db(
            db_path,
            [
                ("https://claude.ai/chat/1", int(now - 200)),
                ("https://claude.ai/chat/2", int(now - 100)),
            ],
        )

        parser = BrowserHistoryParser(browser_config, browser_telemetry)
        parser._default_since = now - 3600
        parser._get_browsers = lambda: [("safari", db_path, parser._parse_safari)]

        parser.scan()

        browser_telemetry.browser_domain_active_duration.add.assert_called_once()
        duration = browser_telemetry.browser_domain_active_duration.add.call_args[0][0]
        assert duration == pytest.approx(400.0, abs=2)


class TestEdgeBrowserHistory:
    """Tests for Edge browser (Chromium schema, same as Chrome)."""

    def test_edge_uses_chromium_schema(self, browser_config, browser_telemetry, tmp_path):
        """Edge uses the same Chromium schema and parser as Chrome."""
        now = time.time()
        db_path = tmp_path / "History"
        _create_chromium_db(
            db_path,
            [
                ("https://chat.openai.com/chat/edge", int(now - 300)),
            ],
        )

        parser = BrowserHistoryParser(browser_config, browser_telemetry)
        parser._default_since = now - 3600
        # Simulate Edge using _parse_chromium (same as all Chromium browsers)
        parser._get_browsers = lambda: [("edge", db_path, parser._parse_chromium)]

        parser.scan()

        browser_telemetry.browser_domain_visit_count.add.assert_called_once()
        args = browser_telemetry.browser_domain_visit_count.add.call_args
        assert args[0][0] == 1
        assert args[0][1]["browser.name"] == "edge"


class TestBraveBrowserHistory:
    """Tests for Brave browser (Chromium schema)."""

    def test_brave_uses_chromium_schema(self, browser_config, browser_telemetry, tmp_path):
        """Brave uses the same Chromium schema and parser."""
        now = time.time()
        db_path = tmp_path / "History"
        _create_chromium_db(
            db_path,
            [
                ("https://claude.ai/brave/1", int(now - 500)),
                ("https://claude.ai/brave/2", int(now - 400)),
            ],
        )

        parser = BrowserHistoryParser(browser_config, browser_telemetry)
        parser._default_since = now - 3600
        parser._get_browsers = lambda: [("brave", db_path, parser._parse_chromium)]

        parser.scan()

        browser_telemetry.browser_domain_visit_count.add.assert_called_once()
        args = browser_telemetry.browser_domain_visit_count.add.call_args
        assert args[0][0] == 2
        assert args[0][1]["browser.name"] == "brave"


class TestDBLockedHandling:
    """Tests for graceful failure when SQLite DB is locked."""

    def test_db_locked_returns_none_gracefully(self, browser_config, browser_telemetry, tmp_path):
        """When the DB is locked, the parser logs a warning and returns None."""
        db_path = tmp_path / "History"
        # Create a valid Chromium DB
        _create_chromium_db(
            db_path,
            [
                ("https://chat.openai.com/locked", int(time.time() - 300)),
            ],
        )

        parser = BrowserHistoryParser(browser_config, browser_telemetry)
        parser._default_since = time.time() - 3600

        # Simulate DB lock by patching _query_sqlite to raise OperationalError
        def locked_query(db_path, query, params, browser):
            raise sqlite3.OperationalError("database is locked")

        parser._query_sqlite = locked_query
        parser._get_browsers = lambda: [("chrome", db_path, parser._parse_chromium)]

        # Should not raise; should log warning and continue
        parser.scan()

        # No metrics should be emitted
        browser_telemetry.browser_domain_visit_count.add.assert_not_called()

    def test_permission_denied_handled_gracefully(
        self, browser_config, browser_telemetry, tmp_path
    ):
        """PermissionError during DB copy is handled gracefully."""
        db_path = tmp_path / "History"
        db_path.write_bytes(b"fake")

        parser = BrowserHistoryParser(browser_config, browser_telemetry)
        parser._default_since = time.time() - 3600

        with patch("shutil.copy2", side_effect=PermissionError("permission denied")):
            result = parser._query_sqlite(db_path, "SELECT 1", (), "chrome")

        assert result is None
