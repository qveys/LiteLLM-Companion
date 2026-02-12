"""Tests for the shell history parser."""
import pytest
from pathlib import Path
from unittest.mock import Mock
from ai_cost_observer.config import AppConfig
from ai_cost_observer.detectors.shell_history import ShellHistoryParser

@pytest.fixture
def mock_config(tmp_path: Path) -> AppConfig:
    """Provides a mock AppConfig for testing."""
    config = AppConfig()
    config.state_dir = tmp_path / "state"
    config.ai_cli_tools = [
        {
            "name": "Claude-CLI",
            "command_patterns": ["claude-code", "claude"],
        },
        {
            "name": "Ollama",
            "command_patterns": ["ollama"],
        },
    ]
    return config

@pytest.fixture
def mock_telemetry() -> Mock:
    """Provides a mock TelemetryManager."""
    telemetry = Mock()
    telemetry.cli_command_count = Mock()
    telemetry.cli_command_count.add = Mock()
    return telemetry

def test_zsh_history_parsing(mock_config: AppConfig, mock_telemetry: Mock, tmp_path: Path):
    """Test parsing of zsh-style extended history."""
    history_content = """
: 1629410103:0;claude-code -m 'Fix the thing'
ollama run mistral
: 1629410105:0;claude -p 'another prompt'
ls -la
ollama pull qwen
"""
    history_file = tmp_path / ".zsh_history"
    history_file.write_text(history_content.strip(), encoding="utf-8")

    parser = ShellHistoryParser(mock_config, mock_telemetry)
    # Patch the discovery to only find our test file
    parser._get_history_files = lambda: [(str(history_file), "zsh")]

    parser.scan()

    # Verify that the mock's 'add' method was called correctly
    # We expect two calls: one for Claude-CLI (count=2) and one for Ollama (count=2)
    assert mock_telemetry.cli_command_count.add.call_count == 2
    
    # Check the call arguments
    call_args_list = mock_telemetry.cli_command_count.add.call_args_list
    
    claude_call = [call for call in call_args_list if call.args[1]["cli.name"] == "Claude-CLI"]
    assert len(claude_call) == 1
    assert claude_call[0].args[0] == 2 # count for Claude-CLI

    ollama_call = [call for call in call_args_list if call.args[1]["cli.name"] == "Ollama"]
    assert len(ollama_call) == 1
    assert ollama_call[0].args[0] == 2 # count for Ollama

def test_incremental_parsing(mock_config: AppConfig, mock_telemetry: Mock, tmp_path: Path):
    """Test that only new commands are parsed on subsequent scans."""
    history_content_v1 = "ollama run mistral\n"
    history_file = tmp_path / ".bash_history"
    history_file.write_text(history_content_v1, encoding="utf-8")

    parser = ShellHistoryParser(mock_config, mock_telemetry)
    parser._get_history_files = lambda: [(str(history_file), "bash")]
    
    # First scan
    parser.scan()
    
    # It should have been called once for Ollama with a count of 1
    mock_telemetry.cli_command_count.add.assert_called_once_with(1, {"cli.name": "Ollama"})
    
    # Reset the mock to check the next call
    mock_telemetry.cli_command_count.add.reset_mock()
    
    # Add new content to the history file
    history_content_v2 = "claude -p 'new feature'\n"
    with open(history_file, "a", encoding="utf-8") as f:
        f.write(history_content_v2)
        
    # Second scan
    parser.scan()
    
    # It should now be called once for Claude-CLI with a count of 1
    mock_telemetry.cli_command_count.add.assert_called_once_with(1, {"cli.name": "Claude-CLI"})


def test_cc_c_compiler_not_matched(mock_config: AppConfig, mock_telemetry: Mock, tmp_path: Path):
    """The C compiler 'cc' should NOT be matched as an AI CLI tool."""
    history_content = "cc main.c -o main\ncc -Wall -O2 hello.c\nmake all\n"
    history_file = tmp_path / ".bash_history"
    history_file.write_text(history_content, encoding="utf-8")

    parser = ShellHistoryParser(mock_config, mock_telemetry)
    parser._get_history_files = lambda: [(str(history_file), "bash")]

    parser.scan()

    # None of these should match any AI tool
    mock_telemetry.cli_command_count.add.assert_not_called()
