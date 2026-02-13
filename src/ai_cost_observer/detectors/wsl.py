"""WSL detector — Windows-only: detect AI processes inside WSL."""

from __future__ import annotations

import platform
import subprocess

from loguru import logger

from ai_cost_observer.config import AppConfig
from ai_cost_observer.telemetry import TelemetryManager


class WSLDetector:
    """Detect AI processes running inside WSL on Windows."""

    def __init__(self, config: AppConfig, telemetry: TelemetryManager) -> None:
        self.config = config
        self.telemetry = telemetry
        self._enabled = platform.system() == "Windows"
        self._cli_names = {
            tool["name"]: tool
            for tool in config.ai_cli_tools
        }
        self._running_tools: set[tuple[str, str]] = set()

    def scan(self) -> None:
        """Scan for AI processes inside WSL. No-ops on non-Windows."""
        if not self._enabled:
            return

        try:
            distros = self._get_running_distros()
            currently_running: set[tuple[str, str]] = set()
            for distro in distros:
                currently_running.update(self._scan_distro(distro))
            self._apply_running_transitions(currently_running)
        except FileNotFoundError:
            logger.debug("wsl.exe not found — WSL not installed")
            self._enabled = False
        except Exception:
            logger.opt(exception=True).debug("WSL scan failed")

    def _get_running_distros(self) -> list[str]:
        """Get list of running WSL distributions."""
        result = subprocess.run(
            ["wsl.exe", "--list", "--running", "--quiet"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return []
        return [d.strip() for d in result.stdout.strip().splitlines() if d.strip()]

    def _scan_distro(self, distro: str) -> set[tuple[str, str]]:
        """Scan a specific WSL distro for AI processes."""
        try:
            result = subprocess.run(
                ["wsl.exe", "-d", distro, "-e", "ps", "aux"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return set()

            matched_tool_names: set[str] = set()
            for line in result.stdout.splitlines()[1:]:  # skip header
                parts = line.split()
                if len(parts) < 11:
                    continue
                cmd = " ".join(parts[10:])

                for tool_name, tool_cfg in self._cli_names.items():
                    proc_names_map = tool_cfg.get("process_names", {})
                    # WSL runs Linux; prefer "linux" key, fall back to "macos"
                    # for backward compatibility (most CLI tool names are the
                    # same on Linux and macOS).
                    proc_names = proc_names_map.get("linux") or proc_names_map.get("macos", [])
                    for proc_name in proc_names:
                        if proc_name in cmd:
                            matched_tool_names.add(tool_name)
                            break
            return {(tool_name, distro) for tool_name in matched_tool_names}
        except subprocess.TimeoutExpired:
            logger.debug("WSL ps command timed out for {}", distro)
            return set()
        except Exception:
            logger.opt(exception=True).debug("Error scanning WSL distro {}", distro)
            return set()

    def _apply_running_transitions(
        self, currently_running: set[tuple[str, str]]
    ) -> None:
        started = currently_running - self._running_tools
        stopped = self._running_tools - currently_running

        for tool_name, distro in sorted(started):
            logger.info("Detected AI tool in WSL/{}: {}", distro, tool_name)

        for tool_name, distro in sorted(stopped):
            logger.info("AI tool stopped in WSL/{}: {}", distro, tool_name)

        self._running_tools = currently_running

        # Build snapshot for ObservableGauge callback
        snapshot = {
            f"{tool_name}:wsl:{distro}": self._build_labels(tool_name, distro)
            for tool_name, distro in currently_running
        }
        self.telemetry.set_running_wsl(snapshot)

    def _build_labels(self, tool_name: str, distro: str) -> dict[str, str]:
        tool_cfg = self._cli_names.get(tool_name, {})
        return {
            "cli.name": tool_name,
            "cli.category": tool_cfg.get("category", "unknown"),
            "runtime.environment": "wsl",
            "wsl.distro": distro,
        }
