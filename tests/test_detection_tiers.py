"""Tests for the 3-tier detection system (process name, exe path, cmdline).

Validates detection of AI desktop apps and CLI tools using the real ai_config.yaml.
Covers positive detection, negative (no false positives), and edge cases.
"""

from __future__ import annotations

from unittest.mock import MagicMock, Mock, patch

import psutil
import pytest

from ai_cost_observer.config import AppConfig, _load_builtin_ai_config
from ai_cost_observer.detectors.cli import CLIDetector
from ai_cost_observer.detectors.desktop import DesktopDetector

# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def real_config() -> AppConfig:
    """Load real ai_config.yaml into AppConfig (no side effects)."""
    builtin = _load_builtin_ai_config()
    config = AppConfig()
    config.ai_apps = builtin.get("ai_apps", [])
    config.ai_cli_tools = builtin.get("ai_cli_tools", [])
    return config


@pytest.fixture
def desktop_telemetry() -> Mock:
    """Mock TelemetryManager for desktop detector."""
    tm = Mock()
    tm.set_running_apps = Mock()
    tm.app_active_duration = Mock()
    tm.app_active_duration.add = Mock()
    tm.app_estimated_cost = Mock()
    tm.app_estimated_cost.add = Mock()
    tm.app_cpu_usage = Mock()
    tm.app_cpu_usage.set = Mock()
    tm.app_memory_usage = Mock()
    tm.app_memory_usage.set = Mock()
    return tm


@pytest.fixture
def cli_telemetry() -> Mock:
    """Mock TelemetryManager for CLI detector."""
    tm = Mock()
    tm.set_running_cli = Mock()
    tm.cli_active_duration = Mock()
    tm.cli_active_duration.add = Mock()
    tm.cli_estimated_cost = Mock()
    tm.cli_estimated_cost.add = Mock()
    return tm


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _fake_proc(
    pid: int,
    name: str,
    exe: str | None = None,
    cmdline: list[str] | None = None,
) -> MagicMock:
    """Create a mock psutil process with proc.info dict."""
    proc = MagicMock()
    proc.info = {"pid": pid, "name": name, "exe": exe, "cmdline": cmdline or []}
    proc.cpu_percent.return_value = 5.0
    proc.memory_info.return_value = Mock(rss=100 * 1024 * 1024)
    return proc


def _desktop_detected_apps(config, telemetry, procs) -> dict:
    """Run a desktop scan with given processes and return detected apps."""
    with patch(
        "ai_cost_observer.detectors.desktop.get_foreground_app", return_value=None
    ):
        detector = DesktopDetector(config, telemetry)
        with patch("psutil.process_iter", return_value=procs):
            detector.scan()
    return telemetry.set_running_apps.call_args[0][0]


def _cli_detected_tools(config, telemetry, procs) -> dict:
    """Run a CLI scan with given processes and return detected tools."""
    detector = CLIDetector(config, telemetry)
    with patch("psutil.process_iter", return_value=procs):
        detector.scan()
    return telemetry.set_running_cli.call_args[0][0]


# ═══════════════════════════════════════════════════════════════════════════════
# Positive tests — detection expected
# ═══════════════════════════════════════════════════════════════════════════════


