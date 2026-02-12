"""Extended shell history tests — bash, PowerShell, malformed zsh, empty files."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from ai_cost_observer.config import AppConfig
from ai_cost_observer.detectors.shell_history import ShellHistoryParser


@pytest.fixture
def shell_config(tmp_path: Path) -> AppConfig:
    """AppConfig for shell history testing."""
    config = AppConfig()
    config.state_dir = tmp_path / "state"
    config.state_dir.mkdir(parents=True, exist_ok=True)
    config.ai_cli_tools = [
        {
            "name": "Claude-CLI",
            "command_patterns": ["claude-code", "claude"],
        },
        {
            "name": "Ollama",
            "command_patterns": ["ollama"],
        },
        {
            "name": "Codex",
            "command_patterns": ["codex"],
        },
    ]
    return config


@pytest.fixture
def shell_telemetry() -> Mock:
    """Mock telemetry for shell history tests."""
    telemetry = Mock()
    telemetry.cli_command_count = Mock()
    telemetry.cli_command_count.add = Mock()
    return telemetry


class TestBashHistoryParsing:
    """Test bash history parsing (plain format, one command per line)."""

    def test_bash_basic_parsing(self, shell_config, shell_telemetry, tmp_path):
        """Bash history with plain one-command-per-line format is parsed."""
        history_file = tmp_path / ".bash_history"
        history_file.write_text(
            "ollama run llama3\n"
            "ls -la\n"
            "claude-code -m 'fix bug'\n"
            "cd /tmp\n"
            "ollama pull qwen\n",
            encoding="utf-8",
        )

        parser = ShellHistoryParser(shell_config, shell_telemetry)
        parser._get_history_files = lambda: [(str(history_file), "bash")]

        parser.scan()

        assert shell_telemetry.cli_command_count.add.call_count == 2
        calls = {
            call.args[1]["cli.name"]: call.args[0]
            for call in shell_telemetry.cli_command_count.add.call_args_list
        }
        assert calls["Ollama"] == 2
        assert calls["Claude-CLI"] == 1

    def test_bash_empty_lines_ignored(self, shell_config, shell_telemetry, tmp_path):
        """Empty and whitespace-only lines in bash history are ignored."""
        history_file = tmp_path / ".bash_history"
        history_file.write_text(
            "\n\n  \nollama run test\n\n",
            encoding="utf-8",
        )

        parser = ShellHistoryParser(shell_config, shell_telemetry)
        parser._get_history_files = lambda: [(str(history_file), "bash")]

        parser.scan()

        shell_telemetry.cli_command_count.add.assert_called_once_with(1, {"cli.name": "Ollama"})


class TestPowerShellHistoryParsing:
    """Test PowerShell ConsoleHost_history.txt format."""

    def test_powershell_basic_parsing(self, shell_config, shell_telemetry, tmp_path):
        """PowerShell history is one command per line, same as bash."""
        history_file = tmp_path / "ConsoleHost_history.txt"
        history_file.write_text(
            "Get-Process\n"
            "ollama run mistral\n"
            "dir C:\\Users\n"
            "codex generate code\n",
            encoding="utf-8",
        )

        parser = ShellHistoryParser(shell_config, shell_telemetry)
        # PowerShell uses "powershell" as shell_name but the parsing is same as bash
        parser._get_history_files = lambda: [(str(history_file), "powershell")]

        parser.scan()

        calls = {
            call.args[1]["cli.name"]: call.args[0]
            for call in shell_telemetry.cli_command_count.add.call_args_list
        }
        assert calls["Ollama"] == 1
        assert calls["Codex"] == 1


class TestMalformedZshHistory:
    """Test handling of malformed zsh history entries."""

    def test_malformed_zsh_entries_skipped(self, shell_config, shell_telemetry, tmp_path):
        """Malformed zsh entries (missing semicolon, etc.) are handled gracefully."""
        history_file = tmp_path / ".zsh_history"
        history_file.write_text(
            ": 1629410103:0;ollama run ok\n"
            ": invalid_timestamp\n"  # missing semicolon
            "bare command ollama pull\n"  # not extended format, treated as plain
            ": 1629410105:0;claude -m 'fix'\n"
            "",
            encoding="utf-8",
        )

        parser = ShellHistoryParser(shell_config, shell_telemetry)
        parser._get_history_files = lambda: [(str(history_file), "zsh")]

        parser.scan()

        calls = {
            call.args[1]["cli.name"]: call.args[0]
            for call in shell_telemetry.cli_command_count.add.call_args_list
        }
        # "ollama run ok" (zsh extended) + "bare command ollama pull" (plain line)
        assert calls["Ollama"] == 2
        assert calls["Claude-CLI"] == 1

    def test_zsh_multiline_commands(self, shell_config, shell_telemetry, tmp_path):
        """Lines without zsh extended header are treated as plain commands."""
        history_file = tmp_path / ".zsh_history"
        history_file.write_text(
            ": 1629410103:0;echo hello\n"
            "ollama run test\n"  # bare line (continuation or fallback)
            ": 1629410104:0;claude prompt\n",
            encoding="utf-8",
        )

        parser = ShellHistoryParser(shell_config, shell_telemetry)
        parser._get_history_files = lambda: [(str(history_file), "zsh")]

        parser.scan()

        calls = {
            call.args[1]["cli.name"]: call.args[0]
            for call in shell_telemetry.cli_command_count.add.call_args_list
        }
        assert calls["Ollama"] == 1
        assert calls["Claude-CLI"] == 1


class TestEmptyHistoryFiles:
    """Test behavior with empty history files."""

    def test_empty_file_no_metrics(self, shell_config, shell_telemetry, tmp_path):
        """An empty history file produces no metrics and no errors."""
        history_file = tmp_path / ".bash_history"
        history_file.write_text("", encoding="utf-8")

        parser = ShellHistoryParser(shell_config, shell_telemetry)
        parser._get_history_files = lambda: [(str(history_file), "bash")]

        parser.scan()

        shell_telemetry.cli_command_count.add.assert_not_called()

    def test_nonexistent_file_no_crash(self, shell_config, shell_telemetry, tmp_path):
        """A missing history file path does not crash the parser."""
        parser = ShellHistoryParser(shell_config, shell_telemetry)
        parser._get_history_files = lambda: [(str(tmp_path / "nonexistent"), "bash")]

        parser.scan()  # Should not raise

        shell_telemetry.cli_command_count.add.assert_not_called()

    def test_whitespace_only_file(self, shell_config, shell_telemetry, tmp_path):
        """A file with only whitespace produces no metrics."""
        history_file = tmp_path / ".bash_history"
        history_file.write_text("   \n  \n\n", encoding="utf-8")

        parser = ShellHistoryParser(shell_config, shell_telemetry)
        parser._get_history_files = lambda: [(str(history_file), "bash")]

        parser.scan()

        shell_telemetry.cli_command_count.add.assert_not_called()
