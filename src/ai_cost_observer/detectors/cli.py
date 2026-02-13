"""CLI AI tool detection — scans processes for AI CLI tools, tracks duration and cost."""

from __future__ import annotations

import platform
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import psutil
from loguru import logger

from ai_cost_observer.config import AppConfig
from ai_cost_observer.telemetry import TelemetryManager

if TYPE_CHECKING:
    from ai_cost_observer.detectors.desktop import DesktopDetector

_OS_KEY = "macos" if platform.system() == "Darwin" else "windows"


@dataclass
class _CLIState:
    """Tracks per-tool running state between scans."""

    pids: set[int] = field(default_factory=set)
    was_running: bool = False
    last_scan_time: float = 0.0


class CLIDetector:
    """Detects running AI CLI tools and tracks duration."""

    def __init__(
        self,
        config: AppConfig,
        telemetry: TelemetryManager,
        desktop_detector: DesktopDetector | None = None,
    ) -> None:
        self.config = config
        self.telemetry = telemetry
        self._state: dict[str, _CLIState] = {}
        self._desktop_detector = desktop_detector
        # Bug H1: track currently running tools for ObservableGauge callback
        self._running_tools: dict[str, dict] = {}  # tool_name -> labels

        # Build process name → tool config lookup
        self._process_map: dict[str, dict] = {}
        for tool in config.ai_cli_tools:
            for proc_name in tool.get("process_names", {}).get(_OS_KEY, []):
                self._process_map[proc_name.lower()] = tool

        # Build cmdline pattern → tool config lookup (for interpreted scripts)
        self._cmdline_patterns: dict[str, dict] = {}
        for tool in config.ai_cli_tools:
            for pattern in tool.get("cmdline_patterns", []):
                self._cmdline_patterns[pattern.lower()] = tool

        # Build exe path pattern → tool config lookup (Tier 2 matching)
        # Use list of tuples to avoid key collisions if multiple tools share a pattern.
        self._exe_patterns: list[tuple[str, dict]] = []
        for tool in config.ai_cli_tools:
            for pattern in tool.get("exe_path_patterns", []):
                self._exe_patterns.append((pattern.lower(), tool))

        # Desktop app process names (lowercased) — used as a fallback name-based dedup
        # when no desktop_detector reference is available for PID-based dedup.
        # Case-insensitive to handle tools like Ollama where psutil returns "ollama"
        # for both the GUI app (config: "Ollama") and CLI binary (config: "ollama").
        self._desktop_proc_lower: set[str] = set()
        for app in config.ai_apps:
            for proc_name in app.get("process_names", {}).get(_OS_KEY, []):
                self._desktop_proc_lower.add(proc_name.lower())

    def scan(self) -> None:
        """Run one scan cycle: detect CLI tools, update metrics."""
        now = time.monotonic()

        # PIDs already claimed by the desktop detector (primary dedup mechanism).
        # When available, PID-based dedup is precise and handles all cases correctly.
        desktop_pids: set[int] = set()
        has_pid_dedup = self._desktop_detector is not None
        if has_pid_dedup:
            desktop_pids = self._desktop_detector.claimed_pids

        found: dict[str, set[int]] = {}

        for proc in psutil.process_iter(["pid", "name", "exe", "cmdline"]):
            try:
                pid = proc.info["pid"]
                proc_name = proc.info["name"]
                if not proc_name:
                    continue

                # PID-based dedup: skip any PID already claimed by the desktop detector
                if pid in desktop_pids:
                    continue

                proc_name_lower = proc_name.lower()

                tool_cfg = None

                # Tier 1: match by process name
                if proc_name_lower in self._process_map:
                    # When PID-based dedup is active, it already filtered desktop PIDs
                    # above, so no additional name check is needed.
                    # When PID-based dedup is NOT available (no desktop_detector),
                    # fall back to case-insensitive name dedup to avoid double-counting.
                    if has_pid_dedup or proc_name_lower not in self._desktop_proc_lower:
                        tool_cfg = self._process_map[proc_name_lower]

                # Tier 2: match by exe path
                # Apply the same name-based dedup guard as Tier 1 to prevent
                # desktop apps from being claimed as CLI tools via exe path.
                if tool_cfg is None and self._exe_patterns and (
                    has_pid_dedup or proc_name_lower not in self._desktop_proc_lower
                ):
                    exe_path = proc.info.get("exe") or ""
                    if exe_path and not exe_path.startswith("/System/Library/"):
                        exe_lower = exe_path.lower()
                        for pattern, candidate in self._exe_patterns:
                            if pattern in exe_lower:
                                tool_cfg = candidate
                                break

                # Tier 3: match by cmdline for interpreted scripts (node, python)
                # Same dedup guard as Tier 1/2.
                if tool_cfg is None and self._cmdline_patterns and (
                    has_pid_dedup or proc_name_lower not in self._desktop_proc_lower
                ):
                    cmdline = proc.info.get("cmdline") or []
                    if cmdline:
                        cmdline_str = " ".join(cmdline[:3]).lower()
                        for pattern, candidate in self._cmdline_patterns.items():
                            if pattern in cmdline_str:
                                tool_cfg = candidate
                                break

                if tool_cfg:
                    tool_name = tool_cfg["name"]
                    if tool_name not in found:
                        found[tool_name] = set()
                    found[tool_name].add(pid)

            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
            except Exception:
                logger.opt(exception=True).debug("Error scanning CLI process")
                continue

        all_tools = set(found.keys()) | set(self._state.keys())

        for tool_name in all_tools:
            state = self._state.setdefault(tool_name, _CLIState())
            is_running = tool_name in found
            tool_cfg = self._find_tool_config(tool_name)
            if not tool_cfg:
                continue

            labels = {
                "cli.name": tool_name,
                "cli.category": tool_cfg.get("category", "unknown"),
            }

            # Running state transitions (log only; metric via ObservableGauge)
            if is_running and not state.was_running:
                logger.info(
                    "Detected AI CLI tool: {} (PIDs: {})",
                    tool_name, found.get(tool_name),
                )
            elif not is_running and state.was_running:
                logger.info("AI CLI tool stopped: {}", tool_name)

            # Update running tools snapshot for ObservableGauge callback
            if is_running:
                self._running_tools[tool_name] = labels
            else:
                self._running_tools.pop(tool_name, None)

            # Duration tracking (while running)
            if is_running and state.last_scan_time > 0:
                elapsed = now - state.last_scan_time
                self.telemetry.cli_active_duration.add(elapsed, labels)

                cost_per_hour = tool_cfg.get("cost_per_hour", 0)
                if cost_per_hour > 0:
                    cost = cost_per_hour * (elapsed / 3600)
                    self.telemetry.cli_estimated_cost.add(cost, labels)

            state.pids = found.get(tool_name, set())
            state.was_running = is_running
            state.last_scan_time = now

        # Push snapshot to TelemetryManager for ObservableGauge callback
        self.telemetry.set_running_cli(self._running_tools)

    @property
    def running_tools(self) -> dict[str, dict]:
        """Return currently running tools (name -> labels) for ObservableGauge."""
        return dict(self._running_tools)

    def _find_tool_config(self, tool_name: str) -> dict | None:
        for tool in self.config.ai_cli_tools:
            if tool["name"] == tool_name:
                return tool
        return None
