"""Tests for detection config fixes: removed fake desktop apps, CLI dedup, codex pattern tightening.

Covers:
- Removed entries from ai_apps (Gemini, Codex, DALL-E via ChatGPT)
- CLI detector PID-based dedup with desktop detector (prevents Ollama double-counting)
- CLI detector case-insensitive name-based fallback dedup (when no desktop_detector)
- Tightened codex-cli cmdline_patterns to avoid Electron false positives
- No duplicate ChatGPT entries after DALL-E removal
"""

from __future__ import annotations

import platform
from unittest.mock import MagicMock, PropertyMock

import pytest

from ai_cost_observer.config import AppConfig, _load_builtin_ai_config
from ai_cost_observer.detectors.cli import CLIDetector

_OS_KEY = "macos" if platform.system() == "Darwin" else "windows"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _config_with_real_data() -> AppConfig:
    """Build an AppConfig populated with the real ai_config.yaml data."""
    builtin = _load_builtin_ai_config()
    config = AppConfig()
    config.ai_apps = builtin.get("ai_apps", [])
    config.ai_domains = builtin.get("ai_domains", [])
    config.ai_cli_tools = builtin.get("ai_cli_tools", [])
    return config


def _fake_process(pid: int, name: str, cmdline: list[str] | None = None) -> MagicMock:
    """Create a mock psutil process with given info fields."""
    proc = MagicMock()
    proc.info = {"pid": pid, "name": name, "cmdline": cmdline or []}
    return proc


def _make_telemetry() -> MagicMock:
    """Create a minimal mock TelemetryManager for CLIDetector."""
    tm = MagicMock()
    tm.cli_running = MagicMock()
    tm.set_running_cli = MagicMock()
    tm.cli_active_duration = MagicMock()
    tm.cli_estimated_cost = MagicMock()
    return tm


def _make_desktop_detector(claimed_pids: set[int] | None = None) -> MagicMock:
    """Create a mock DesktopDetector that exposes claimed_pids."""
    dd = MagicMock()
    type(dd).claimed_pids = PropertyMock(return_value=claimed_pids or set())
    return dd


# ---------------------------------------------------------------------------
# 1-3: Verify removed desktop app entries
# ---------------------------------------------------------------------------

class TestRemovedDesktopApps:
    """Verify that fake desktop apps were removed from ai_config.yaml."""

    def test_no_gemini_in_desktop_apps(self):
        """Gemini is not in ai_apps (no standalone desktop app) but exists as gemini-cli in ai_cli_tools."""
        config = _config_with_real_data()

        desktop_app_names = [app["name"] for app in config.ai_apps]
        assert "Gemini" not in desktop_app_names, "Gemini should not be in ai_apps (it is CLI-only)"

        cli_tool_names = [tool["name"] for tool in config.ai_cli_tools]
        assert "gemini-cli" in cli_tool_names, "gemini-cli should exist in ai_cli_tools"

    def test_no_codex_in_desktop_apps(self):
        """Codex is not in ai_apps (no standalone desktop app) but exists as codex-cli in ai_cli_tools."""
        config = _config_with_real_data()

        desktop_app_names = [app["name"] for app in config.ai_apps]
        assert "Codex" not in desktop_app_names, "Codex should not be in ai_apps (it is CLI-only)"

        cli_tool_names = [tool["name"] for tool in config.ai_cli_tools]
        assert "codex-cli" in cli_tool_names, "codex-cli should exist in ai_cli_tools"

    def test_no_dalle_in_desktop_apps(self):
        """DALL-E (via ChatGPT) is not in ai_apps (same process as ChatGPT, can't distinguish)."""
        config = _config_with_real_data()

        desktop_app_names = [app["name"] for app in config.ai_apps]
        assert "DALL-E (via ChatGPT)" not in desktop_app_names, (
            "DALL-E (via ChatGPT) should not be in ai_apps (indistinguishable from ChatGPT)"
        )


# ---------------------------------------------------------------------------
# 4-5: CLI detector PID-based dedup with desktop detector
# ---------------------------------------------------------------------------

