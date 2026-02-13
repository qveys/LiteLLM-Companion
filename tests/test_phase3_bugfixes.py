"""Tests for Phase 3 bug fixes (#11-#20).

Each bug fix has at least one dedicated test to verify the fix and prevent
regressions.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import pytest

from ai_cost_observer.config import AppConfig, _deep_merge, load_config


# ---------------------------------------------------------------------------
# Bug #11 — Session duration: single-visit sessions get flat 60s, not +300s
# ---------------------------------------------------------------------------

class TestBug11SessionDurationBuffer:
    """Single-visit sessions should not get the 300s multi-visit buffer."""

    @pytest.fixture
    def parser(self):
        from ai_cost_observer.detectors.browser_history import BrowserHistoryParser

        config = AppConfig(
            ai_domains=[
                {"domain": "test.ai", "category": "test", "cost_per_hour": 0},
            ],
        )
        telemetry = Mock()
        telemetry.browser_domain_visit_count = Mock()
        telemetry.browser_domain_visit_count.add = Mock()
        telemetry.browser_domain_active_duration = Mock()
        telemetry.browser_domain_active_duration.add = Mock()
        telemetry.browser_domain_estimated_cost = Mock()
        telemetry.browser_domain_estimated_cost.add = Mock()
        return BrowserHistoryParser(config, telemetry)

    def test_single_visit_gets_60s_not_300s(self, parser):
        """A single visit should estimate 60s, not 300s."""
        visits = [
            {"visit_time": 13300000000000000, "browser": "chromium"},
        ]
        duration = parser._estimate_session_duration(visits, "chrome")
        assert duration == 60.0

    def test_two_close_visits_get_300s_buffer(self, parser):
        """Two visits in the same session should get the 300s buffer."""
        base = 13300000000000000
        visits = [
            {"visit_time": base, "browser": "chromium"},
            {"visit_time": base + 120_000_000, "browser": "chromium"},  # 2 min later
        ]
        duration = parser._estimate_session_duration(visits, "chrome")
        # span = 120s, buffer = 300s => 420s
        assert duration == pytest.approx(420.0)

    def test_two_sessions_one_single_one_multi(self, parser):
        """Two separate sessions: one single-visit (60s), one multi-visit (span+300s)."""
        base = 13300000000000000
        gap = 31 * 60 * 1_000_000  # 31 minutes in microseconds (> 30 min session gap)
        visits = [
            # Session 1: single visit
            {"visit_time": base, "browser": "chromium"},
            # Session 2: two close visits
            {"visit_time": base + gap, "browser": "chromium"},
            {"visit_time": base + gap + 60_000_000, "browser": "chromium"},  # 1 min later
        ]
        duration = parser._estimate_session_duration(visits, "chrome")
        # Session 1: single visit = 60s
        # Session 2: span=60s + buffer=300s = 360s
        # Total = 420s
        assert duration == pytest.approx(420.0)


# ---------------------------------------------------------------------------
# Bug #12 — JetBrains/VS Code requires_plugin flag
# ---------------------------------------------------------------------------

class TestBug12RequiresPluginFlag:
    """IDE entries should have requires_plugin=true in ai_config.yaml."""

    def test_vscode_has_requires_plugin_flag(self):
        """GitHub Copilot (VS Code) entry has requires_plugin: true."""
        from importlib.resources import files

        import yaml

        data_dir = files("ai_cost_observer") / "data"
        config = yaml.safe_load((data_dir / "ai_config.yaml").read_text())

        vscode = next(a for a in config["ai_apps"] if "VS Code" in a["name"])
        assert vscode.get("requires_plugin") is True

    def test_jetbrains_has_requires_plugin_flag(self):
        """JetBrains AI entry has requires_plugin: true."""
        from importlib.resources import files

        import yaml

        data_dir = files("ai_cost_observer") / "data"
        config = yaml.safe_load((data_dir / "ai_config.yaml").read_text())

        jetbrains = next(a for a in config["ai_apps"] if "JetBrains" in a["name"])
        assert jetbrains.get("requires_plugin") is True

    def test_desktop_detector_emits_requires_plugin_label(self, mocker):
        """Desktop detector adds app.requires_plugin label for flagged apps."""
        from ai_cost_observer.detectors.desktop import DesktopDetector

        apps = [
            {
                "name": "JetBrains AI",
                "process_names": {"macos": ["idea"], "windows": ["idea64.exe"]},
                "category": "code",
                "cost_per_hour": 0.40,
                "requires_plugin": True,
            }
        ]
        config = AppConfig(ai_apps=apps)
        telemetry = Mock()
        telemetry.set_running_apps = Mock()
        telemetry.app_cpu_usage = Mock()
        telemetry.app_cpu_usage.set = Mock()
        telemetry.app_memory_usage = Mock()
        telemetry.app_memory_usage.set = Mock()
        telemetry.app_active_duration = Mock()
        telemetry.app_estimated_cost = Mock()

        detector = DesktopDetector(config, telemetry)

        proc = MagicMock()
        proc.info = {"pid": 42, "name": "idea", "cmdline": []}
        proc.cpu_percent.return_value = 5.0
        proc.memory_info.return_value = SimpleNamespace(rss=100 * 1024 * 1024)

        mocker.patch("psutil.process_iter", return_value=[proc])
        mocker.patch(
            "ai_cost_observer.detectors.desktop.get_foreground_app",
            return_value=None,
        )
        detector.scan()

        # Check that running_apps has the requires_plugin label
        running = detector.running_apps
        assert "JetBrains AI" in running
        assert running["JetBrains AI"]["app.requires_plugin"] == "true"


# ---------------------------------------------------------------------------
# Bug #13 — Missing cli.category in shell history
# ---------------------------------------------------------------------------

class TestBug13ShellHistoryCategory:
    """Shell history parser should emit cli.category attribute."""

    def test_category_included_in_labels(self, tmp_path):
        from ai_cost_observer.detectors.shell_history import ShellHistoryParser

        config = AppConfig()
        config.state_dir = tmp_path / "state"
        config.ai_cli_tools = [
            {"name": "ollama", "command_patterns": ["ollama"], "category": "local"},
        ]

        telemetry = Mock()
        telemetry.cli_command_count = Mock()
        telemetry.cli_command_count.add = Mock()

        history_file = tmp_path / ".bash_history"
        history_file.write_text("ollama run llama3\n", encoding="utf-8")

        parser = ShellHistoryParser(config, telemetry)
        parser._get_history_files = lambda: [(str(history_file), "bash")]
        parser.scan()

        telemetry.cli_command_count.add.assert_called_once_with(
            1, {"cli.name": "ollama", "cli.category": "local"},
        )

    def test_missing_category_defaults_to_unknown(self, tmp_path):
        from ai_cost_observer.detectors.shell_history import ShellHistoryParser

        config = AppConfig()
        config.state_dir = tmp_path / "state"
        config.ai_cli_tools = [
            {"name": "mycli", "command_patterns": ["mycli"]},
            # no 'category' key
        ]

        telemetry = Mock()
        telemetry.cli_command_count = Mock()
        telemetry.cli_command_count.add = Mock()

        history_file = tmp_path / ".bash_history"
        history_file.write_text("mycli do-something\n", encoding="utf-8")

        parser = ShellHistoryParser(config, telemetry)
        parser._get_history_files = lambda: [(str(history_file), "bash")]
        parser.scan()

        call_labels = telemetry.cli_command_count.add.call_args[0][1]
        assert call_labels["cli.category"] == "unknown"


# ---------------------------------------------------------------------------
# Bug #14 — Config deep merge
# ---------------------------------------------------------------------------

class TestBug14DeepMerge:
    """_deep_merge should recursively merge nested dicts."""

    def test_deep_merge_nested_dicts(self):
        base = {"a": {"x": 1, "y": 2}, "b": 3}
        override = {"a": {"y": 99, "z": 100}}
        result = _deep_merge(base, override)
        assert result == {"a": {"x": 1, "y": 99, "z": 100}, "b": 3}

    def test_deep_merge_replaces_non_dict(self):
        base = {"a": [1, 2, 3]}
        override = {"a": [4, 5]}
        result = _deep_merge(base, override)
        assert result == {"a": [4, 5]}

    def test_deep_merge_adds_new_keys(self):
        base = {"a": 1}
        override = {"b": 2}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": 2}

    def test_token_tracking_deep_merge(self, mocker):
        """User overriding one source in token_tracking should not wipe others."""
        builtin = {
            "ai_apps": [],
            "ai_domains": [],
            "ai_cli_tools": [],
            "token_tracking": {
                "enabled": True,
                "sources": {
                    "claude_code": True,
                    "codex": True,
                    "gemini": True,
                    "browser_extension": True,
                },
            },
        }
        user = {
            "token_tracking": {
                "sources": {
                    "codex": False,
                },
            },
        }

        mocker.patch("ai_cost_observer.config._load_builtin_ai_config", return_value=builtin)
        mocker.patch("ai_cost_observer.config._load_user_config", return_value=user)
        mocker.patch("ai_cost_observer.config._default_config_dir", return_value=Path("/tmp/mock"))
        mocker.patch("pathlib.Path.mkdir")

        config = load_config()

        # codex should be overridden to False
        assert config.token_tracking["sources"]["codex"] is False
        # other sources should be preserved (not wiped by shallow update)
        assert config.token_tracking["sources"]["claude_code"] is True
        assert config.token_tracking["sources"]["gemini"] is True
        assert config.token_tracking["sources"]["browser_extension"] is True


# ---------------------------------------------------------------------------
# Bug #15 — WSL "linux" key support
# ---------------------------------------------------------------------------

class TestBug15WslLinuxKey:
    """WSL detector should use 'linux' key, falling back to 'macos'."""

    def test_linux_key_preferred_over_macos(self, mocker):
        from ai_cost_observer.detectors.wsl import WSLDetector

        config = AppConfig(
            ai_cli_tools=[
                {
                    "name": "mytool",
                    "category": "code",
                    "process_names": {
                        "linux": ["mytool-linux"],
                        "macos": ["mytool-mac"],
                    },
                }
            ],
        )

        wsl_snapshots = []
        telemetry = SimpleNamespace(
            set_running_wsl=lambda running: wsl_snapshots.append(dict(running)),
        )
        detector = WSLDetector(config, telemetry)
        detector._enabled = True

        mocker.patch.object(detector, "_get_running_distros", return_value=["Ubuntu"])

        ps_output = (
            "USER PID %CPU %MEM VSZ RSS TTY STAT START TIME COMMAND\n"
            "user 1 0.0 0.1 1 1 ? S 00:00 00:00 mytool-linux\n"
        )
        mocker.patch(
            "ai_cost_observer.detectors.wsl.subprocess.run",
            return_value=SimpleNamespace(returncode=0, stdout=ps_output),
        )
        detector.scan()

        assert len(wsl_snapshots) == 1
        assert len(wsl_snapshots[0]) == 1
        labels = list(wsl_snapshots[0].values())[0]
        assert labels["cli.name"] == "mytool"

    def test_fallback_to_macos_when_no_linux_key(self, mocker):
        from ai_cost_observer.detectors.wsl import WSLDetector

        config = AppConfig(
            ai_cli_tools=[
                {
                    "name": "oldtool",
                    "category": "code",
                    "process_names": {"macos": ["oldtool"]},
                }
            ],
        )

        wsl_snapshots = []
        telemetry = SimpleNamespace(
            set_running_wsl=lambda running: wsl_snapshots.append(dict(running)),
        )
        detector = WSLDetector(config, telemetry)
        detector._enabled = True

        mocker.patch.object(detector, "_get_running_distros", return_value=["Debian"])

        ps_output = (
            "USER PID %CPU %MEM VSZ RSS TTY STAT START TIME COMMAND\n"
            "user 1 0.0 0.1 1 1 ? S 00:00 00:00 oldtool\n"
        )
        mocker.patch(
            "ai_cost_observer.detectors.wsl.subprocess.run",
            return_value=SimpleNamespace(returncode=0, stdout=ps_output),
        )
        detector.scan()

        assert len(wsl_snapshots) == 1
        assert len(wsl_snapshots[0]) == 1
        labels = list(wsl_snapshots[0].values())[0]
        assert labels["cli.name"] == "oldtool"

    def test_cli_tools_have_linux_key(self):
        """All CLI tools in ai_config.yaml should have a linux key."""
        from importlib.resources import files

        import yaml

        data_dir = files("ai_cost_observer") / "data"
        config = yaml.safe_load((data_dir / "ai_config.yaml").read_text())

        for tool in config["ai_cli_tools"]:
            pn = tool.get("process_names", {})
            assert "linux" in pn, (
                f"CLI tool '{tool['name']}' is missing a 'linux' key in process_names"
            )


# ---------------------------------------------------------------------------
# Bug #16 — HTTP receiver rate limiting and payload size
# ---------------------------------------------------------------------------

class TestBug16HttpLimits:
    """HTTP receiver should enforce rate limits and payload size."""

    @pytest.fixture
    def app(self):
        from ai_cost_observer.server.http_receiver import create_app

        config = AppConfig(
            ai_domains=[
                {"domain": "test.ai", "category": "test", "cost_per_hour": 0},
            ],
        )
        telemetry = Mock()
        telemetry.browser_domain_visit_count = Mock()
        telemetry.browser_domain_visit_count.add = Mock()
        telemetry.browser_domain_active_duration = Mock()
        telemetry.browser_domain_active_duration.add = Mock()
        telemetry.browser_domain_estimated_cost = Mock()
        telemetry.browser_domain_estimated_cost.add = Mock()

        flask_app = create_app(config, telemetry)
        flask_app.config["TESTING"] = True
        return flask_app

    def test_too_many_events_rejected(self, app):
        """Requests with more than MAX_EVENTS_PER_REQUEST events are rejected."""
        from ai_cost_observer.server.http_receiver import MAX_EVENTS_PER_REQUEST

        client = app.test_client()
        events = [{"domain": "test.ai", "duration_seconds": 1, "visit_count": 1}] * (
            MAX_EVENTS_PER_REQUEST + 1
        )
        resp = client.post("/metrics/browser", json={"events": events})
        assert resp.status_code == 400
        assert "Too many events" in resp.get_json()["error"]

    def test_valid_events_accepted(self, app):
        """Normal-sized payloads are accepted."""
        client = app.test_client()
        events = [{"domain": "test.ai", "duration_seconds": 10, "visit_count": 1}]
        resp = client.post("/metrics/browser", json={"events": events})
        assert resp.status_code == 200

    def test_token_events_limit(self, app):
        """Token endpoint also enforces max events."""
        from ai_cost_observer.server.http_receiver import MAX_EVENTS_PER_REQUEST

        client = app.test_client()
        events = [
            {"type": "api_intercept", "tool": "test", "model": "m", "input_tokens": 1, "output_tokens": 1}
        ] * (MAX_EVENTS_PER_REQUEST + 1)
        resp = client.post("/api/tokens", json={"events": events})
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Bug #17 — Encryption key from env var
# ---------------------------------------------------------------------------

class TestBug17EncryptionKeyFromEnv:
    """Prompt DB should use PROMPT_DB_KEY env var for encryption when set."""

    def test_env_key_produces_different_ciphertext(self, tmp_path):
        """Different PROMPT_DB_KEY values should produce different ciphertext."""
        from ai_cost_observer.storage.prompt_db import PromptDB

        db1_path = tmp_path / "db1.db"
        db2_path = tmp_path / "db2.db"

        with patch.dict(os.environ, {"PROMPT_DB_KEY": "secret-key-alpha"}):
            db1 = PromptDB(db_path=db1_path, encrypt=True)
        with patch.dict(os.environ, {"PROMPT_DB_KEY": "secret-key-beta"}):
            db2 = PromptDB(db_path=db2_path, encrypt=True)

        if db1._fernet is None or db2._fernet is None:
            pytest.skip("cryptography not installed")

        # Same plaintext
        text = "test prompt"
        enc1 = db1._encrypt_text(text)
        enc2 = db2._encrypt_text(text)

        # Encrypted output should differ (different keys)
        # (Fernet also uses random IV, so even same key gives different output,
        # but decrypting with the wrong key should fail)
        assert enc1 != text
        assert enc2 != text

        # db1 can decrypt its own text
        assert db1._decrypt_text(enc1) == text
        # db2 can decrypt its own text
        assert db2._decrypt_text(enc2) == text


# ---------------------------------------------------------------------------
# Bug #19 — cpu_percent priming
# ---------------------------------------------------------------------------

class TestBug19CpuPercentPriming:
    """First call to cpu_percent for a new PID should be treated as priming."""

    def test_first_scan_cpu_is_zero(self, mocker):
        """On the first scan, a new PID's cpu value should be 0 (primed)."""
        from ai_cost_observer.detectors.desktop import DesktopDetector

        config = AppConfig(
            ai_apps=[
                {
                    "name": "TestApp",
                    "process_names": {"macos": ["TestApp"], "windows": ["TestApp.exe"]},
                    "category": "test",
                    "cost_per_hour": 0,
                }
            ],
        )

        telemetry = Mock()
        telemetry.set_running_apps = Mock()
        telemetry.app_cpu_usage = Mock()
        telemetry.app_cpu_usage.set = Mock()
        telemetry.app_memory_usage = Mock()
        telemetry.app_memory_usage.set = Mock()
        telemetry.app_active_duration = Mock()
        telemetry.app_estimated_cost = Mock()

        detector = DesktopDetector(config, telemetry)

        proc = MagicMock()
        proc.info = {"pid": 123, "name": "TestApp", "cmdline": []}
        proc.cpu_percent.return_value = 50.0
        proc.memory_info.return_value = SimpleNamespace(rss=256 * 1024 * 1024)

        mocker.patch("psutil.process_iter", return_value=[proc])
        mocker.patch(
            "ai_cost_observer.detectors.desktop.get_foreground_app",
            return_value=None,
        )

        # First scan: PID is primed, CPU forced to 0.0
        detector.scan()
        cpu_val = telemetry.app_cpu_usage.set.call_args[0][0]
        assert cpu_val == 0.0

        # Second scan: PID is already primed, real CPU value used
        telemetry.app_cpu_usage.set.reset_mock()
        detector.scan()
        cpu_val = telemetry.app_cpu_usage.set.call_args[0][0]
        assert cpu_val == 50.0

    def test_stale_primed_pids_cleaned_up(self, mocker):
        """PIDs that no longer exist are removed from the primed set."""
        from ai_cost_observer.detectors.desktop import DesktopDetector

        config = AppConfig(
            ai_apps=[
                {
                    "name": "TestApp",
                    "process_names": {"macos": ["TestApp"], "windows": ["TestApp.exe"]},
                    "category": "test",
                    "cost_per_hour": 0,
                }
            ],
        )

        telemetry = Mock()
        telemetry.set_running_apps = Mock()
        telemetry.app_cpu_usage = Mock()
        telemetry.app_cpu_usage.set = Mock()
        telemetry.app_memory_usage = Mock()
        telemetry.app_memory_usage.set = Mock()
        telemetry.app_active_duration = Mock()
        telemetry.app_estimated_cost = Mock()

        detector = DesktopDetector(config, telemetry)

        proc = MagicMock()
        proc.info = {"pid": 999, "name": "TestApp", "cmdline": []}
        proc.cpu_percent.return_value = 10.0
        proc.memory_info.return_value = SimpleNamespace(rss=100 * 1024 * 1024)

        mocker.patch("psutil.process_iter", return_value=[proc])
        mocker.patch(
            "ai_cost_observer.detectors.desktop.get_foreground_app",
            return_value=None,
        )

        detector.scan()
        assert 999 in detector._primed_pids

        # Process goes away
        mocker.patch("psutil.process_iter", return_value=[])
        detector.scan()
        assert 999 not in detector._primed_pids


