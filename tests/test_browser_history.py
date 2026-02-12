"""Tests for browser history domain matching logic."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from ai_cost_observer.config import AppConfig
from ai_cost_observer.detectors.browser_history import BrowserHistoryParser


@pytest.fixture
def parser_with_domains():
    """Create a BrowserHistoryParser with a specific set of AI domains."""
    config = AppConfig(
        ai_domains=[
            {"domain": "chat.openai.com", "category": "chat", "cost_per_hour": 0.50},
            {"domain": "claude.ai", "category": "chat", "cost_per_hour": 0.60},
            {"domain": "github.com/copilot", "category": "code", "cost_per_hour": 0.40},
        ]
    )
    telemetry = Mock()
    telemetry.browser_domain_visit_count = Mock()
    telemetry.browser_domain_visit_count.add = Mock()
    telemetry.browser_domain_active_duration = Mock()
    telemetry.browser_domain_active_duration.add = Mock()
    telemetry.browser_domain_estimated_cost = Mock()
    telemetry.browser_domain_estimated_cost.add = Mock()
    return BrowserHistoryParser(config, telemetry)


class TestDomainMatching:
    """Test that _process_visits uses exact hostname matching, not substring."""

    def test_exact_domain_matches(self, parser_with_domains):
        """chat.openai.com should match chat.openai.com."""
        visits = [
            {
                "url": "https://chat.openai.com/some/path",
                "title": "ChatGPT",
                "visit_time": 13300000000000000,
                "visit_duration": 0,
                "browser": "chromium",
            }
        ]
        parser_with_domains._process_visits(visits, "chrome")
        parser_with_domains.telemetry.browser_domain_visit_count.add.assert_called()
        call_args = parser_with_domains.telemetry.browser_domain_visit_count.add.call_args
        assert call_args[0][1]["ai.domain"] == "chat.openai.com"

    def test_subdomain_matches(self, parser_with_domains):
        """subdomain.chat.openai.com should match chat.openai.com."""
        visits = [
            {
                "url": "https://subdomain.chat.openai.com/path",
                "title": "ChatGPT",
                "visit_time": 13300000000000000,
                "visit_duration": 0,
                "browser": "chromium",
            }
        ]
        parser_with_domains._process_visits(visits, "chrome")
        parser_with_domains.telemetry.browser_domain_visit_count.add.assert_called()
        call_args = parser_with_domains.telemetry.browser_domain_visit_count.add.call_args
        assert call_args[0][1]["ai.domain"] == "chat.openai.com"

    def test_prefix_domain_does_not_match(self, parser_with_domains):
        """notchat.openai.com should NOT match chat.openai.com."""
        visits = [
            {
                "url": "https://notchat.openai.com/path",
                "title": "Not ChatGPT",
                "visit_time": 13300000000000000,
                "visit_duration": 0,
                "browser": "chromium",
            }
        ]
        parser_with_domains._process_visits(visits, "chrome")
        parser_with_domains.telemetry.browser_domain_visit_count.add.assert_not_called()

    def test_domain_in_path_does_not_match(self, parser_with_domains):
        """evil.com/chat.openai.com should NOT match chat.openai.com."""
        visits = [
            {
                "url": "https://evil.com/chat.openai.com",
                "title": "Evil Site",
                "visit_time": 13300000000000000,
                "visit_duration": 0,
                "browser": "chromium",
            }
        ]
        parser_with_domains._process_visits(visits, "chrome")
        parser_with_domains.telemetry.browser_domain_visit_count.add.assert_not_called()

    def test_domain_with_path_matching(self, parser_with_domains):
        """github.com/copilot should match URLs with the /copilot path prefix."""
        visits = [
            {
                "url": "https://github.com/copilot/settings",
                "title": "Copilot",
                "visit_time": 13300000000000000,
                "visit_duration": 0,
                "browser": "chromium",
            }
        ]
        parser_with_domains._process_visits(visits, "chrome")
        parser_with_domains.telemetry.browser_domain_visit_count.add.assert_called()
        call_args = parser_with_domains.telemetry.browser_domain_visit_count.add.call_args
        assert call_args[0][1]["ai.domain"] == "github.com/copilot"

    def test_domain_with_path_no_false_positive(self, parser_with_domains):
        """github.com/other should NOT match github.com/copilot."""
        visits = [
            {
                "url": "https://github.com/other/repo",
                "title": "Other",
                "visit_time": 13300000000000000,
                "visit_duration": 0,
                "browser": "chromium",
            }
        ]
        parser_with_domains._process_visits(visits, "chrome")
        parser_with_domains.telemetry.browser_domain_visit_count.add.assert_not_called()

    def test_invalid_url_does_not_crash(self, parser_with_domains):
        """Invalid URLs should be silently skipped, not cause crashes."""
        visits = [
            {
                "url": "not-a-valid-url",
                "title": "",
                "visit_time": 13300000000000000,
                "visit_duration": 0,
                "browser": "chromium",
            }
        ]
        parser_with_domains._process_visits(visits, "chrome")
        parser_with_domains.telemetry.browser_domain_visit_count.add.assert_not_called()
