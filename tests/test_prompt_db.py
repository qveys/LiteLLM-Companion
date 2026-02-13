"""Tests for the prompt database storage module."""

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from ai_cost_observer.storage.prompt_db import PromptDB


class TestPromptDB:
    def test_create_db(self, tmp_path):
        """DB is created with correct schema."""
        db_path = tmp_path / "test.db"
        PromptDB(db_path=db_path, encrypt=False)

        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = {row[0] for row in cursor}
        conn.close()

        assert "prompts" in tables
        assert "sessions" in tables
        assert "schema_version" in tables

    def test_insert_and_retrieve(self, tmp_path):
        """Insert a prompt and retrieve it."""
        db = PromptDB(db_path=tmp_path / "test.db", encrypt=False)

        row_id = db.insert_prompt(
            tool_name="claude-code",
            source="cli",
            model_name="claude-sonnet-4-5",
            input_tokens=500,
            output_tokens=200,
            estimated_cost_usd=0.0045,
            prompt_text="Hello world",
            response_text="Hi there!",
        )

        assert row_id == 1

        prompts = db.get_prompts()
        assert len(prompts) == 1
        assert prompts[0]["tool_name"] == "claude-code"
        assert prompts[0]["input_tokens"] == 500
        assert prompts[0]["prompt_text"] == "Hello world"
        assert prompts[0]["response_text"] == "Hi there!"

    def test_filter_by_tool_name(self, tmp_path):
        """get_prompts filters by tool_name."""
        db = PromptDB(db_path=tmp_path / "test.db", encrypt=False)

        db.insert_prompt(tool_name="claude-code", source="cli", input_tokens=100)
        db.insert_prompt(tool_name="chatgpt-web", source="browser", input_tokens=200)
        db.insert_prompt(tool_name="claude-code", source="cli", input_tokens=300)

        results = db.get_prompts(tool_name="claude-code")
        assert len(results) == 2
        assert all(r["tool_name"] == "claude-code" for r in results)

    def test_encryption(self, tmp_path):
        """Encrypted text is stored encrypted and decrypted on read."""
        db = PromptDB(db_path=tmp_path / "test.db", encrypt=True)

        if db._fernet is None:
            pytest.skip("cryptography not installed")

        db.insert_prompt(
            tool_name="test",
            source="test",
            prompt_text="secret prompt",
            response_text="secret response",
        )

        # Read raw from SQLite — should be encrypted
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        row = conn.execute("SELECT prompt_text, response_text FROM prompts LIMIT 1").fetchone()
        conn.close()

        assert row[0] != "secret prompt"  # Encrypted
        assert row[1] != "secret response"  # Encrypted

        # Read via API — should be decrypted
        prompts = db.get_prompts()
        assert prompts[0]["prompt_text"] == "secret prompt"
        assert prompts[0]["response_text"] == "secret response"

    def test_get_stats(self, tmp_path):
        """get_stats returns correct aggregates."""
        db = PromptDB(db_path=tmp_path / "test.db", encrypt=False)

        db.insert_prompt(
            tool_name="a", source="cli", input_tokens=100, output_tokens=50, estimated_cost_usd=0.01
        )
        db.insert_prompt(
            tool_name="b",
            source="cli",
            input_tokens=200,
            output_tokens=100,
            estimated_cost_usd=0.02,
        )

        stats = db.get_stats()
        assert stats["total_prompts"] == 2
        assert stats["total_input_tokens"] == 300
        assert stats["total_output_tokens"] == 150
        assert abs(stats["total_cost_usd"] - 0.03) < 1e-10

    def test_cleanup_retention(self, tmp_path):
        """cleanup removes old prompts."""
        db = PromptDB(db_path=tmp_path / "test.db", encrypt=False, retention_days=1)

        # Insert an old prompt
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        old_time = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
        conn.execute(
            "INSERT INTO prompts (timestamp, tool_name, source, input_tokens) VALUES (?, ?, ?, ?)",
            (old_time, "old-tool", "cli", 100),
        )
        conn.commit()
        conn.close()

        # Insert a recent prompt
        db.insert_prompt(tool_name="new-tool", source="cli", input_tokens=200)

        deleted = db.cleanup()
        assert deleted == 1

        remaining = db.get_prompts()
        assert len(remaining) == 1
        assert remaining[0]["tool_name"] == "new-tool"

    def test_upsert_session(self, tmp_path):
        """upsert_session creates and updates sessions."""
        db = PromptDB(db_path=tmp_path / "test.db", encrypt=False)

        db.upsert_session(
            session_id="sess-1",
            tool_name="claude-code",
            total_input_tokens=1000,
            total_output_tokens=500,
            total_cost_usd=0.05,
        )

        conn = sqlite3.connect(str(tmp_path / "test.db"))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM sessions WHERE id = 'sess-1'").fetchone()
        conn.close()

        assert row["tool_name"] == "claude-code"
        assert row["total_input_tokens"] == 1000

        # Update
        db.upsert_session(
            session_id="sess-1",
            tool_name="claude-code",
            total_input_tokens=2000,
            total_output_tokens=1000,
            total_cost_usd=0.10,
        )

        conn = sqlite3.connect(str(tmp_path / "test.db"))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM sessions WHERE id = 'sess-1'").fetchone()
        conn.close()

        assert row["total_input_tokens"] == 2000

    def test_null_text_fields(self, tmp_path):
        """Insert with None text fields works fine."""
        db = PromptDB(db_path=tmp_path / "test.db", encrypt=False)

        db.insert_prompt(tool_name="test", source="cli", prompt_text=None, response_text=None)

        prompts = db.get_prompts()
        assert prompts[0]["prompt_text"] is None
        assert prompts[0]["response_text"] is None