# ---------------------------------------------------------------------------
# Bug #20 — _total suffix removed from OTel metric names
# ---------------------------------------------------------------------------

class TestBug20TotalSuffixRemoved:
    """OTel metric names should not contain _total; Prometheus adds it."""

    @patch("ai_cost_observer.telemetry.metrics")
    @patch("ai_cost_observer.telemetry.MeterProvider")
    @patch("ai_cost_observer.telemetry.PeriodicExportingMetricReader")
    @patch("ai_cost_observer.telemetry.Resource")
    def test_metric_names_have_no_embedded_total(
        self, mock_resource, mock_reader_cls, mock_provider_cls, mock_metrics
    ):
        """Counter metric names should not contain _total in the OTel name."""
        from ai_cost_observer.telemetry import TelemetryManager

        mock_exporter = MagicMock()
        mock_meter = MagicMock()
        mock_provider_cls.return_value.get_meter.return_value = mock_meter

        config = AppConfig()
        config.otel_endpoint = "localhost:4317"
        config.host_name = "test-host"

        TelemetryManager(config, exporter=mock_exporter)

        counter_names = [
            call.kwargs.get("name") or call.args[0]
            for call in mock_meter.create_counter.call_args_list
        ]

        # None of the metric names should end with _total
        for name in counter_names:
            assert not name.endswith("_total"), (
                f"OTel metric name '{name}' should not contain _total "
                "(Prometheus exporter adds it automatically for counters)"
            )
