"""Evaluation tests: extension payload -> telemetry values."""

from __future__ import annotations

from ai_cost_observer.config import AppConfig
from ai_cost_observer.server.http_receiver import create_app


class _Recorder:
    def __init__(self) -> None:
        self.calls: list[tuple[float, dict[str, str]]] = []

    def add(self, value: float, labels: dict[str, str]) -> None:
        self.calls.append((value, labels.copy()))


class _DummyTelemetry:
    def __init__(self) -> None:
        self.browser_domain_active_duration = _Recorder()
        self.browser_domain_visit_count = _Recorder()
        self.browser_domain_estimated_cost = _Recorder()


def _build_test_app():
    config = AppConfig(
        ai_domains=[
            {"domain": "chatgpt.com", "category": "chat", "cost_per_hour": 0.5},
            {"domain": "claude.ai", "category": "chat", "cost_per_hour": 0.6},
        ]
    )
    telemetry = _DummyTelemetry()
    app = create_app(config, telemetry)
    app.config["TESTING"] = True
    return app, telemetry


def test_receiver_reports_expected_duration_visit_and_cost_values() -> None:
    app, telemetry = _build_test_app()
    client = app.test_client()

    response = client.post(
        "/metrics/browser",
        json={
            "events": [
                {
                    "domain": "chatgpt.com",
                    "duration_seconds": 1800,
                    "visit_count": 3,
                    "browser": "chrome",
                }
            ]
        },
    )

    assert response.status_code == 200
    assert telemetry.browser_domain_active_duration.calls == [
        (
            1800,
            {
                "ai.domain": "chatgpt.com",
                "ai.category": "chat",
                "browser.name": "chrome",
                "usage.source": "extension",
            },
        )
    ]
    assert telemetry.browser_domain_visit_count.calls == [
        (
            3,
            {
                "ai.domain": "chatgpt.com",
                "ai.category": "chat",
                "browser.name": "chrome",
                "usage.source": "extension",
            },
        )
    ]
    assert len(telemetry.browser_domain_estimated_cost.calls) == 1
    reported_cost, labels = telemetry.browser_domain_estimated_cost.calls[0]
    assert reported_cost == 0.25
    assert labels == {
        "ai.domain": "chatgpt.com",
        "ai.category": "chat",
    }


def test_receiver_ignores_unknown_domains() -> None:
    app, telemetry = _build_test_app()
    client = app.test_client()

    response = client.post(
        "/metrics/browser",
        json={
            "events": [
                {
                    "domain": "unknown.example",
                    "duration_seconds": 900,
                    "visit_count": 1,
                    "browser": "chrome",
                }
            ]
        },
    )

    assert response.status_code == 200
    assert telemetry.browser_domain_active_duration.calls == []
    assert telemetry.browser_domain_visit_count.calls == []
    assert telemetry.browser_domain_estimated_cost.calls == []
