"""Browser history parser — reads Chrome/Firefox/Safari SQLite history for AI domain visits."""

from __future__ import annotations

import os
import platform
import shutil
import sqlite3
import tempfile
import time
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from loguru import logger

from ai_cost_observer.config import AppConfig
from ai_cost_observer.telemetry import TelemetryManager

# Chrome uses a custom epoch: microseconds since 1601-01-01
_CHROME_EPOCH_OFFSET = 11644473600  # seconds between 1601 and 1970
_SESSION_GAP_SECONDS = 30 * 60  # 30 minutes = new session

# All Chromium-based browsers share the same SQLite schema
CHROMIUM_BROWSERS = {
    "Chrome": {
        "macos": "~/Library/Application Support/Google/Chrome/Default/History",
        "windows": "%LOCALAPPDATA%/Google/Chrome/User Data/Default/History",
    },
    "Edge": {
        "macos": "~/Library/Application Support/Microsoft Edge/Default/History",
        "windows": "%LOCALAPPDATA%/Microsoft/Edge/User Data/Default/History",
    },
    "Brave": {
        "macos": "~/Library/Application Support/BraveSoftware/Brave-Browser/Default/History",
        "windows": "%LOCALAPPDATA%/BraveSoftware/Brave-Browser/User Data/Default/History",
    },
    "Arc": {
        "macos": "~/Library/Application Support/Arc/User Data/Default/History",
    },
    "Vivaldi": {
        "macos": "~/Library/Application Support/Vivaldi/Default/History",
        "windows": "%LOCALAPPDATA%/Vivaldi/User Data/Default/History",
    },
    "Opera": {
        "macos": "~/Library/Application Support/com.operasoftware.Opera/History",
        "windows": "%APPDATA%/Opera Software/Opera Stable/History",
    },
}


