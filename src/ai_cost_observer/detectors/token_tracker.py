"""Token tracker — reads local AI tool files to extract real token usage metrics."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from loguru import logger

from ai_cost_observer.config import AppConfig
from ai_cost_observer.telemetry import TelemetryManager

# Known pricing per 1M tokens (input/output) — updated as of 2025
MODEL_PRICING: dict[str, tuple[float, float]] = {
    # Anthropic
    "claude-opus-4": (15.0, 75.0),
    "claude-opus-4-6": (15.0, 75.0),
    "claude-sonnet-4": (3.0, 15.0),
    "claude-sonnet-4-5": (3.0, 15.0),
    "claude-haiku-3-5": (0.80, 4.0),
    # OpenAI
    "gpt-4o": (2.50, 10.0),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4-turbo": (10.0, 30.0),
    "gpt-4.1": (2.0, 8.0),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1-nano": (0.10, 0.40),
    "o1": (15.0, 60.0),
    "o1-mini": (3.0, 12.0),
    "o3": (10.0, 40.0),
    "o3-mini": (1.10, 4.40),
    "o4-mini": (1.10, 4.40),
    # Google
    "gemini-2.5-pro": (1.25, 10.0),
    "gemini-2.5-flash": (0.15, 0.60),
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-2.0-pro": (1.25, 10.0),
    "gemini-1.5-pro": (1.25, 5.0),
    "gemini-1.5-flash": (0.075, 0.30),
    # DeepSeek
    "deepseek-v3": (0.27, 1.10),
    "deepseek-r1": (0.55, 2.19),
}


def estimate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_creation_input_tokens: int = 0,
    cache_read_input_tokens: int = 0,
) -> float:
    """Estimate cost in USD from model name and token counts.

    Cache token pricing follows Anthropic conventions:
    - cache_creation_input_tokens: 1.25x the input price
    - cache_read_input_tokens: 0.1x the input price
    """
    # Try exact match first, then prefix match
    pricing = MODEL_PRICING.get(model)
    if not pricing:
        for key, val in MODEL_PRICING.items():
            if model and model.startswith(key):
                pricing = val
                break
    if not pricing:
        # Default fallback: mid-range pricing
        pricing = (3.0, 15.0)

    input_price = pricing[0]
    output_price = pricing[1]

    input_cost = (input_tokens / 1_000_000) * input_price
    output_cost = (output_tokens / 1_000_000) * output_price
    cache_creation_cost = (cache_creation_input_tokens / 1_000_000) * input_price * 1.25
    cache_read_cost = (cache_read_input_tokens / 1_000_000) * input_price * 0.1
    return input_cost + output_cost + cache_creation_cost + cache_read_cost


class TokenTracker:
    """Scans local AI tool data files for token usage metrics.

    Sources:
    - Claude Code: ~/.claude/projects/*/[session].jsonl
    - Codex: ~/.codex/ (if present)
    """

    def __init__(
        self,
        config: AppConfig,
        telemetry: TelemetryManager,
        prompt_db=None,
    ) -> None:
        self.config = config
        self.telemetry = telemetry
        self.prompt_db = prompt_db

        # Track file positions for incremental reading
        self._file_offsets: dict[str, int] = {}
        self._codex_last_rowid: int = 0
        self._last_scan_time: float = 0.0

        # State file for persisting offsets across restarts
        self._state_file = config.state_dir / "token_tracker_state.json"
        self._load_state()

        # Token tracking config from ai_config
        self._tt_config = getattr(config, "token_tracking", {}) or {}

    def _load_state(self) -> None:
        """Load persisted state (file offsets, codex rowid) from disk."""
        if self._state_file.exists():
            try:
                data = json.loads(self._state_file.read_text(encoding="utf-8"))
                self._file_offsets = {k: int(v) for k, v in data.get("file_offsets", {}).items()}
                self._codex_last_rowid = int(data.get("codex_last_rowid", 0))
            except Exception:
                logger.opt(exception=True).debug("Failed to load token tracker state")

    def _save_state(self) -> None:
        """Persist state (file offsets, codex rowid) to disk."""
        try:
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "file_offsets": self._file_offsets,
                "codex_last_rowid": self._codex_last_rowid,
            }
            self._state_file.write_text(json.dumps(data), encoding="utf-8")
        except Exception:
            logger.opt(exception=True).debug("Failed to save token tracker state")

    def scan(self) -> None:
        """Run one scan cycle: read local files, extract tokens, emit metrics."""
        try:
            self._scan_claude_code()
        except Exception:
            logger.opt(exception=True).error("Error scanning Claude Code data")

        try:
            self._scan_codex()
        except Exception:
            logger.opt(exception=True).error("Error scanning Codex data")

        self._save_state()
        self._last_scan_time = time.monotonic()

    def _scan_claude_code(self) -> None:
        """Read Claude Code JSONL transcripts for token/cost data."""
        claude_dir = Path.home() / ".claude" / "projects"
        if not claude_dir.exists():
            return

        for jsonl_file in claude_dir.rglob("*.jsonl"):
            self._process_claude_jsonl(jsonl_file)

    def _process_claude_jsonl(self, path: Path) -> None:
        """Process a single Claude Code JSONL file incrementally."""
        path_str = str(path)
        try:
            file_size = path.stat().st_size
        except OSError:
            return

        offset = self._file_offsets.get(path_str, 0)
        if file_size <= offset:
            return  # No new data

        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                f.seek(offset)
                new_data = f.read()
                self._file_offsets[path_str] = f.tell()
        except OSError:
            logger.debug("Cannot read {}", path_str)
            return

        # Parse each new line
        for line in new_data.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            self._extract_claude_tokens(entry, path)

    def _extract_claude_tokens(self, entry: dict, source_path: Path) -> None:
        """Extract token usage from a Claude Code JSONL entry."""
        # Claude Code JSONL has various message types
        # Look for usage data in assistant responses
        usage = entry.get("usage")
        if not usage:
            # Some entries nest usage under "message"
            message = entry.get("message", {})
            if isinstance(message, dict):
                usage = message.get("usage")

        if not usage:
            return

        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        cache_creation = usage.get("cache_creation_input_tokens", 0)
        cache_read = usage.get("cache_read_input_tokens", 0)

        if input_tokens == 0 and output_tokens == 0:
            return

        model = entry.get("model", "") or entry.get("message", {}).get("model", "") or "unknown"
        cost = estimate_cost(
            model,
            input_tokens,
            output_tokens,
            cache_creation_input_tokens=cache_creation,
            cache_read_input_tokens=cache_read,
        )

        labels = {"tool.name": "claude-code", "model.name": model}

        self.telemetry.tokens_input_total.add(input_tokens, labels)
        self.telemetry.tokens_output_total.add(output_tokens, labels)
        if cost > 0:
            self.telemetry.tokens_cost_usd_total.add(cost, labels)
        self.telemetry.prompt_count_total.add(1, {"tool.name": "claude-code", "source": "cli"})

        # Store in prompt DB if available
        if self.prompt_db:
            prompt_text = None

            # Extract prompt/response text if configured
            if self._tt_config.get("capture_prompt_text", True):
                content = entry.get("content") or entry.get("message", {}).get("content")
                if isinstance(content, list):
                    # Content blocks format
                    texts = [b.get("text", "") for b in content if isinstance(b, dict)]
                    prompt_text = "\n".join(t for t in texts if t)
                elif isinstance(content, str):
                    prompt_text = content

            role = entry.get("role") or entry.get("message", {}).get("role", "")

            try:
                self.prompt_db.insert_prompt(
                    tool_name="claude-code",
                    model_name=model,
                    source="cli",
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cache_creation_tokens=cache_creation,
                    cache_read_tokens=cache_read,
                    estimated_cost_usd=cost,
                    prompt_text=prompt_text if role == "user" else None,
                    response_text=prompt_text if role == "assistant" else None,
                    project_path=str(source_path.parent.name),
                )
            except Exception:
                logger.opt(exception=True).debug("Failed to store prompt")

    def _scan_codex(self) -> None:
        """Read Codex CLI SQLite database for session/token data."""
        codex_db = Path.home() / ".codex" / "sqlite" / "codex-dev.db"
        if not codex_db.exists():
            return

        try:
            conn = sqlite3.connect(f"file:{codex_db}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
        except sqlite3.Error:
            logger.opt(exception=True).debug("Cannot open Codex DB")
            return

        try:
            # Read sessions with token data (schema may vary)
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row["name"] for row in cursor}

            if "sessions" not in tables:
                return

            # Get column names to adapt query
            cursor = conn.execute("PRAGMA table_info(sessions)")
            columns = {row["name"] for row in cursor}

            if "input_tokens" not in columns:
                return

            # Read only new sessions since last processed rowid
            cursor = conn.execute(
                "SELECT rowid, * FROM sessions WHERE input_tokens > 0 AND rowid > ? ORDER BY rowid",
                (self._codex_last_rowid,),
            )

            for row in cursor:
                self._codex_last_rowid = row["rowid"]
                input_tokens = row["input_tokens"] or 0
                output_tokens = row["output_tokens"] if "output_tokens" in columns else 0
                model = row["model"] if "model" in columns else "unknown"

                cost = estimate_cost(model, input_tokens, output_tokens)
                labels = {"tool.name": "codex-cli", "model.name": model}

                self.telemetry.tokens_input_total.add(input_tokens, labels)
                self.telemetry.tokens_output_total.add(output_tokens, labels)
                if cost > 0:
                    self.telemetry.tokens_cost_usd_total.add(cost, labels)
                self.telemetry.prompt_count_total.add(
                    1, {"tool.name": "codex-cli", "source": "cli"}
                )

        except sqlite3.Error:
            logger.opt(exception=True).debug("Error reading Codex DB")
        finally:
            conn.close()

    def record_api_intercept(
        self,
        tool_name: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        prompt_text: str | None = None,
        response_text: str | None = None,
    ) -> None:
        """Record token usage from an API intercept (e.g., Chrome extension)."""
        cost = estimate_cost(model, input_tokens, output_tokens)
        labels = {"tool.name": tool_name, "model.name": model}

        self.telemetry.tokens_input_total.add(input_tokens, labels)
        self.telemetry.tokens_output_total.add(output_tokens, labels)
        if cost > 0:
            self.telemetry.tokens_cost_usd_total.add(cost, labels)
        self.telemetry.prompt_count_total.add(1, {"tool.name": tool_name, "source": "browser"})

        if self.prompt_db:
            try:
                self.prompt_db.insert_prompt(
                    tool_name=tool_name,
                    model_name=model,
                    source="browser",
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    estimated_cost_usd=cost,
                    prompt_text=prompt_text,
                    response_text=response_text,
                )
            except Exception:
                logger.opt(exception=True).debug("Failed to store browser prompt")
