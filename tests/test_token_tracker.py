"""Tests for the token tracker module."""

import json
import sqlite3
import tempfile
from pathlib import Path
from unittest import mock
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

    def test_cache_creation_tokens_add_125x_input_cost(self):
        """Cache creation tokens cost 1.25x the input price."""
        # claude-sonnet-4-5: $3/M input, $15/M output
        cost = estimate_cost(
            "claude-sonnet-4-5",
            input_tokens=1_000_000,
            output_tokens=0,
            cache_creation_input_tokens=1_000_000,
        )
        # input cost = $3.0 + cache creation = $3.0 * 1.25 = $3.75
        expected = 3.0 + 3.0 * 1.25
        assert abs(cost - expected) < 1e-10

    def test_cache_read_tokens_add_01x_input_cost(self):
        """Cache read tokens cost 0.1x the input price."""
        # claude-sonnet-4-5: $3/M input, $15/M output
        cost = estimate_cost(
            "claude-sonnet-4-5",
            input_tokens=0,
            output_tokens=0,
            cache_read_input_tokens=1_000_000,
        )
        # cache read = $3.0 * 0.1 = $0.30
        expected = 3.0 * 0.1
        assert abs(cost - expected) < 1e-10

    def test_cache_tokens_default_to_zero(self):
        """When cache tokens not provided, cost is unchanged."""
        cost_without = estimate_cost("claude-sonnet-4-5", 1_000_000, 1_000_000)
        cost_with_zero = estimate_cost(
            "claude-sonnet-4-5", 1_000_000, 1_000_000,
            cache_creation_input_tokens=0, cache_read_input_tokens=0,
        )
        assert cost_without == cost_with_zero

    def test_cost_with_all_token_types(self):
        """Full cost calculation with input, output, cache creation, and cache read."""
        # claude-sonnet-4-5: $3/M input, $15/M output
        cost = estimate_cost(
            "claude-sonnet-4-5",
            input_tokens=500_000,
            output_tokens=200_000,
            cache_creation_input_tokens=100_000,
            cache_read_input_tokens=300_000,
        )
        input_price = 3.0
        output_price = 15.0
        expected = (
            (500_000 / 1_000_000) * input_price
            + (200_000 / 1_000_000) * output_price
            + (100_000 / 1_000_000) * input_price * 1.25
            + (300_000 / 1_000_000) * input_price * 0.1
        )
        assert abs(cost - expected) < 1e-10


