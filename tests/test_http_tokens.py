"""Tests for the HTTP receiver /api/tokens endpoint."""

import json
from unittest.mock import MagicMock

from ai_cost_observer.config import AppConfig
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

    def test_receive_token_event_without_tracker(self):
        """Without a token tracker, metrics are recorded directly."""
        config = AppConfig()
        config.ai_domains = []
        telemetry = _make_telemetry()
        app = create_app(config, telemetry)

        with app.test_client() as client:
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

        telemetry.tokens_input_total.add.assert_called_once_with(
            1000, {"tool.name": "claude-web", "model.name": "claude-sonnet-4-5"}
        )
        telemetry.tokens_output_total.add.assert_called_once_with(
            500, {"tool.name": "claude-web", "model.name": "claude-sonnet-4-5"}
        )

    def test_receive_token_event_with_tracker(self):
        """With a token tracker, events are forwarded to it."""
        config = AppConfig()
        config.ai_domains = []
        telemetry = _make_telemetry()

        tracker = MagicMock()
        http_receiver.set_token_tracker(tracker)

        app = create_app(config, telemetry)

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
        config = AppConfig()
        config.ai_domains = []
        telemetry = _make_telemetry()
        app = create_app(config, telemetry)

        with app.test_client() as client:
            resp = client.post(
                "/api/tokens",
                data="not json",
                content_type="application/json",
            )

        assert resp.status_code == 400

    def test_empty_events(self):
        """Empty events list returns success with 0 processed."""
        config = AppConfig()
        config.ai_domains = []
        telemetry = _make_telemetry()
        app = create_app(config, telemetry)

        with app.test_client() as client:
            resp = client.post(
                "/api/tokens",
                data=json.dumps({"events": []}),
                content_type="application/json",
            )

        assert resp.status_code == 200
        assert resp.get_json()["processed"] == 0

    def test_health_endpoint(self):
        """Health endpoint still works."""
        config = AppConfig()
        config.ai_domains = []
        telemetry = _make_telemetry()
        app = create_app(config, telemetry)

        with app.test_client() as client:
            resp = client.get("/health")

        assert resp.status_code == 200
        assert resp.get_json()["status"] == "healthy"
