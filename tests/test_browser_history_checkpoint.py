"""Regression tests for browser history scan checkpoint behavior."""

from __future__ import annotations

from pathlib import Path

from ai_cost_observer.config import AppConfig
from ai_cost_observer.detectors.browser_history import BrowserHistoryParser


class _DummyTelemetry:
    pass


def test_checkpoint_advances_only_after_successful_scan(tmp_path: Path) -> None:
    parser = BrowserHistoryParser(AppConfig(ai_domains=[]), _DummyTelemetry())

    calls: list[float] = []
    should_fail = {"value": True}

    def flaky_parser(_db_path: Path, since: float):
        calls.append(since)
        if should_fail["value"]:
            should_fail["value"] = False
            raise RuntimeError("transient sqlite error")
        return []

    parser._get_browsers = lambda: [("chrome", tmp_path / "History", flaky_parser)]  # type: ignore[method-assign]

    parser.scan()
    assert "chrome" not in parser._last_scan_time

    parser.scan()
    assert "chrome" in parser._last_scan_time

    # The failed scan must not advance the checkpoint.
    assert calls[1] == calls[0]