class BrowserHistoryParser:
    """Parses browser history databases for AI domain visits."""

    def __init__(self, config: AppConfig, telemetry: TelemetryManager) -> None:
        self.config = config
        self.telemetry = telemetry
        self._default_since: float = time.time()
        self._last_scan_time: dict[str, float] = {}
        self._domain_lookup = {d["domain"]: d for d in config.ai_domains}

    def scan(self) -> None:
        """Parse all browser histories for new AI domain visits."""
        for browser_name, db_path, parser_fn in self._get_browsers():
            since = self._last_scan_time.get(browser_name, self._default_since)
            scan_started_at = time.time()
            try:
                visits = parser_fn(db_path, since)
                if visits is None:
                    continue
                if visits:
                    self._process_visits(visits, browser_name)
                self._last_scan_time[browser_name] = scan_started_at
            except Exception:
                logger.opt(exception=True).warning("Error parsing {} history", browser_name)

    def _get_browsers(self) -> list[tuple[str, Path, Callable[[Path, float], list[dict] | None]]]:
        """Return available browsers with their history paths and parsers."""
        browsers = []
        system = platform.system()
        platform_key = "macos" if system == "Darwin" else "windows" if system == "Windows" else None

        # All Chromium-based browsers (same SQLite schema as Chrome)
        if platform_key:
            for browser_name, paths in CHROMIUM_BROWSERS.items():
                raw_path = paths.get(platform_key)
                if not raw_path:
                    continue
                resolved = Path(os.path.expandvars(os.path.expanduser(raw_path)))
                if resolved.exists():
                    browsers.append((browser_name.lower(), resolved, self._parse_chromium))

        # Firefox (different schema)
        firefox_path = self._firefox_history_path(system)
        if firefox_path and firefox_path.exists():
            browsers.append(("firefox", firefox_path, self._parse_firefox))

        # Safari (macOS only, different schema)
        if system == "Darwin":
            safari_path = Path.home() / "Library" / "Safari" / "History.db"
            if safari_path.exists():
                browsers.append(("safari", safari_path, self._parse_safari))

        return browsers

    def _parse_chromium(self, db_path: Path, since: float) -> list[dict] | None:
        """Parse Chromium-based browser history. Timestamps are microseconds since 1601-01-01."""
        chrome_since = int((since + _CHROME_EPOCH_OFFSET) * 1_000_000)

        query = """
            SELECT urls.url, urls.title, visits.visit_time, visits.visit_duration
            FROM visits
            JOIN urls ON visits.url = urls.id
            WHERE visits.visit_time > ?
            ORDER BY visits.visit_time ASC
        """
        return self._query_sqlite(db_path, query, (chrome_since,), "chromium")

    def _parse_firefox(self, db_path: Path, since: float) -> list[dict] | None:
        """Parse Firefox history. Timestamps are microseconds since Unix epoch."""
        ff_since = int(since * 1_000_000)

        query = """
            SELECT p.url, p.title, v.visit_date AS visit_time, 0 AS visit_duration
            FROM moz_historyvisits v
            JOIN moz_places p ON v.place_id = p.id
            WHERE v.visit_date > ?
            ORDER BY v.visit_date ASC
        """
        return self._query_sqlite(db_path, query, (ff_since,), "firefox")

    def _parse_safari(self, db_path: Path, since: float) -> list[dict] | None:
        """Parse Safari history. Timestamps are seconds since 2001-01-01 (Core Data epoch)."""
        # Core Data epoch offset: seconds between 2001-01-01 and 1970-01-01
        core_data_offset = 978307200
        safari_since = since - core_data_offset

        query = """
            SELECT hi.url, hv.title, hv.visit_time AS visit_time, 0 AS visit_duration
            FROM history_visits hv
            JOIN history_items hi ON hv.history_item = hi.id
            WHERE hv.visit_time > ?
            ORDER BY hv.visit_time ASC
        """
        return self._query_sqlite(db_path, query, (safari_since,), "safari")

    def _query_sqlite(
        self, db_path: Path, query: str, params: tuple, browser: str
    ) -> list[dict] | None:
        """Copy DB to temp, run query, return results."""
        tmp_path = None
        try:
            # Copy to temp to avoid lock conflicts with running browser
            tmp_fd, tmp_path = tempfile.mkstemp(suffix=".sqlite")
            os.close(tmp_fd)
            shutil.copy2(db_path, tmp_path)

            conn = sqlite3.connect(f"file:{tmp_path}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            try:
                rows = conn.execute(query, params).fetchall()
                return [
                    {
                        "url": row["url"],
                        "title": row["title"] if "title" in row.keys() else "",
                        "visit_time": row["visit_time"],
                        "visit_duration": (
                            row["visit_duration"] if "visit_duration" in row.keys() else 0
                        ),
                        "browser": browser,
                    }
                    for row in rows
                ]
            finally:
                conn.close()
        except sqlite3.OperationalError as e:
            logger.warning("SQLite error for {}: {}", browser, e)
            return None
        except PermissionError:
            logger.warning("Permission denied copying {} history DB", browser)
            return None
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    @staticmethod
    def _url_matches_domain(url: str, domain: str) -> bool:
        """Check if a URL matches a tracked domain using proper hostname parsing.

        Uses urllib.parse.urlparse() to extract the hostname, then checks for
        exact match or subdomain match (hostname ends with '.'+domain).
        Domains that include a path component (e.g. 'github.com/copilot') also
        require the URL path to start with that prefix.
        """
        try:
            parsed = urlparse(url)
            hostname = (parsed.hostname or "").lower()
        except Exception:
            return False

        if "/" in domain:
            # Domain includes a path prefix, e.g. "github.com/copilot"
            dom_part, _, path_part = domain.partition("/")
            path_prefix = "/" + path_part
            host_ok = hostname == dom_part or hostname.endswith("." + dom_part)
            if host_ok and parsed.path.startswith(path_prefix):
                return True
        else:
            if hostname == domain or hostname.endswith("." + domain):
                return True

        return False

    def _process_visits(self, visits: list[dict], browser_name: str) -> None:
        """Group visits by AI domain, estimate sessions, update metrics."""
        domain_visits: dict[str, list[dict]] = {}

        for visit in visits:
            url = visit.get("url", "")
            for domain, domain_cfg in self._domain_lookup.items():
                if self._url_matches_domain(url, domain):
                    if domain not in domain_visits:
                        domain_visits[domain] = []
                    domain_visits[domain].append(visit)
                    break

        for domain, visits_list in domain_visits.items():
            domain_cfg = self._domain_lookup[domain]
            labels = {
                "ai.domain": domain,
                "ai.category": domain_cfg.get("category", "unknown"),
                "browser.name": browser_name,
                "usage.source": "history_parser",
            }

            # Count visits
            self.telemetry.browser_domain_visit_count.add(len(visits_list), labels)

            # Estimate session duration
            total_duration = self._estimate_session_duration(visits_list, browser_name)
            if total_duration > 0:
                self.telemetry.browser_domain_active_duration.add(total_duration, labels)

                cost_per_hour = domain_cfg.get("cost_per_hour", 0)
                if cost_per_hour > 0:
                    cost_labels = {
                        "ai.domain": domain,
                        "ai.category": domain_cfg.get("category", "unknown"),
                    }
                    cost = cost_per_hour * (total_duration / 3600)
                    self.telemetry.browser_domain_estimated_cost.add(cost, cost_labels)

            logger.debug(
                "Browser history: {} — {} visits, {:.0f}s estimated duration ({})",
                domain,
                len(visits_list),
                total_duration,
                browser_name,
            )

    def _estimate_session_duration(self, visits: list[dict], browser: str) -> float:
        """Estimate total session duration from visit timestamps.

        For multi-visit sessions, adds a 5-minute buffer after the last visit
        to account for reading/interaction time. Single-visit sessions get a
        flat 60-second estimate instead of the full 300-second buffer.
        """
        if not visits:
            return 0.0

        # Normalize timestamps to Unix seconds
        # Use the browser type stored in each visit dict (set by the parser)
        timestamps = []
        for v in visits:
            ts = v["visit_time"]
            visit_browser = v.get("browser", browser)
            if visit_browser == "chromium":
                ts = ts / 1_000_000 - _CHROME_EPOCH_OFFSET
            elif visit_browser == "firefox":
                ts = ts / 1_000_000
            elif visit_browser == "safari":
                ts = ts + 978307200  # Core Data → Unix
            timestamps.append(ts)

        timestamps.sort()

        # Split into sessions (gap > 30 min = new session)
        total = 0.0
        session_start = timestamps[0]
        session_visit_count = 1
        prev = timestamps[0]

        for ts in timestamps[1:]:
            gap = ts - prev
            if gap > _SESSION_GAP_SECONDS:
                # Close previous session
                session_span = prev - session_start
                if session_visit_count > 1:
                    total += session_span + 300  # multi-visit: 5 min buffer
                else:
                    total += 60  # single-visit: flat 60s estimate
                session_start = ts
                session_visit_count = 1
            else:
                session_visit_count += 1
            prev = ts

        # Final session
        session_span = prev - session_start
        if session_visit_count > 1:
            total += session_span + 300  # multi-visit: 5 min buffer
        else:
            total += 60  # single-visit: flat 60s estimate
        return max(total, 0)

    @staticmethod
    def _firefox_history_path(system: str) -> Path | None:
        if system == "Darwin":
            profiles_dir = Path.home() / "Library" / "Application Support" / "Firefox" / "Profiles"
        elif system == "Windows":
            appdata = os.environ.get("APPDATA", "")
            if not appdata:
                return None
            profiles_dir = Path(appdata) / "Mozilla" / "Firefox" / "Profiles"
        else:
            return None

        if profiles_dir.exists():
            for profile in profiles_dir.iterdir():
                places = profile / "places.sqlite"
                if places.exists():
                    return places
        return None
