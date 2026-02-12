"""SQLite prompt storage — stores prompts/responses with optional Fernet encryption."""

from __future__ import annotations

import base64
import hashlib
import os
import platform
import socket
import sqlite3
import time
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path

from loguru import logger

_SCHEMA_VERSION = 1

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS prompts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    model_name TEXT,
    source TEXT NOT NULL,
    session_id TEXT,
    input_tokens INTEGER,
    output_tokens INTEGER,
    cache_creation_tokens INTEGER,
    cache_read_tokens INTEGER,
    estimated_cost_usd REAL,
    prompt_text TEXT,
    response_text TEXT,
    project_path TEXT,
    host_name TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    tool_name TEXT NOT NULL,
    start_time TEXT,
    end_time TEXT,
    total_input_tokens INTEGER DEFAULT 0,
    total_output_tokens INTEGER DEFAULT 0,
    total_cost_usd REAL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_prompts_timestamp ON prompts(timestamp);
CREATE INDEX IF NOT EXISTS idx_prompts_tool ON prompts(tool_name);
CREATE INDEX IF NOT EXISTS idx_prompts_session ON prompts(session_id);

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);
"""


def _default_db_path() -> Path:
    if platform.system() == "Windows":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "ai-cost-observer" / "prompts.db"
    return Path.home() / ".local" / "state" / "ai-cost-observer" / "prompts.db"


def _derive_key(password: str) -> bytes:
    """Derive a Fernet-compatible 32-byte key from a password string."""
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), b"ai-cost-observer", 100_000)
    return base64.urlsafe_b64encode(dk)


class PromptDB:
    """Thread-safe SQLite database for prompt/response storage with optional encryption."""

    def __init__(
        self,
        db_path: Path | str | None = None,
        encrypt: bool = True,
        retention_days: int = 90,
    ) -> None:
        self.db_path = Path(db_path) if db_path else _default_db_path()
        self.encrypt = encrypt
        self.retention_days = retention_days
        self._lock = threading.Lock()
        self._fernet = None
        self._host_name = socket.gethostname()

        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize encryption
        if self.encrypt:
            self._init_encryption()

        # Initialize database
        self._init_db()

    def _init_encryption(self) -> None:
        """Initialize Fernet encryption with a derived key."""
        try:
            from cryptography.fernet import Fernet

            # Derive key from hostname + username (stable across restarts)
            identity = f"{socket.gethostname()}:{os.getlogin()}"
            key = _derive_key(identity)
            self._fernet = Fernet(key)
            logger.debug("Prompt encryption initialized")
        except ImportError:
            logger.warning(
                "cryptography package not installed — prompt text will be stored in plaintext. "
                "Install with: pip install cryptography"
            )
            self.encrypt = False
        except Exception:
            logger.opt(exception=True).warning("Failed to initialize encryption — falling back to plaintext")
            self.encrypt = False

    def _init_db(self) -> None:
        """Create tables if they don't exist."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                conn.executescript(_SCHEMA_SQL)

                # Set schema version
                cursor = conn.execute("SELECT version FROM schema_version LIMIT 1")
                row = cursor.fetchone()
                if not row:
                    conn.execute(
                        "INSERT INTO schema_version (version) VALUES (?)",
                        (_SCHEMA_VERSION,),
                    )
                conn.commit()
            finally:
                conn.close()

        logger.debug("PromptDB initialized at {}", self.db_path)

    def _encrypt_text(self, text: str | None) -> str | None:
        """Encrypt text if encryption is enabled."""
        if text is None:
            return None
        if self._fernet:
            return self._fernet.encrypt(text.encode("utf-8")).decode("ascii")
        return text

    def _decrypt_text(self, text: str | None) -> str | None:
        """Decrypt text if encryption is enabled."""
        if text is None:
            return None
        if self._fernet:
            try:
                return self._fernet.decrypt(text.encode("ascii")).decode("utf-8")
            except Exception:
                logger.debug("Failed to decrypt text — returning as-is")
                return text
        return text

    def insert_prompt(
        self,
        tool_name: str,
        source: str,
        model_name: str | None = None,
        session_id: str | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        cache_creation_tokens: int | None = None,
        cache_read_tokens: int | None = None,
        estimated_cost_usd: float | None = None,
        prompt_text: str | None = None,
        response_text: str | None = None,
        project_path: str | None = None,
    ) -> int:
        """Insert a prompt record. Returns the row ID."""
        now = datetime.now(timezone.utc).isoformat()

        # Encrypt sensitive text fields
        enc_prompt = self._encrypt_text(prompt_text)
        enc_response = self._encrypt_text(response_text)

        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.execute(
                    """INSERT INTO prompts (
                        timestamp, tool_name, model_name, source, session_id,
                        input_tokens, output_tokens, cache_creation_tokens, cache_read_tokens,
                        estimated_cost_usd, prompt_text, response_text,
                        project_path, host_name
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        now, tool_name, model_name, source, session_id,
                        input_tokens, output_tokens, cache_creation_tokens, cache_read_tokens,
                        estimated_cost_usd, enc_prompt, enc_response,
                        project_path, self._host_name,
                    ),
                )
                conn.commit()
                return cursor.lastrowid
            finally:
                conn.close()

    def upsert_session(
        self,
        session_id: str,
        tool_name: str,
        start_time: str | None = None,
        end_time: str | None = None,
        total_input_tokens: int = 0,
        total_output_tokens: int = 0,
        total_cost_usd: float = 0,
    ) -> None:
        """Insert or update a session record."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                conn.execute(
                    """INSERT INTO sessions (id, tool_name, start_time, end_time,
                        total_input_tokens, total_output_tokens, total_cost_usd)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        end_time = excluded.end_time,
                        total_input_tokens = excluded.total_input_tokens,
                        total_output_tokens = excluded.total_output_tokens,
                        total_cost_usd = excluded.total_cost_usd""",
                    (session_id, tool_name, start_time, end_time,
                     total_input_tokens, total_output_tokens, total_cost_usd),
                )
                conn.commit()
            finally:
                conn.close()

    def get_prompts(
        self,
        tool_name: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Query prompts with optional filters. Decrypts text fields."""
        conditions = []
        params = []

        if tool_name:
            conditions.append("tool_name = ?")
            params.append(tool_name)
        if since:
            conditions.append("timestamp >= ?")
            params.append(since.isoformat())

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            try:
                rows = conn.execute(
                    f"SELECT * FROM prompts {where} ORDER BY timestamp DESC LIMIT ?",
                    (*params, limit),
                ).fetchall()

                results = []
                for row in rows:
                    d = dict(row)
                    d["prompt_text"] = self._decrypt_text(d.get("prompt_text"))
                    d["response_text"] = self._decrypt_text(d.get("response_text"))
                    results.append(d)
                return results
            finally:
                conn.close()

    def get_stats(self) -> dict:
        """Get aggregate statistics from the database."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                row = conn.execute(
                    """SELECT
                        COUNT(*) as total_prompts,
                        SUM(input_tokens) as total_input_tokens,
                        SUM(output_tokens) as total_output_tokens,
                        SUM(estimated_cost_usd) as total_cost_usd
                    FROM prompts"""
                ).fetchone()
                return {
                    "total_prompts": row[0] or 0,
                    "total_input_tokens": row[1] or 0,
                    "total_output_tokens": row[2] or 0,
                    "total_cost_usd": row[3] or 0.0,
                }
            finally:
                conn.close()

    def cleanup(self) -> int:
        """Delete prompts older than retention_days. Returns number of rows deleted."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.retention_days)

        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.execute(
                    "DELETE FROM prompts WHERE timestamp < ?",
                    (cutoff.isoformat(),),
                )
                deleted = cursor.rowcount
                conn.commit()
                if deleted > 0:
                    conn.execute("VACUUM")
                logger.debug("Cleaned up {} prompts older than {} days", deleted, self.retention_days)
                return deleted
            finally:
                conn.close()

    def close(self) -> None:
        """No persistent connection to close, but available for API consistency."""
        pass