class TestTokenTrackerCacheCostInScan:
    def test_scan_emits_cost_including_cache_tokens(self, tmp_path):
        """When JSONL has cache tokens, cost metric includes their cost."""
        project_dir = tmp_path / ".claude" / "projects" / "test-project"
        project_dir.mkdir(parents=True)

        entry = {
            "role": "assistant",
            "model": "claude-sonnet-4-5",
            "usage": {
                "input_tokens": 1_000_000,
                "output_tokens": 0,
                "cache_creation_input_tokens": 1_000_000,
                "cache_read_input_tokens": 1_000_000,
            },
        }
        jsonl_file = project_dir / "session-cache.jsonl"
        jsonl_file.write_text(json.dumps(entry) + "\n")

        config = AppConfig()
        config.token_tracking = {}
        telemetry = MagicMock()
        telemetry.tokens_input_total = MagicMock()
        telemetry.tokens_output_total = MagicMock()
        telemetry.tokens_cost_usd_total = MagicMock()
        telemetry.prompt_count_total = MagicMock()

        tracker = TokenTracker(config, telemetry)

        with mock.patch(
            "ai_cost_observer.detectors.token_tracker.Path.home",
            return_value=tmp_path,
        ):
            tracker.scan()

        # Cost should include cache tokens
        # input: $3.0, cache_creation: $3.0 * 1.25 = $3.75, cache_read: $3.0 * 0.1 = $0.30
        expected_cost = 3.0 + 3.0 * 1.25 + 3.0 * 0.1
        actual_cost = telemetry.tokens_cost_usd_total.add.call_args[0][0]
        assert abs(actual_cost - expected_cost) < 1e-10

    def test_scan_handles_missing_cache_fields(self, tmp_path):
        """When JSONL entry has no cache fields, cost is computed without them."""
        project_dir = tmp_path / ".claude" / "projects" / "test-project"
        project_dir.mkdir(parents=True)

        entry = {
            "role": "assistant",
            "model": "claude-sonnet-4-5",
            "usage": {
                "input_tokens": 1_000_000,
                "output_tokens": 1_000_000,
                # No cache fields at all
            },
        }
        jsonl_file = project_dir / "session-nocache.jsonl"
        jsonl_file.write_text(json.dumps(entry) + "\n")

        config = AppConfig()
        config.token_tracking = {}
        telemetry = MagicMock()
        telemetry.tokens_input_total = MagicMock()
        telemetry.tokens_output_total = MagicMock()
        telemetry.tokens_cost_usd_total = MagicMock()
        telemetry.prompt_count_total = MagicMock()

        tracker = TokenTracker(config, telemetry)

        with mock.patch(
            "ai_cost_observer.detectors.token_tracker.Path.home",
            return_value=tmp_path,
        ):
            tracker.scan()

        # Cost should just be input + output: $3.0 + $15.0 = $18.0
        expected_cost = 3.0 + 15.0
        actual_cost = telemetry.tokens_cost_usd_total.add.call_args[0][0]
        assert abs(actual_cost - expected_cost) < 1e-10


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
        with mock.patch("ai_cost_observer.detectors.token_tracker.Path.home", return_value=tmp_path):
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

        with mock.patch("ai_cost_observer.detectors.token_tracker.Path.home", return_value=tmp_path):
            tracker.scan()

        assert telemetry.tokens_input_total.add.call_count == 1

        # Second scan with no new data
        telemetry.reset_mock()
        with mock.patch("ai_cost_observer.detectors.token_tracker.Path.home", return_value=tmp_path):
            tracker.scan()

        telemetry.tokens_input_total.add.assert_not_called()

        # Add new data
        entry2 = {"role": "assistant", "model": "gpt-4o",
                   "usage": {"input_tokens": 200, "output_tokens": 100}}
        with open(jsonl_file, "a") as f:
            f.write(json.dumps(entry2) + "\n")

        telemetry.reset_mock()
        with mock.patch("ai_cost_observer.detectors.token_tracker.Path.home", return_value=tmp_path):
            tracker.scan()

        assert telemetry.tokens_input_total.add.call_count == 1


