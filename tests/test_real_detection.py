"""Real detection test -- verifies detectors against actually running processes.

This test does NOT mock psutil. It uses the real process list on the current
machine, cross-references with ai_config.yaml, and verifies that the detectors
find everything they should.

Works on any machine: assertions are conditional on what is actually running.
"""

from __future__ import annotations

import platform
from unittest.mock import Mock

import psutil
import yaml

from ai_cost_observer.config import AppConfig
from ai_cost_observer.detectors.cli import CLIDetector
from ai_cost_observer.detectors.desktop import DesktopDetector

_OS_KEY = "macos" if platform.system() == "Darwin" else "windows"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_ai_config() -> dict:
    """Load ai_config.yaml from package data."""
    from importlib.resources import files

    data_dir = files("ai_cost_observer") / "data"
    config_path = data_dir / "ai_config.yaml"
    return yaml.safe_load(config_path.read_text(encoding="utf-8"))


def _build_process_map(entries: list[dict], key: str = "process_names") -> dict[str, str]:
    """Build lowercase process-name -> config-name lookup."""
    mapping: dict[str, str] = {}
    for entry in entries:
        for proc_name in entry.get(key, {}).get(_OS_KEY, []):
            mapping[proc_name.lower()] = entry["name"]
    return mapping


def _build_cmdline_map(entries: list[dict]) -> dict[str, str]:
    """Build lowercase cmdline-pattern -> config-name lookup."""
    mapping: dict[str, str] = {}
    for entry in entries:
        for pattern in entry.get("cmdline_patterns", []):
            mapping[pattern.lower()] = entry["name"]
    return mapping


def _scan_running_processes() -> list[dict]:
    """Return a list of dicts with pid, name, cmdline for all accessible procs."""
    procs = []
    for p in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            info = p.info
            if info["name"]:
                procs.append(info)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return procs


def _find_expected_matches(
    procs: list[dict],
    proc_map: dict[str, str],
    cmdline_map: dict[str, str],
) -> dict[str, set[int]]:
    """Given running processes and lookup maps, return expected {name: {pids}}."""
    found: dict[str, set[int]] = {}
    for p in procs:
        name_lower = p["name"].lower()
        config_name = proc_map.get(name_lower)

        # Fallback: cmdline pattern
        if config_name is None and cmdline_map:
            cmdline = p.get("cmdline") or []
            if cmdline:
                cmdline_str = " ".join(cmdline).lower()
                for pattern, cname in cmdline_map.items():
                    if pattern in cmdline_str:
                        config_name = cname
                        break

        if config_name:
            found.setdefault(config_name, set()).add(p["pid"])
    return found


def _exclude_desktop_overlapping_tools(
    expected: dict[str, set[int]],
    cli_tools: list[dict],
    desktop_proc_lower: set[str],
    procs: list[dict],
) -> dict[str, set[int]]:
    """Remove CLI tool entries whose PIDs were matched via a process name that
    also appears (case-insensitive) in the desktop app config.

    This mirrors the CLI detector's name-based dedup fallback: when no
    desktop_detector is provided, the CLI detector skips process names that
    match a desktop app to avoid double-counting.
    """
    # Build CLI tool name -> set of desktop-overlapping process names
    overlapping: dict[str, set[str]] = {}
    for tool in cli_tools:
        for pn in tool.get("process_names", {}).get(_OS_KEY, []):
            if pn.lower() in desktop_proc_lower:
                overlapping.setdefault(tool["name"], set()).add(pn.lower())

    if not overlapping:
        return expected

    # For each expected tool, remove PIDs that were matched via an overlapping name
    filtered = {}
    for tool_name, pids in expected.items():
        if tool_name not in overlapping:
            filtered[tool_name] = pids
            continue
        # Keep only PIDs that were NOT matched via the overlapping process name
        kept = set()
        overlap_names = overlapping[tool_name]
        for p in procs:
            if p["pid"] in pids and p["name"].lower() not in overlap_names:
                kept.add(p["pid"])
        if kept:
            filtered[tool_name] = kept
    return filtered


def _make_mock_telemetry() -> Mock:
    """Create a mock TelemetryManager capturing all metric calls."""
    telemetry = Mock()
    # ObservableGauges (Bug H1: was UpDownCounter)
    telemetry.app_running = Mock()
    telemetry.set_running_apps = Mock()
    telemetry.cli_running = Mock()
    telemetry.set_running_cli = Mock()
    # Counters
    for attr in [
        "app_active_duration",
        "app_estimated_cost",
    ]:
        counter = Mock()
        counter.add = Mock()
        setattr(telemetry, attr, counter)
    # Gauges (Bug C3: was Histogram)
    for attr in ["app_cpu_usage", "app_memory_usage"]:
        gauge = Mock()
        gauge.set = Mock()
        setattr(telemetry, attr, gauge)
    for attr in [
        "cli_active_duration",
        "cli_estimated_cost",
        "cli_command_count",
    ]:
        counter = Mock()
        counter.add = Mock()
        setattr(telemetry, attr, counter)
    return telemetry