class TestPositiveDetection:
    """10 tests verifying that known AI apps/tools are correctly detected."""

    def test_chatgpt_helper_detected(self, real_config, desktop_telemetry):
        """D1: ChatGPTHelper (macOS helper process) detected as ChatGPT (Tier 1)."""
        procs = [
            _fake_proc(
                100,
                "ChatGPTHelper",
                "/Applications/ChatGPT.app/Contents/MacOS/ChatGPTHelper",
            )
        ]
        snapshot = _desktop_detected_apps(real_config, desktop_telemetry, procs)
        assert "ChatGPT" in snapshot

    def test_claude_desktop_exe_path(self, real_config, desktop_telemetry):
        """D2: chrome-native-host from Claude.app detected as Claude (Tier 2)."""
        procs = [
            _fake_proc(
                101,
                "chrome-native-host",
                "/Applications/Claude.app/Contents/Frameworks/chrome-native-host",
            )
        ]
        snapshot = _desktop_detected_apps(real_config, desktop_telemetry, procs)
        assert "Claude" in snapshot

    def test_comet_detected(self, real_config, desktop_telemetry):
        """D3: Comet (Perplexity rebrand) detected as Perplexity (Tier 1)."""
        procs = [
            _fake_proc(
                102, "Comet", "/Applications/Comet.app/Contents/MacOS/Comet"
            )
        ]
        snapshot = _desktop_detected_apps(real_config, desktop_telemetry, procs)
        assert "Perplexity" in snapshot

    def test_copilot_language_server(self, real_config, desktop_telemetry):
        """D4: copilot-language-server detected as JetBrains AI (Tier 1)."""
        procs = [
            _fake_proc(
                103,
                "copilot-language-server",
                "/Users/user/.copilot-agent/bin/copilot-language-server",
            )
        ]
        snapshot = _desktop_detected_apps(real_config, desktop_telemetry, procs)
        assert "JetBrains AI" in snapshot

    def test_superwhisper_detected(self, real_config, desktop_telemetry):
        """D5: superwhisper detected (Tier 1)."""
        procs = [
            _fake_proc(
                104,
                "superwhisper",
                "/Applications/superwhisper.app/Contents/MacOS/superwhisper",
            )
        ]
        snapshot = _desktop_detected_apps(real_config, desktop_telemetry, procs)
        assert "superwhisper" in snapshot

    def test_claude_code_version_name(self, real_config, cli_telemetry):
        """C1: proc.name()=2.1.39 (version!) detected via exe path (Tier 2)."""
        procs = [
            _fake_proc(
                200,
                "2.1.39",
                "/Users/user/.local/share/claude/versions/2.1.39",
                ["claude", "--resume", "49958b5c"],
            )
        ]
        snapshot = _cli_detected_tools(real_config, cli_telemetry, procs)
        assert "claude-code" in snapshot

    def test_codex_cli_arch_name(self, real_config, cli_telemetry):
        """C2: codex-aarch64-apple-darwin detected as codex-cli (Tier 1)."""
        procs = [
            _fake_proc(
                201,
                "codex-aarch64-apple-darwin",
                "/Users/user/.codex/codex-aarch64-apple-darwin",
            )
        ]
        snapshot = _cli_detected_tools(real_config, cli_telemetry, procs)
        assert "codex-cli" in snapshot

    def test_gemini_node_cmdline(self, real_config, cli_telemetry):
        """C3: node running gemini-cli detected via cmdline[:3] (Tier 3)."""
        procs = [
            _fake_proc(
                202,
                "node",
                "/usr/local/bin/node",
                ["node", "/path/gemini-cli/index.js"],
            )
        ]
        snapshot = _cli_detected_tools(real_config, cli_telemetry, procs)
        assert "gemini-cli" in snapshot

    def test_vibe_python_exe_path(self, real_config, cli_telemetry):
        """C4: python from uv/tools/mistral-vibe detected as vibe."""
        procs = [
            _fake_proc(
                203,
                "python",
                "/Users/user/.local/share/uv/tools/mistral-vibe/lib/python3.12/bin/python",
                ["python3", "-m", "vibe"],
            )
        ]
        snapshot = _cli_detected_tools(real_config, cli_telemetry, procs)
        assert "vibe" in snapshot

    def test_gh_copilot_detected(self, real_config, cli_telemetry):
        """C5: gh copilot suggest detected as github-copilot-cli (Tier 3)."""
        procs = [
            _fake_proc(
                204,
                "gh",
                "/usr/local/bin/gh",
                ["gh", "copilot", "suggest"],
            )
        ]
        snapshot = _cli_detected_tools(real_config, cli_telemetry, procs)
        assert "github-copilot-cli" in snapshot


# ═══════════════════════════════════════════════════════════════════════════════
# Negative tests — NO detection expected
# ═══════════════════════════════════════════════════════════════════════════════


