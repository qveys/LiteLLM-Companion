"""Tests for the token tracker module."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from ai_cost_observer.config import AppConfig
from ai_cost_observer.detectors.token_tracker import TokenTracker, estimate_cost


class TestEstimateCost:
    def test_known_model(self):
        cost = estimate_cost("claude-sonnet-4-5", 1_000_000, 1_000_000)
        assert cost == 3.0 + 15.0  # $3/M input + $15/M output

    def test_prefix_match(self):
        cost = estimate_cost("claude-opus-4-20250101", 1_000_000, 0)
        assert cost == 15.0  # Matches claude-opus-4

    def test_unknown_model_uses_fallback(self):
        cost = estimate_cost("unknown-model-xyz", 1_000_000, 1_000_000)
        assert cost == 3.0 + 15.0  # Fallback: $3 + $15

    def test_zero_tokens(self):
        cost = estimate_cost("gpt-4o", 0, 0)
        assert cost == 0.0

    def test_small_token_count(self):
        cost = estimate_cost("gpt-4o-mini", 1000, 500)
        # $0.15/M input, $0.60/M output
        expected = (1000 / 1_000_000) * 0.15 + (500 / 1_000_000) * 0.60
        assert abs(cost - expected) < 1e-10


class TestTokenTrackerClaudeCode:
    def test_scan_claude_jsonl(self, tmp_path):
        """Token tracker reads Claude Code JSONL files and emits metrics."""
        # Create a fake Claude Code project directory
        project_dir = tmp_path / ".claude" / "projects" / "test-project"
        project_dir.mkdir(parents=True)

        jsonl_file = project_dir / "session-123.jsonl"
        entries = [
            {
                "role": "assistant",
                "model": "claude-sonnet-4-5",
                "usage": {
                    "input_tokens": 500,
                    "output_tokens": 200,
                    "cache_creation_input_tokens": 0,
                    "cache_read_input_tokens": 100,
                },
                "content": [{"type": "text", "text": "Hello!"}],
            },
            {
                "role": "user",
                "content": "What is Python?",
            },
        ]
        jsonl_file.write_text("\n".join(json.dumps(e) for e in entries))

        config = AppConfig()
        config.token_tracking = {"capture_prompt_text": True, "capture_response_text": True}
        telemetry = MagicMock()
        telemetry.tokens_input_total = MagicMock()
        telemetry.tokens_output_total = MagicMock()
        telemetry.tokens_cost_usd_total = MagicMock()
        telemetry.prompt_count_total = MagicMock()

        tracker = TokenTracker(config, telemetry)

        # Patch home to use tmp_path
        import unittest.mock
        with unittest.mock.patch("ai_cost_observer.detectors.token_tracker.Path.home", return_value=tmp_path):
            tracker.scan()

        # Should have recorded metrics for the entry with usage data
        telemetry.tokens_input_total.add.assert_called_once_with(
            500, {"tool.name": "claude-code", "model.name": "claude-sonnet-4-5"}
        )
        telemetry.tokens_output_total.add.assert_called_once_with(
            200, {"tool.name": "claude-code", "model.name": "claude-sonnet-4-5"}
        )

    def test_incremental_reading(self, tmp_path):
        """Token tracker only reads new data on subsequent scans."""
        project_dir = tmp_path / ".claude" / "projects" / "test-project"
        project_dir.mkdir(parents=True)
        jsonl_file = project_dir / "session-456.jsonl"

        entry1 = {"role": "assistant", "model": "claude-sonnet-4-5",
                   "usage": {"input_tokens": 100, "output_tokens": 50}}
        jsonl_file.write_text(json.dumps(entry1) + "\n")

        config = AppConfig()
        config.token_tracking = {}
        telemetry = MagicMock()
        telemetry.tokens_input_total = MagicMock()
        telemetry.tokens_output_total = MagicMock()
        telemetry.tokens_cost_usd_total = MagicMock()
        telemetry.prompt_count_total = MagicMock()

        tracker = TokenTracker(config, telemetry)

        import unittest.mock
        with unittest.mock.patch("ai_cost_observer.detectors.token_tracker.Path.home", return_value=tmp_path):
            tracker.scan()

        assert telemetry.tokens_input_total.add.call_count == 1

        # Second scan with no new data
        telemetry.reset_mock()
        with unittest.mock.patch("ai_cost_observer.detectors.token_tracker.Path.home", return_value=tmp_path):
            tracker.scan()

        telemetry.tokens_input_total.add.assert_not_called()

        # Add new data
        entry2 = {"role": "assistant", "model": "gpt-4o",
                   "usage": {"input_tokens": 200, "output_tokens": 100}}
        with open(jsonl_file, "a") as f:
            f.write(json.dumps(entry2) + "\n")

        telemetry.reset_mock()
        with unittest.mock.patch("ai_cost_observer.detectors.token_tracker.Path.home", return_value=tmp_path):
            tracker.scan()

        assert telemetry.tokens_input_total.add.call_count == 1


class TestTokenTrackerApiIntercept:
    def test_record_api_intercept(self):
        """record_api_intercept emits correct OTel metrics."""
        config = AppConfig()
        config.token_tracking = {}
        telemetry = MagicMock()
        telemetry.tokens_input_total = MagicMock()
        telemetry.tokens_output_total = MagicMock()
        telemetry.tokens_cost_usd_total = MagicMock()
        telemetry.prompt_count_total = MagicMock()

        tracker = TokenTracker(config, telemetry)
        tracker.record_api_intercept(
            tool_name="claude-web",
            model="claude-sonnet-4-5",
            input_tokens=1000,
            output_tokens=500,
        )

        telemetry.tokens_input_total.add.assert_called_once_with(
            1000, {"tool.name": "claude-web", "model.name": "claude-sonnet-4-5"}
        )
        telemetry.tokens_output_total.add.assert_called_once_with(
            500, {"tool.name": "claude-web", "model.name": "claude-sonnet-4-5"}
        )
        telemetry.prompt_count_total.add.assert_called_once()
