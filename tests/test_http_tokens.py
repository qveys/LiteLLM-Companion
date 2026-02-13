"""Tests for the HTTP receiver /api/tokens endpoint."""

import json
from unittest.mock import MagicMock

from ai_cost_observer.config import AppConfig
from ai_cost_observer.detectors.token_tracker import estimate_cost
from ai_cost_observer.server import http_receiver
from ai_cost_observer.server.http_receiver import create_app


def _make_telemetry():
    tm = MagicMock()
    tm.tokens_input_total = MagicMock()
    tm.tokens_output_total = MagicMock()
    tm.tokens_cost_usd_total = MagicMock()
    tm.prompt_count_total = MagicMock()
    tm.browser_domain_active_duration = MagicMock()
    tm.browser_domain_visit_count = MagicMock()
    tm.browser_domain_estimated_cost = MagicMock()
    return tm


class TestTokensEndpoint:
    def setup_method(self):
        # Reset the global token tracker
        http_receiver._token_tracker = None
        self.config = AppConfig()
        self.config.ai_domains = []
        self.telemetry = _make_telemetry()
        self.app = create_app(self.config, self.telemetry)

    def test_receive_token_event_without_tracker(self):
        """Without a token tracker, metrics are recorded directly."""
        with self.app.test_client() as client:
            resp = client.post(
                "/api/tokens",
                data=json.dumps({
                    "events": [
                        {
                            "type": "api_intercept",
                            "tool": "claude-web",
                            "model": "claude-sonnet-4-5",
                            "input_tokens": 1000,
                            "output_tokens": 500,
                        }
                    ]
                }),
                content_type="application/json",
            )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["processed"] == 1

        labels = {"tool.name": "claude-web", "model.name": "claude-sonnet-4-5"}
        self.telemetry.tokens_input_total.add.assert_called_once_with(1000, labels)
        self.telemetry.tokens_output_total.add.assert_called_once_with(500, labels)

        # Cost must be recorded in the fallback path (fixes #45)
        expected_cost = estimate_cost("claude-sonnet-4-5", 1000, 500)
        self.telemetry.tokens_cost_usd_total.add.assert_called_once_with(expected_cost, labels)

    def test_fallback_cost_uses_default_pricing_for_unknown_model(self):
        """Unknown model falls back to mid-range pricing for cost estimation."""
        with self.app.test_client() as client:
            resp = client.post(
                "/api/tokens",
                data=json.dumps({
                    "events": [
                        {
                            "type": "api_intercept",
                            "tool": "some-tool",
                            "model": "unknown-model-xyz",
                            "input_tokens": 5000,
                            "output_tokens": 1000,
                        }
                    ]
                }),
                content_type="application/json",
            )

        assert resp.status_code == 200
        labels = {"tool.name": "some-tool", "model.name": "unknown-model-xyz"}
        expected_cost = estimate_cost("unknown-model-xyz", 5000, 1000)
        assert expected_cost > 0  # default fallback pricing should produce non-zero cost
        self.telemetry.tokens_cost_usd_total.add.assert_called_once_with(expected_cost, labels)

    def test_fallback_no_cost_when_zero_tokens(self):
        """No cost metric recorded when both token counts are zero."""
        with self.app.test_client() as client:
            resp = client.post(
                "/api/tokens",
                data=json.dumps({
                    "events": [
                        {
                            "type": "api_intercept",
                            "tool": "test-tool",
                            "model": "gpt-4o",
                            "input_tokens": 0,
                            "output_tokens": 0,
                        }
                    ]
                }),
                content_type="application/json",
            )

        assert resp.status_code == 200
        self.telemetry.tokens_cost_usd_total.add.assert_not_called()

    def test_receive_token_event_with_tracker(self):
        """With a token tracker, events are forwarded to it."""
        tracker = MagicMock()
        http_receiver.set_token_tracker(tracker)
        # Re-create app with tracker set
        app = create_app(self.config, self.telemetry)

        with app.test_client() as client:
            resp = client.post(
                "/api/tokens",
                data=json.dumps({
                    "events": [
                        {
                            "type": "api_intercept",
                            "tool": "chatgpt-web",
                            "model": "gpt-4o",
                            "input_tokens": 2000,
                            "output_tokens": 800,
                        }
                    ]
                }),
                content_type="application/json",
            )

        assert resp.status_code == 200
        tracker.record_api_intercept.assert_called_once_with(
            tool_name="chatgpt-web",
            model="gpt-4o",
            input_tokens=2000,
            output_tokens=800,
            prompt_text=None,
            response_text=None,
        )

    def test_invalid_json(self):
        """Invalid JSON returns 400."""
        with self.app.test_client() as client:
            resp = client.post(
                "/api/tokens",
                data="not json",
                content_type="application/json",
            )

        assert resp.status_code == 400

    def test_empty_events(self):
        """Empty events list returns success with 0 processed."""
        with self.app.test_client() as client:
            resp = client.post(
                "/api/tokens",
                data=json.dumps({"events": []}),
                content_type="application/json",
            )

        assert resp.status_code == 200
        assert resp.get_json()["processed"] == 0

    def test_health_endpoint(self):
        """Health endpoint still works."""
        with self.app.test_client() as client:
            resp = client.get("/health")

        assert resp.status_code == 200
        assert resp.get_json()["status"] == "healthy"
