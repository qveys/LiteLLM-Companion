"""Configuration loader with YAML support and environment variable overrides."""

from __future__ import annotations

import os
import platform
import socket
from dataclasses import dataclass, field
from importlib.resources import files
from pathlib import Path

import yaml


def _default_config_dir() -> Path:
    return Path.home() / ".config" / "ai-cost-observer"


def _default_state_dir() -> Path:
    if platform.system() == "Windows":
        return Path.home() / ".config" / "ai-cost-observer" / "state"
    return Path.home() / ".local" / "state" / "ai-cost-observer"


@dataclass
class AppConfig:
    otel_endpoint: str = "vps.quentinveys.be:4317"
    otel_bearer_token: str = ""
    otel_insecure: bool = False
    scan_interval_seconds: int = 15
    browser_history_interval_seconds: int = 60
    shell_history_interval_seconds: int = 3600
    http_receiver_port: int = 8080
    host_name: str = field(default_factory=socket.gethostname)
    config_dir: Path = field(default_factory=_default_config_dir)
    state_dir: Path = field(default_factory=_default_state_dir)
    ai_apps: list[dict] = field(default_factory=list)
    ai_domains: list[dict] = field(default_factory=list)
    ai_cli_tools: list[dict] = field(default_factory=list)
    api_intercept_patterns: list[dict] = field(default_factory=list)
    token_tracking: dict = field(
        default_factory=lambda: {
            "enabled": True,
            "storage_path": "auto",
            "api_polling_interval_seconds": 300,
            "retention_days": 90,
            "encrypt_prompts": True,
            "capture_prompt_text": True,
            "capture_response_text": True,
            "sources": {
                "claude_code": True,
                "codex": True,
                "gemini": True,
                "browser_extension": True,
            },
        }
    )


def _load_builtin_ai_config() -> dict:
    """Load the built-in ai_config.yaml from package data."""
    data_dir = files("ai_cost_observer") / "data"
    config_path = data_dir / "ai_config.yaml"
    return yaml.safe_load(config_path.read_text(encoding="utf-8"))


def _load_user_config(config_dir: Path) -> dict:
    """Load optional user config overlay."""
    user_config_path = config_dir / "config.yaml"
    if user_config_path.exists():
        return yaml.safe_load(user_config_path.read_text(encoding="utf-8")) or {}
    return {}


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base dict.

    For nested dicts, merges recursively instead of replacing the entire dict.
    For all other types (lists, scalars), the override value replaces the base.
    Returns the merged dict (mutates base in place).
    """
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def load_config() -> AppConfig:
    """Load configuration with hierarchy: built-in → user file → env vars."""
    builtin = _load_builtin_ai_config()
    config = AppConfig()

    user = _load_user_config(config.config_dir)

    # Merge user overrides for connection settings
    if "otel_endpoint" in user:
        config.otel_endpoint = user["otel_endpoint"]
    if "otel_bearer_token" in user:
        config.otel_bearer_token = user["otel_bearer_token"]
    if "otel_insecure" in user:
        config.otel_insecure = user["otel_insecure"]
    if "host_name" in user:
        config.host_name = user["host_name"]
    if "scan_interval_seconds" in user:
        config.scan_interval_seconds = user["scan_interval_seconds"]

    # Environment variable overrides (highest priority)
    if env_endpoint := os.environ.get("OTEL_ENDPOINT"):
        config.otel_endpoint = env_endpoint
    if env_token := os.environ.get("OTEL_BEARER_TOKEN"):
        config.otel_bearer_token = env_token
    if os.environ.get("OTEL_INSECURE", "").lower() in ("true", "1"):
        config.otel_insecure = True

    # Load AI tool definitions
    config.ai_apps = builtin.get("ai_apps", [])
    config.ai_domains = builtin.get("ai_domains", [])
    config.ai_cli_tools = builtin.get("ai_cli_tools", [])
    config.api_intercept_patterns = builtin.get("api_intercept_patterns", [])

    # Load token tracking config from built-in, deep-merge user overrides
    builtin_tt = builtin.get("token_tracking", {})
    if builtin_tt:
        _deep_merge(config.token_tracking, builtin_tt)
    if "token_tracking" in user:
        _deep_merge(config.token_tracking, user["token_tracking"])

    # User can add extra tools
    if "extra_ai_apps" in user:
        config.ai_apps.extend(user["extra_ai_apps"])
    if "extra_ai_domains" in user:
        config.ai_domains.extend(user["extra_ai_domains"])
    if "extra_ai_cli_tools" in user:
        config.ai_cli_tools.extend(user["extra_ai_cli_tools"])
    if "extra_api_intercept_patterns" in user:
        config.api_intercept_patterns.extend(user["extra_api_intercept_patterns"])

    # Ensure state directory exists
    config.state_dir.mkdir(parents=True, exist_ok=True)

    return config