class TestTokenTrackerOffsetPersistence:
    def test_offsets_persist_across_restarts(self, tmp_path):
        """File offsets survive tracker restart (new instance)."""
        project_dir = tmp_path / ".claude" / "projects" / "test-project"
        project_dir.mkdir(parents=True)
        state_dir = tmp_path / "state"
        state_dir.mkdir(parents=True)

        entry1 = {"role": "assistant", "model": "claude-sonnet-4-5",
                   "usage": {"input_tokens": 100, "output_tokens": 50}}
        jsonl_file = project_dir / "session-persist.jsonl"
        jsonl_file.write_text(json.dumps(entry1) + "\n")

        config = AppConfig()
        config.token_tracking = {}
        config.state_dir = state_dir
        telemetry = MagicMock()
        telemetry.tokens_input_total = MagicMock()
        telemetry.tokens_output_total = MagicMock()
        telemetry.tokens_cost_usd_total = MagicMock()
        telemetry.prompt_count_total = MagicMock()


        # First tracker instance: scan once
        tracker1 = TokenTracker(config, telemetry)
        with mock.patch(
            "ai_cost_observer.detectors.token_tracker.Path.home",
            return_value=tmp_path,
        ):
            tracker1.scan()

        assert telemetry.tokens_input_total.add.call_count == 1

        # Simulate restart: create a NEW tracker instance
        telemetry.reset_mock()
        tracker2 = TokenTracker(config, telemetry)
        with mock.patch(
            "ai_cost_observer.detectors.token_tracker.Path.home",
            return_value=tmp_path,
        ):
            tracker2.scan()

        # Should NOT re-process old data
        telemetry.tokens_input_total.add.assert_not_called()

    def test_offsets_state_file_created(self, tmp_path):
        """Scanning creates a state file in state_dir."""
        project_dir = tmp_path / ".claude" / "projects" / "test-project"
        project_dir.mkdir(parents=True)
        state_dir = tmp_path / "state"
        state_dir.mkdir(parents=True)

        entry = {"role": "assistant", "model": "gpt-4o",
                 "usage": {"input_tokens": 50, "output_tokens": 25}}
        jsonl_file = project_dir / "session-state.jsonl"
        jsonl_file.write_text(json.dumps(entry) + "\n")

        config = AppConfig()
        config.token_tracking = {}
        config.state_dir = state_dir
        telemetry = MagicMock()
        telemetry.tokens_input_total = MagicMock()
        telemetry.tokens_output_total = MagicMock()
        telemetry.tokens_cost_usd_total = MagicMock()
        telemetry.prompt_count_total = MagicMock()

        tracker = TokenTracker(config, telemetry)

        with mock.patch(
            "ai_cost_observer.detectors.token_tracker.Path.home",
            return_value=tmp_path,
        ):
            tracker.scan()

        state_file = state_dir / "token_tracker_state.json"
        assert state_file.exists()
        data = json.loads(state_file.read_text())
        assert "file_offsets" in data

    def test_new_data_after_restart_is_processed(self, tmp_path):
        """After restart, new data appended to JSONL is still processed."""
        project_dir = tmp_path / ".claude" / "projects" / "test-project"
        project_dir.mkdir(parents=True)
        state_dir = tmp_path / "state"
        state_dir.mkdir(parents=True)

        entry1 = {"role": "assistant", "model": "claude-sonnet-4-5",
                   "usage": {"input_tokens": 100, "output_tokens": 50}}
        jsonl_file = project_dir / "session-new.jsonl"
        jsonl_file.write_text(json.dumps(entry1) + "\n")

        config = AppConfig()
        config.token_tracking = {}
        config.state_dir = state_dir
        telemetry = MagicMock()
        telemetry.tokens_input_total = MagicMock()
        telemetry.tokens_output_total = MagicMock()
        telemetry.tokens_cost_usd_total = MagicMock()
        telemetry.prompt_count_total = MagicMock()


        # First instance: scan
        tracker1 = TokenTracker(config, telemetry)
        with mock.patch(
            "ai_cost_observer.detectors.token_tracker.Path.home",
            return_value=tmp_path,
        ):
            tracker1.scan()

        assert telemetry.tokens_input_total.add.call_count == 1

        # Append new data
        entry2 = {"role": "assistant", "model": "gpt-4o",
                   "usage": {"input_tokens": 200, "output_tokens": 100}}
        with open(jsonl_file, "a") as f:
            f.write(json.dumps(entry2) + "\n")

        # Simulate restart
        telemetry.reset_mock()
        tracker2 = TokenTracker(config, telemetry)
        with mock.patch(
            "ai_cost_observer.detectors.token_tracker.Path.home",
            return_value=tmp_path,
        ):
            tracker2.scan()

        # Should only process the NEW entry
        assert telemetry.tokens_input_total.add.call_count == 1
        telemetry.tokens_input_total.add.assert_called_once_with(
            200, {"tool.name": "claude-code", "model.name": "gpt-4o"}
        )


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