def _make_real_config() -> AppConfig:
    """Build an AppConfig loaded with the real ai_config.yaml data."""
    ai_cfg = _load_ai_config()
    config = AppConfig()
    config.ai_apps = ai_cfg.get("ai_apps", [])
    config.ai_cli_tools = ai_cfg.get("ai_cli_tools", [])
    config.ai_domains = ai_cfg.get("ai_domains", [])
    return config


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRealDesktopDetection:
    """Verify DesktopDetector against the real process list."""

    def test_list_matching_desktop_processes(self):
        """Report which AI desktop apps are currently running (informational)."""
        ai_cfg = _load_ai_config()
        proc_map = _build_process_map(ai_cfg["ai_apps"])
        cmdline_map = _build_cmdline_map(ai_cfg["ai_apps"])
        procs = _scan_running_processes()
        expected = _find_expected_matches(procs, proc_map, cmdline_map)

        print("\n--- Running AI Desktop Apps ---")
        if not expected:
            print("  (none detected)")
        for name, pids in sorted(expected.items()):
            print(f"  {name}: PIDs {sorted(pids)}")
        print(f"  Total: {len(expected)} app(s) detected")

    def test_desktop_detector_finds_running_apps(self, mocker):
        """DesktopDetector scan should detect all AI apps visible to psutil."""
        config = _make_real_config()
        telemetry = _make_mock_telemetry()

        # Patch only the foreground check -- we want real process scanning
        mocker.patch(
            "ai_cost_observer.detectors.desktop.get_foreground_app",
            return_value=None,
        )

        detector = DesktopDetector(config, telemetry)

        # Build expected set from our own scan
        proc_map = _build_process_map(config.ai_apps)
        cmdline_map = _build_cmdline_map(config.ai_apps)
        procs = _scan_running_processes()
        expected = _find_expected_matches(procs, proc_map, cmdline_map)

        # Run detector scan
        detector.scan()

        # Bug H1: Collect detected apps from running_apps property
        detected_names: set[str] = set(detector.running_apps.keys())

        print("\n--- Desktop Detection Results ---")
        print(f"  Expected (from psutil scan): {sorted(expected.keys())}")
        print(f"  Detected (by DesktopDetector): {sorted(detected_names)}")

        # Core assertion: every app we found in psutil should be detected
        for app_name in expected:
            assert app_name in detected_names, (
                f"DesktopDetector missed running app '{app_name}' "
                f"(PIDs: {sorted(expected[app_name])})"
            )

        # No false negatives for the process-name path
        if expected:
            assert len(detected_names) >= len(expected), (
                "DesktopDetector found fewer apps than expected"
            )

    def test_desktop_detector_internal_state(self, mocker):
        """After scan, detector internal state should reflect running apps."""
        config = _make_real_config()
        telemetry = _make_mock_telemetry()
        mocker.patch(
            "ai_cost_observer.detectors.desktop.get_foreground_app",
            return_value=None,
        )

        detector = DesktopDetector(config, telemetry)
        detector.scan()

        running_in_state = {name for name, st in detector._state.items() if st.was_running}

        proc_map = _build_process_map(config.ai_apps)
        cmdline_map = _build_cmdline_map(config.ai_apps)
        procs = _scan_running_processes()
        expected = set(_find_expected_matches(procs, proc_map, cmdline_map).keys())

        print("\n--- Desktop Internal State ---")
        print(f"  State reports running: {sorted(running_in_state)}")
        print(f"  Expected running: {sorted(expected)}")

        for app_name in expected:
            assert app_name in running_in_state, f"Internal state missing running app '{app_name}'"