class TestCLIDesktopDedup:
    """CLI detector skips PIDs already claimed by the desktop detector."""

    def test_cli_skips_pid_claimed_by_desktop(self, mocker):
        """PID claimed by desktop detector is skipped by CLI detector (PID-based dedup)."""
        config = _config_with_real_data()
        telemetry = _make_telemetry()
        desktop = _make_desktop_detector(claimed_pids={100})
        detector = CLIDetector(config, telemetry, desktop_detector=desktop)

        # PID 100 is "Claude" GUI, already claimed by desktop -- CLI should skip it
        procs = [_fake_process(100, "Claude")]
        mocker.patch("psutil.process_iter", return_value=procs)

        detector.scan()

        # Bug H1: check snapshot instead of .add()
        snapshot = telemetry.set_running_cli.call_args[0][0]
        assert len(snapshot) == 0

    def test_cli_detects_unclaimed_pid(self, mocker):
        """PID NOT claimed by desktop detector is detected by CLI detector."""
        config = _config_with_real_data()
        telemetry = _make_telemetry()
        desktop = _make_desktop_detector(claimed_pids={100})  # only PID 100 claimed
        detector = CLIDetector(config, telemetry, desktop_detector=desktop)

        # PID 200 is "claude" CLI binary, NOT claimed by desktop
        procs = [_fake_process(200, "claude")]
        mocker.patch("psutil.process_iter", return_value=procs)

        detector.scan()

        # Bug H1: check snapshot instead of .add()
        snapshot = telemetry.set_running_cli.call_args[0][0]
        assert "claude-code" in snapshot

    def test_ollama_not_double_counted_via_pid_dedup(self, mocker):
        """Ollama PID claimed by desktop is NOT double-counted by CLI (the core bug fix).

        This is the exact scenario from the bug report: Ollama PID 1129 is detected
        by both desktop (as 'Ollama (GUI)') and CLI (as 'ollama'). The desktop
        detector claims the PID first, and the CLI detector skips it.
        """
        config = _config_with_real_data()
        telemetry = _make_telemetry()
        # Desktop has already claimed PIDs 847 and 1129 for Ollama (GUI)
        desktop = _make_desktop_detector(claimed_pids={847, 1129})
        detector = CLIDetector(config, telemetry, desktop_detector=desktop)

        # psutil returns "ollama" (lowercase) for the same PID -- CLI should skip it
        procs = [_fake_process(1129, "ollama"), _fake_process(847, "ollama")]
        mocker.patch("psutil.process_iter", return_value=procs)

        detector.scan()

        # CLI detector should NOT detect these PIDs (already claimed by desktop)
        snapshot = telemetry.set_running_cli.call_args[0][0]
        assert len(snapshot) == 0

    def test_ollama_name_dedup_fallback_without_desktop_detector(self, mocker):
        """Without a desktop_detector, name-based dedup (case-insensitive) prevents
        double-counting for Ollama-like cases where the process name matches a
        desktop app regardless of case.
        """
        config = _config_with_real_data()
        telemetry = _make_telemetry()
        # No desktop_detector -- falls back to case-insensitive name dedup
        detector = CLIDetector(config, telemetry)

        # "ollama" lowercase matches desktop "Ollama" case-insensitively -- skipped
        procs = [_fake_process(400, "ollama")]
        mocker.patch("psutil.process_iter", return_value=procs)

        detector.scan()

        # Bug H1: check snapshot
        snapshot = telemetry.set_running_cli.call_args[0][0]
        assert len(snapshot) == 0

    def test_claude_cli_detected_alongside_desktop_via_pid_dedup(self, mocker):
        """Claude CLI (different PID) is detected even when Claude GUI is running.

        PID-based dedup correctly distinguishes the GUI (PID 100) from the CLI
        (PID 200) even though both process names are 'claude'/'Claude'.
        """
        config = _config_with_real_data()
        telemetry = _make_telemetry()
        desktop = _make_desktop_detector(claimed_pids={100})  # GUI PID
        detector = CLIDetector(config, telemetry, desktop_detector=desktop)

        # PID 100 is GUI (claimed), PID 200 is CLI (not claimed)
        procs = [_fake_process(100, "Claude"), _fake_process(200, "claude")]
        mocker.patch("psutil.process_iter", return_value=procs)

        detector.scan()

        # Bug H1: check snapshot
        snapshot = telemetry.set_running_cli.call_args[0][0]
        assert "claude-code" in snapshot


# ---------------------------------------------------------------------------
# 6: Tightened codex-cli cmdline_patterns
# ---------------------------------------------------------------------------