def _create_codex_db(db_path, rows):
    """Helper: create a Codex-style SQLite database with sessions table."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE sessions ("
        "  id TEXT PRIMARY KEY,"
        "  model TEXT,"
        "  input_tokens INTEGER,"
        "  output_tokens INTEGER"
        ")"
    )
    for row in rows:
        conn.execute(
            "INSERT INTO sessions (id, model, input_tokens, output_tokens) VALUES (?, ?, ?, ?)",
            row,
        )
    conn.commit()
    conn.close()


class TestCodexScannerIncremental:
    def test_codex_does_not_reprocess_rows(self, tmp_path):
        """Codex scanner should not re-process rows on the second scan cycle."""
        codex_db = tmp_path / ".codex" / "sqlite" / "codex-dev.db"
        state_dir = tmp_path / "state"
        state_dir.mkdir(parents=True)

        _create_codex_db(codex_db, [
            ("sess-1", "o3-mini", 500, 200),
        ])

        config = AppConfig()
        config.token_tracking = {}
        config.state_dir = state_dir
        telemetry = MagicMock()
        telemetry.tokens_input_total = MagicMock()
        telemetry.tokens_output_total = MagicMock()
        telemetry.tokens_cost_usd_total = MagicMock()
        telemetry.prompt_count_total = MagicMock()

        tracker = TokenTracker(config, telemetry)

        with mock.patch(
            "ai_cost_observer.detectors.token_tracker.Path.home",
            return_value=tmp_path,
        ):
            tracker.scan()

        assert telemetry.tokens_input_total.add.call_count == 1

        # Second scan with no new data: should NOT re-count
        telemetry.reset_mock()
        with mock.patch(
            "ai_cost_observer.detectors.token_tracker.Path.home",
            return_value=tmp_path,
        ):
            tracker.scan()

        telemetry.tokens_input_total.add.assert_not_called()

    def test_codex_processes_only_new_rows(self, tmp_path):
        """After initial scan, only newly inserted rows are processed."""
        codex_db = tmp_path / ".codex" / "sqlite" / "codex-dev.db"
        state_dir = tmp_path / "state"
        state_dir.mkdir(parents=True)

        _create_codex_db(codex_db, [
            ("sess-1", "o3-mini", 500, 200),
        ])

        config = AppConfig()
        config.token_tracking = {}
        config.state_dir = state_dir
        telemetry = MagicMock()
        telemetry.tokens_input_total = MagicMock()
        telemetry.tokens_output_total = MagicMock()
        telemetry.tokens_cost_usd_total = MagicMock()
        telemetry.prompt_count_total = MagicMock()

        tracker = TokenTracker(config, telemetry)

        with mock.patch(
            "ai_cost_observer.detectors.token_tracker.Path.home",
            return_value=tmp_path,
        ):
            tracker.scan()

        assert telemetry.tokens_input_total.add.call_count == 1

        # Insert new row
        conn = sqlite3.connect(str(codex_db))
        conn.execute(
            "INSERT INTO sessions (id, model, input_tokens, output_tokens) VALUES (?, ?, ?, ?)",
            ("sess-2", "gpt-4o", 300, 150),
        )
        conn.commit()
        conn.close()

        telemetry.reset_mock()
        with mock.patch(
            "ai_cost_observer.detectors.token_tracker.Path.home",
            return_value=tmp_path,
        ):
            tracker.scan()

        # Only the new row should be processed
        assert telemetry.tokens_input_total.add.call_count == 1
        telemetry.tokens_input_total.add.assert_called_once_with(
            300, {"tool.name": "codex-cli", "model.name": "gpt-4o"}
        )

    def test_codex_rowid_persists_across_restarts(self, tmp_path):
        """Codex last_rowid survives restarts via state file."""
        codex_db = tmp_path / ".codex" / "sqlite" / "codex-dev.db"
        state_dir = tmp_path / "state"
        state_dir.mkdir(parents=True)

        _create_codex_db(codex_db, [
            ("sess-1", "o3-mini", 500, 200),
        ])

        config = AppConfig()
        config.token_tracking = {}
        config.state_dir = state_dir
        telemetry = MagicMock()
        telemetry.tokens_input_total = MagicMock()
        telemetry.tokens_output_total = MagicMock()
        telemetry.tokens_cost_usd_total = MagicMock()
        telemetry.prompt_count_total = MagicMock()


        # First tracker instance
        tracker1 = TokenTracker(config, telemetry)
        with mock.patch(
            "ai_cost_observer.detectors.token_tracker.Path.home",
            return_value=tmp_path,
        ):
            tracker1.scan()

        assert telemetry.tokens_input_total.add.call_count == 1

        # Simulate restart: new tracker instance
        telemetry.reset_mock()
        tracker2 = TokenTracker(config, telemetry)
        with mock.patch(
            "ai_cost_observer.detectors.token_tracker.Path.home",
            return_value=tmp_path,
        ):
            tracker2.scan()

        # Should NOT re-process
        telemetry.tokens_input_total.add.assert_not_called()