class TestNegativeDetection:
    """5 tests verifying that non-AI processes are NOT falsely detected."""

    def test_gh_alone_not_detected(self, real_config, cli_telemetry):
        """C5: gh without copilot NOT detected (no false positive)."""
        procs = [
            _fake_proc(300, "gh", "/usr/local/bin/gh", ["gh", "pr", "list"])
        ]
        snapshot = _cli_detected_tools(real_config, cli_telemetry, procs)
        assert "github-copilot-cli" not in snapshot

    def test_node_random_not_detected(self, real_config, cli_telemetry):
        """Random node process (webpack) NOT detected."""
        procs = [
            _fake_proc(
                301, "node", "/usr/local/bin/node", ["node", "webpack", "serve"]
            )
        ]
        snapshot = _cli_detected_tools(real_config, cli_telemetry, procs)
        assert len(snapshot) == 0

    def test_python_random_not_detected(self, real_config, cli_telemetry):
        """Random python process (Django) NOT detected."""
        procs = [
            _fake_proc(
                302,
                "python",
                "/usr/bin/python3",
                ["python3", "manage.py", "runserver"],
            )
        ]
        snapshot = _cli_detected_tools(real_config, cli_telemetry, procs)
        assert len(snapshot) == 0

    def test_system_cursor_not_detected(self, real_config, desktop_telemetry):
        """CursorUIViewService in /System/Library/ NOT detected (system filter)."""
        procs = [
            _fake_proc(
                303,
                "CursorUIViewService",
                "/System/Library/Frameworks/UIKit.framework/CursorUIViewService",
            )
        ]
        snapshot = _desktop_detected_apps(real_config, desktop_telemetry, procs)
        assert "Cursor" not in snapshot

    def test_chrome_native_not_claude(self, real_config, desktop_telemetry):
        """chrome-native-host from Arc.app NOT detected as Claude."""
        procs = [
            _fake_proc(
                304,
                "chrome-native-host",
                "/Applications/Arc.app/Contents/Frameworks/chrome-native-host",
            )
        ]
        snapshot = _desktop_detected_apps(real_config, desktop_telemetry, procs)
        assert "Claude" not in snapshot


# ═══════════════════════════════════════════════════════════════════════════════
# Edge case tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """5 edge case and non-regression tests."""

    def test_exe_none_no_crash(self, real_config, desktop_telemetry):
        """proc.info['exe'] = None does not crash the desktop scanner."""
        procs = [_fake_proc(400, "SomeProcess", None)]
        # Should not raise
        _desktop_detected_apps(real_config, desktop_telemetry, procs)

    def test_cmdline_empty_no_crash(self, real_config, cli_telemetry):
        """proc.info['cmdline'] = [] or None does not crash the CLI scanner."""
        procs = [
            _fake_proc(401, "node", "/usr/local/bin/node", []),
            _fake_proc(402, "python", "/usr/bin/python3", None),
        ]
        # Should not raise
        _cli_detected_tools(real_config, cli_telemetry, procs)

    def test_exe_access_denied(self, real_config, cli_telemetry):
        """psutil.AccessDenied on proc.exe() does not crash the CLI scanner."""
        proc = MagicMock()
        proc.info = {"pid": 403, "name": "mystery", "exe": None, "cmdline": None}
        proc.exe.side_effect = psutil.AccessDenied(pid=403)
        # Should not raise
        _cli_detected_tools(real_config, cli_telemetry, [proc])

    def test_existing_ollama_still_works(self, real_config, desktop_telemetry):
        """Non-regression: Ollama GUI still detected."""
        procs = [
            _fake_proc(
                404, "Ollama", "/Applications/Ollama.app/Contents/MacOS/Ollama"
            )
        ]
        snapshot = _desktop_detected_apps(real_config, desktop_telemetry, procs)
        assert "Ollama (GUI)" in snapshot

    def test_existing_idea_still_works(self, real_config, desktop_telemetry):
        """Non-regression: IntelliJ IDEA still detected as JetBrains AI."""
        procs = [
            _fake_proc(
                405,
                "idea",
                "/Applications/IntelliJ IDEA.app/Contents/MacOS/idea",
            )
        ]
        snapshot = _desktop_detected_apps(real_config, desktop_telemetry, procs)
        assert "JetBrains AI" in snapshot