class TestCodexCmdlinePatterns:
    """Codex-cli cmdline_patterns ('/codex', 'codex ') avoid false positives from old broad pattern."""

    def test_codex_cmdline_pattern_no_false_positive(self, mocker):
        """A process with 'codecov' or other 'codex'-substring words in cmdline is NOT matched.

        The old pattern ["codex"] would match any occurrence (e.g. "codecoverage").
        The new patterns ["/codex", "codex "] require either a path separator or trailing space.
        """
        config = _config_with_real_data()
        telemetry = _make_telemetry()
        detector = CLIDetector(config, telemetry)

        # Process whose cmdline contains "codex" as a substring but NOT as "/codex" or "codex "
        # e.g. a test runner argument like "--codecov" or a module named "mycodex_utils"
        false_positive_proc = _fake_process(
            500,
            "node",
            cmdline=[
                "/usr/local/bin/node",
                "run-tests",
                "--coverage-tool=codecoverage",
            ],
        )
        mocker.patch("psutil.process_iter", return_value=[false_positive_proc])

        detector.scan()

        # "codecoverage" does NOT contain "/codex" or "codex " -- should not match
        snapshot = telemetry.set_running_cli.call_args[0][0]
        assert "codex-cli" not in snapshot

        # Reset
        telemetry.set_running_cli.reset_mock()

        # Actual codex CLI usage: "codex chat" contains "codex " (with trailing space)
        codex_proc = _fake_process(
            600,
            "node",
            cmdline=["/usr/local/bin/node", "/usr/local/bin/codex", "chat"],
        )
        mocker.patch("psutil.process_iter", return_value=[codex_proc])

        detector.scan()

        # Bug H1: check snapshot
        snapshot = telemetry.set_running_cli.call_args[0][0]
        assert "codex-cli" in snapshot

    def test_codex_cmdline_pattern_matches_path_prefix(self, mocker):
        """A cmdline containing '/codex' (absolute path to codex binary) IS matched."""
        config = _config_with_real_data()
        telemetry = _make_telemetry()
        detector = CLIDetector(config, telemetry)

        # cmdline: "/usr/local/bin/codex" -- contains "/codex"
        codex_proc = _fake_process(
            700,
            "node",
            cmdline=["/usr/local/bin/codex"],
        )
        mocker.patch("psutil.process_iter", return_value=[codex_proc])

        detector.scan()

        # Bug H1: check snapshot
        snapshot = telemetry.set_running_cli.call_args[0][0]
        assert "codex-cli" in snapshot

    def test_codex_cmdline_patterns_are_tightened(self):
        """Verify the actual codex-cli patterns in config are ['/codex', 'codex '], not the old broad ['codex']."""
        config = _config_with_real_data()
        codex_tool = None
        for tool in config.ai_cli_tools:
            if tool["name"] == "codex-cli":
                codex_tool = tool
                break

        assert codex_tool is not None, "codex-cli should exist in ai_cli_tools"
        patterns = codex_tool.get("cmdline_patterns", [])
        assert "/codex" in patterns, "codex-cli should have '/codex' cmdline pattern"
        assert "codex " in patterns, "codex-cli should have 'codex ' cmdline pattern"
        # The old broad pattern should not be present as the sole match
        assert patterns != ["codex"], "codex-cli patterns should not be the old broad ['codex']"


# ---------------------------------------------------------------------------
# 7: No duplicate ChatGPT desktop entries
# ---------------------------------------------------------------------------

class TestNoDuplicateChatGPT:
    """Verify only one ai_apps entry maps to the ChatGPT process name."""

    def test_chatgpt_not_double_counted(self):
        """Only one entry in ai_apps has process name 'ChatGPT' -- no DALL-E duplicate."""
        config = _config_with_real_data()

        chatgpt_entries = []
        for app in config.ai_apps:
            proc_names_macos = app.get("process_names", {}).get("macos", [])
            proc_names_windows = app.get("process_names", {}).get("windows", [])
            all_proc_names = proc_names_macos + proc_names_windows
            if "ChatGPT" in all_proc_names or "ChatGPT.exe" in all_proc_names:
                chatgpt_entries.append(app["name"])

        assert len(chatgpt_entries) == 1, (
            f"Expected exactly 1 ai_apps entry with ChatGPT process name, "
            f"found {len(chatgpt_entries)}: {chatgpt_entries}"
        )
        assert chatgpt_entries[0] == "ChatGPT"