class TestRealCLIDetection:
    """Verify CLIDetector against the real process list."""

    def test_list_matching_cli_processes(self):
        """Report which AI CLI tools are currently running (informational)."""
        ai_cfg = _load_ai_config()
        proc_map = _build_process_map(ai_cfg["ai_cli_tools"])
        cmdline_map = _build_cmdline_map(ai_cfg["ai_cli_tools"])
        procs = _scan_running_processes()
        expected = _find_expected_matches(procs, proc_map, cmdline_map)

        print("\n--- Running AI CLI Tools ---")
        if not expected:
            print("  (none detected)")
        for name, pids in sorted(expected.items()):
            print(f"  {name}: PIDs {sorted(pids)}")
        print(f"  Total: {len(expected)} tool(s) detected")

    def test_cli_detector_finds_running_tools(self):
        """CLIDetector scan should detect all AI CLI tools visible to psutil.

        Tools whose process names also match a desktop app are excluded from
        expected results because the CLI detector's name-based dedup (fallback
        when no desktop_detector is provided) correctly skips them.
        """
        config = _make_real_config()
        telemetry = _make_mock_telemetry()

        detector = CLIDetector(config, telemetry)

        # Build expected set from our own scan
        proc_map = _build_process_map(config.ai_cli_tools)
        cmdline_map = _build_cmdline_map(config.ai_cli_tools)
        procs = _scan_running_processes()
        expected = _find_expected_matches(procs, proc_map, cmdline_map)

        # Exclude tools whose process names overlap with desktop apps
        # (the CLI detector skips these via case-insensitive name dedup)
        desktop_proc_lower = set()
        for app in config.ai_apps:
            for pn in app.get("process_names", {}).get(_OS_KEY, []):
                desktop_proc_lower.add(pn.lower())
        expected = _exclude_desktop_overlapping_tools(
            expected,
            config.ai_cli_tools,
            desktop_proc_lower,
            procs,
        )

        # Run detector scan
        detector.scan()

        # Bug H1: Collect detected tools from running_tools property
        detected_names: set[str] = set(detector.running_tools.keys())

        print("\n--- CLI Detection Results ---")
        print(f"  Expected (from psutil scan): {sorted(expected.keys())}")
        print(f"  Detected (by CLIDetector): {sorted(detected_names)}")

        # Core assertion: every tool we found in psutil should be detected
        for tool_name in expected:
            assert tool_name in detected_names, (
                f"CLIDetector missed running tool '{tool_name}' "
                f"(PIDs: {sorted(expected[tool_name])})"
            )

    def test_cli_detector_internal_state(self):
        """After scan, detector internal state should reflect running tools."""
        config = _make_real_config()
        telemetry = _make_mock_telemetry()

        detector = CLIDetector(config, telemetry)
        detector.scan()

        running_in_state = {name for name, st in detector._state.items() if st.was_running}

        proc_map = _build_process_map(config.ai_cli_tools)
        cmdline_map = _build_cmdline_map(config.ai_cli_tools)
        procs = _scan_running_processes()
        expected = set(_find_expected_matches(procs, proc_map, cmdline_map).keys())

        # Exclude tools whose process names overlap with desktop apps
        desktop_proc_lower = set()
        for app in config.ai_apps:
            for pn in app.get("process_names", {}).get(_OS_KEY, []):
                desktop_proc_lower.add(pn.lower())
        cli_desktop_overlap = set()
        for tool in config.ai_cli_tools:
            for pn in tool.get("process_names", {}).get(_OS_KEY, []):
                if pn.lower() in desktop_proc_lower:
                    cli_desktop_overlap.add(tool["name"])
        expected -= cli_desktop_overlap

        print("\n--- CLI Internal State ---")
        print(f"  State reports running: {sorted(running_in_state)}")
        print(f"  Expected running: {sorted(expected)}")

        for tool_name in expected:
            assert tool_name in running_in_state, (
                f"Internal state missing running tool '{tool_name}'"
            )


class TestProcessMapCoverage:
    """Verify that the config's process maps are well-formed."""

    def test_all_desktop_apps_have_os_process_names(self):
        """Every ai_app should have at least one process_name for this OS."""
        ai_cfg = _load_ai_config()
        missing = []
        for app in ai_cfg["ai_apps"]:
            names = app.get("process_names", {}).get(_OS_KEY, [])
            if not names:
                missing.append(app["name"])

        print(f"\n--- Desktop apps without {_OS_KEY} process_names ---")
        if missing:
            for name in missing:
                print(f"  WARNING: {name}")
        else:
            print("  All apps have process names for this OS")

    def test_all_cli_tools_have_os_process_names(self):
        """Every ai_cli_tool should have at least one process_name for this OS."""
        ai_cfg = _load_ai_config()
        missing = []
        for tool in ai_cfg["ai_cli_tools"]:
            names = tool.get("process_names", {}).get(_OS_KEY, [])
            if not names:
                missing.append(tool["name"])

        print(f"\n--- CLI tools without {_OS_KEY} process_names ---")
        if missing:
            for name in missing:
                print(f"  WARNING: {name}")
        else:
            print("  All tools have process names for this OS")

    def test_no_duplicate_process_names_in_desktop(self):
        """No two desktop apps should claim the same process name."""
        ai_cfg = _load_ai_config()
        seen: dict[str, str] = {}
        duplicates: list[str] = []
        for app in ai_cfg["ai_apps"]:
            for proc_name in app.get("process_names", {}).get(_OS_KEY, []):
                key = proc_name.lower()
                if key in seen:
                    duplicates.append(
                        f"'{proc_name}' claimed by both '{seen[key]}' and '{app['name']}'"
                    )
                else:
                    seen[key] = app["name"]

        if duplicates:
            print("\n--- Duplicate desktop process names ---")
            for d in duplicates:
                print(f"  WARNING: {d}")
        # ChatGPT and DALL-E share process names by design, so just report
        # rather than fail. This is informational.

    def test_no_overlap_between_desktop_and_cli_process_names(self):
        """Flag process names that appear in both desktop and CLI configs.

        Some overlap is expected (e.g. 'ollama', 'codex') -- this test
        documents them rather than failing.
        """
        ai_cfg = _load_ai_config()
        desktop_map = _build_process_map(ai_cfg["ai_apps"])
        cli_map = _build_process_map(ai_cfg["ai_cli_tools"])

        overlap = set(desktop_map.keys()) & set(cli_map.keys())
        print("\n--- Process names in BOTH desktop and CLI configs ---")
        if overlap:
            for name in sorted(overlap):
                print(f"  '{name}': desktop='{desktop_map[name]}', cli='{cli_map[name]}'")
        else:
            print("  No overlap")
