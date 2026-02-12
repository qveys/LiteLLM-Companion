"""Incremental shell history parser — counts AI CLI commands from zsh/bash/PowerShell history."""

from __future__ import annotations

import os
import platform
import re
from pathlib import Path

from loguru import logger

from ai_cost_observer.config import AppConfig
from ai_cost_observer.telemetry import TelemetryManager


class ShellHistoryParser:
    """Parses shell history files incrementally, counting AI tool commands."""

    def __init__(self, config: AppConfig, telemetry: TelemetryManager) -> None:
        self.config = config
        self.telemetry = telemetry
        self._offsets: dict[str, int] = {}

        # Build command pattern → tool name lookup
        self._patterns: list[tuple[re.Pattern, dict]] = []
        for tool in config.ai_cli_tools:
            for pattern_str in tool.get("command_patterns", []):
                pattern = re.compile(r"(?:^|;|\||\s)" + re.escape(pattern_str) + r"(?:\s|$)")
                self._patterns.append((pattern, tool))

        # Load persisted offsets
        self._offset_file = config.state_dir / "shell_history_offsets.txt"
        self._load_offsets()

    def scan(self) -> None:
        """Parse new history entries and update command count metrics."""
        history_files = self._get_history_files()

        for path_str, shell_name in history_files:
            path = Path(path_str).expanduser()
            if not path.exists():
                continue

            try:
                new_commands = self._read_new_lines(path, shell_name)
                if new_commands:
                    self._count_and_report(new_commands)
            except PermissionError:
                logger.warning("Permission denied reading {}", path)
            except Exception:
                logger.opt(exception=True).warning("Error parsing {}", path)

        self._save_offsets()

    def _get_history_files(self) -> list[tuple[str, str]]:
        """Return list of (path, shell_name) for history files on this OS."""
        files = []
        if platform.system() == "Windows":
            ps_history = os.path.join(
                os.environ.get("APPDATA", ""),
                "Microsoft",
                "Windows",
                "PowerShell",
                "PSReadLine",
                "ConsoleHost_history.txt",
            )
            files.append((ps_history, "powershell"))
        else:
            files.append(("~/.zsh_history", "zsh"))
            files.append(("~/.bash_history", "bash"))
        return files

    def _read_new_lines(self, path: Path, shell_name: str) -> list[str]:
        """Read only new lines since last offset."""
        key = str(path)
        offset = self._offsets.get(key, 0)

        try:
            file_size = path.stat().st_size
        except OSError:
            return []

        if file_size < offset:
            # File was truncated or rotated — reset
            offset = 0

        if file_size == offset:
            return []

        lines = []
        with open(path, "rb") as f:
            f.seek(offset)
            raw = f.read()
            self._offsets[key] = f.tell()

        text = raw.decode("utf-8", errors="replace")

        if shell_name == "zsh":
            # zsh extended history: `: timestamp:flags;command`
            for line in text.splitlines():
                if line.startswith(": ") and ";" in line:
                    _, _, cmd = line.partition(";")
                    lines.append(cmd.strip())
                elif line.strip():
                    lines.append(line.strip())
        else:
            # bash / powershell: one command per line
            for line in text.splitlines():
                stripped = line.strip()
                if stripped:
                    lines.append(stripped)

        return lines

    def _count_and_report(self, commands: list[str]) -> None:
        """Count AI-related commands and report to telemetry."""
        counts: dict[str, tuple[int, dict]] = {}  # tool_name -> (count, tool_cfg)

        for cmd in commands:
            for pattern, tool_cfg in self._patterns:
                if pattern.search(cmd):
                    tool_name = tool_cfg["name"]
                    if tool_name in counts:
                        counts[tool_name] = (counts[tool_name][0] + 1, tool_cfg)
                    else:
                        counts[tool_name] = (1, tool_cfg)
                    break  # one match per command

        for tool_name, (count, tool_cfg) in counts.items():
            labels = {
                "cli.name": tool_name,
                "cli.category": tool_cfg.get("category", "unknown"),
            }
            self.telemetry.cli_command_count.add(count, labels)
            logger.debug("Shell history: {} new commands for {}", count, tool_name)

    def _load_offsets(self) -> None:
        """Load byte offsets from state file."""
        if self._offset_file.exists():
            try:
                for line in self._offset_file.read_text(encoding="utf-8").splitlines():
                    if "=" in line:
                        path_part, offset_str = line.rsplit("=", 1)
                        self._offsets[path_part] = int(offset_str)
            except Exception:
                logger.opt(exception=True).debug("Failed to load shell history offsets")

    def _save_offsets(self) -> None:
        """Persist byte offsets to state file."""
        try:
            self._offset_file.parent.mkdir(parents=True, exist_ok=True)
            lines = [f"{path}={offset}" for path, offset in self._offsets.items()]
            self._offset_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except Exception:
            logger.opt(exception=True).debug("Failed to save shell history offsets")
