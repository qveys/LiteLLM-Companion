"""Tests for the configuration loader."""

import os
from pathlib import Path

from ai_cost_observer.config import load_config


def test_config_loading_priority(mocker):
    """
    Verify the configuration loading priority using direct mocking:
    1. Environment variables (highest)
    2. User config file
    3. Built-in config / defaults (lowest)
    """
    # 1. Mock the return value of the built-in config loader
    builtin_config_data = {
        "ai_apps": [{"name": "BuiltInApp", "cost_per_hour": 1.0}],
        "ai_domains": [{"domain": "builtin.com", "cost_per_hour": 1.0}],
        "ai_cli_tools": [{"name": "builtin-cli", "cost_per_hour": 1.0}],
    }
    mocker.patch(
        "ai_cost_observer.config._load_builtin_ai_config", return_value=builtin_config_data
    )

    # 2. Mock the return value of the user config loader
    user_config_data = {
        "otel_endpoint": "user.endpoint.com:4317",
        "otel_bearer_token": "user_token_from_file",
        "scan_interval_seconds": 99,
        "extra_ai_apps": [{"name": "UserApp", "cost_per_hour": 2.0}],
    }
    # We also mock _default_config_dir to avoid side-effects, though it's not strictly
    # necessary with this approach as _load_user_config is what we care about.
    mocker.patch(
        "ai_cost_observer.config._default_config_dir", return_value=Path("/tmp/mock_config")
    )
    mocker.patch("ai_cost_observer.config._load_user_config", return_value=user_config_data)

    # 3. Mock environment variables
    # Use clear=True to ensure a clean environment for the test
    env_vars = {
        "OTEL_ENDPOINT": "env.endpoint.com:4317",
        "OTEL_BEARER_TOKEN": "env_token",
        "OTEL_INSECURE": "true",
    }
    mocker.patch.dict(os.environ, env_vars, clear=True)

    # 4. Mock the state directory creation to avoid filesystem side effects
    mocker.patch("pathlib.Path.mkdir")

    # Load the configuration with all mocks in place
    config = load_config()

    # --- Assertions ---
    # Env vars have highest priority
    assert config.otel_endpoint == "env.endpoint.com:4317"
    assert config.otel_bearer_token == "env_token"
    assert config.otel_insecure is True

    # User file value is used if not set in env vars
    assert config.scan_interval_seconds == 99

    # Lists are correctly merged (built-in + user 'extra_')
    assert len(config.ai_apps) == 2
    app_names = {app["name"] for app in config.ai_apps}
    assert "BuiltInApp" in app_names
    assert "UserApp" in app_names

    # Lists without 'extra_' come from built-in only
    assert len(config.ai_domains) == 1
    assert config.ai_domains[0]["domain"] == "builtin.com"
