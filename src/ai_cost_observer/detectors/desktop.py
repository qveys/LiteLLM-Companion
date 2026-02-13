"""Desktop AI app detection — scans processes, tracks foreground time, exports metrics."""

from __future__ import annotations

import platform
import time
from dataclasses import dataclass, field

import psutil
from loguru import logger

from ai_cost_observer.config import AppConfig
from ai_cost_observer.detectors.active_window import get_foreground_app
from ai_cost_observer.telemetry import TelemetryManager

_OS_KEY = "macos" if platform.system() == "Darwin" else "windows"


@dataclass
class _AppState:
    """Tracks per-app running state between scans."""

    pids: set[int] = field(default_factory=set)
    was_running: bool = False
    was_foreground: bool = False
    last_scan_time: float = 0.0


class DesktopDetector:
    """Detects running AI desktop apps and tracks foreground time."""

    def __init__(self, config: AppConfig, telemetry: TelemetryManager) -> None:
        self.config = config
        self.telemetry = telemetry
        self._state: dict[str, _AppState] = {}
        self._claimed_pids: set[int] = set()  # PIDs claimed in the last scan
        # Bug H1: track currently running apps for ObservableGauge callback
        self._running_apps: dict[str, dict] = {}  # app_name -> labels
        # Track PIDs that have been primed for cpu_percent (first call returns 0)
        self._primed_pids: set[int] = set()

        # Build process name → app config lookup
        self._process_map: dict[str, dict] = {}
        for app in config.ai_apps:
            for proc_name in app.get("process_names", {}).get(_OS_KEY, []):
                self._process_map[proc_name.lower()] = app

        # Build cmdline pattern → app config lookup (for interpreted scripts)
        self._cmdline_patterns: dict[str, dict] = {}
        for app in config.ai_apps:
            for pattern in app.get("cmdline_patterns", []):
                self._cmdline_patterns[pattern.lower()] = app

        # Build exe path pattern → app config lookup (Tier 2 matching)
        # Use list of tuples to avoid key collisions if multiple apps share a pattern.
        self._exe_patterns: list[tuple[str, dict]] = []
        for app in config.ai_apps:
            for pattern in app.get("exe_path_patterns", []):
                self._exe_patterns.append((pattern.lower(), app))

    def scan(self) -> None:
        """Run one scan cycle: detect apps, update metrics."""
        now = time.monotonic()

        try:
            foreground_app = get_foreground_app()
        except Exception:
            logger.opt(exception=True).debug("Failed to get foreground app")
            foreground_app = None

        # Scan all processes
        found: dict[str, set[int]] = {}
        cpu_by_app: dict[str, float] = {}
        mem_by_app: dict[str, float] = {}

        for proc in psutil.process_iter(["pid", "name", "exe", "cmdline"]):
            try:
                proc_name = proc.info["name"]
                if not proc_name:
                    continue
                proc_name_lower = proc_name.lower()

                app_cfg = None

                # Tier 1: match by process name
                if proc_name_lower in self._process_map:
                    app_cfg = self._process_map[proc_name_lower]

                # Tier 2: match by exe path
                if app_cfg is None and self._exe_patterns:
                    exe_path = proc.info.get("exe") or ""
                    if exe_path and not exe_path.startswith("/System/Library/"):
                        exe_lower = exe_path.lower()
                        for pattern, candidate in self._exe_patterns:
                            if pattern in exe_lower:
                                app_cfg = candidate
                                break

                # Tier 3: match by cmdline for interpreted scripts
                if app_cfg is None and self._cmdline_patterns:
                    cmdline = proc.info.get("cmdline") or []
                    if cmdline:
                        cmdline_str = " ".join(cmdline).lower()
                        for pattern, candidate in self._cmdline_patterns.items():
                            if pattern in cmdline_str:
                                app_cfg = candidate
                                break

                if app_cfg:
                    app_name = app_cfg["name"]

                    if app_name not in found:
                        found[app_name] = set()
                    found[app_name].add(proc.info["pid"])

                    # Collect resource usage (best effort)
                    try:
                        pid = proc.info["pid"]
                        cpu = proc.cpu_percent(interval=0)
                        # cpu_percent(interval=0) returns 0.0 on the first call
                        # for a PID (no baseline yet). Prime it and skip the
                        # value; subsequent scans will report a real reading.
                        if pid not in self._primed_pids:
                            self._primed_pids.add(pid)
                            cpu = 0.0  # explicitly discard first-call value
                        mem = proc.memory_info().rss / (1024 * 1024)  # MB
                        cpu_by_app[app_name] = cpu_by_app.get(app_name, 0) + cpu
                        mem_by_app[app_name] = mem_by_app.get(app_name, 0) + mem
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        pass

            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
            except Exception:
                logger.opt(exception=True).debug("Error scanning process")
                continue

        # Update claimed PIDs for cross-detector dedup
        self._claimed_pids = set()
        for pids in found.values():
            self._claimed_pids.update(pids)

        # Clean up primed PIDs for processes that no longer exist
        self._primed_pids &= self._claimed_pids

        # Update metrics for each known app
        all_apps = set(found.keys()) | set(self._state.keys())

        for app_name in all_apps:
            state = self._state.setdefault(app_name, _AppState())
            is_running = app_name in found
            app_cfg = self._find_app_config(app_name)
            if not app_cfg:
                continue

            labels = {
                "app.name": app_name,
                "app.category": app_cfg.get("category", "unknown"),
            }
            if app_cfg.get("requires_plugin"):
                labels["app.requires_plugin"] = "true"

            # Running state transitions (log only; metric via ObservableGauge)
            if is_running and not state.was_running:
                logger.info(
                    "Detected AI app: {} (PIDs: {})",
                    app_name, found.get(app_name, set()),
                )
            elif not is_running and state.was_running:
                logger.info("AI app stopped: {}", app_name)

            # Update running apps snapshot for ObservableGauge callback
            if is_running:
                self._running_apps[app_name] = labels
            else:
                self._running_apps.pop(app_name, None)

            # Foreground time tracking
            is_foreground = False
            if is_running and foreground_app:
                # Check if the foreground app matches any process name for this app
                for proc_name in app_cfg.get("process_names", {}).get(_OS_KEY, []):
                    if foreground_app.lower() == proc_name.lower():
                        is_foreground = True
                        break

            if is_foreground and state.last_scan_time > 0:
                elapsed = now - state.last_scan_time
                self.telemetry.app_active_duration.add(elapsed, labels)

                cost_per_hour = app_cfg.get("cost_per_hour", 0)
                if cost_per_hour > 0:
                    cost = cost_per_hour * (elapsed / 3600)
                    self.telemetry.app_estimated_cost.add(cost, labels)

            # Resource usage gauges
            if app_name in cpu_by_app:
                self.telemetry.app_cpu_usage.set(cpu_by_app[app_name], labels)
            if app_name in mem_by_app:
                self.telemetry.app_memory_usage.set(mem_by_app[app_name], labels)

            state.pids = found.get(app_name, set())
            state.was_running = is_running
            state.was_foreground = is_foreground
            state.last_scan_time = now

        # Push snapshot to TelemetryManager for ObservableGauge callback
        self.telemetry.set_running_apps(self._running_apps)

    @property
    def running_apps(self) -> dict[str, dict]:
        """Return currently running apps (name -> labels) for ObservableGauge."""
        return dict(self._running_apps)

    @property
    def claimed_pids(self) -> set[int]:
        """Return PIDs claimed in the most recent scan (for cross-detector dedup)."""
        return self._claimed_pids

    def _find_app_config(self, app_name: str) -> dict | None:
        for app in self.config.ai_apps:
            if app["name"] == app_name:
                return app
        return None
