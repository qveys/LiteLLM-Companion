"""Extended WSL detector tests — disabled on macOS, multiple distros."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ai_cost_observer.config import AppConfig
from ai_cost_observer.detectors.wsl import WSLDetector


class _Recorder:
    def __init__(self) -> None:
        self.calls: list[tuple[int, dict[str, str]]] = []

    def add(self, value: int, labels: dict[str, str]) -> None:
        self.calls.append((value, labels.copy()))


class _DummyTelemetry:
    def __init__(self) -> None:
        self.cli_running = _Recorder()


def _make_config(cli_tools=None):
    return AppConfig(
        ai_cli_tools=cli_tools
        or [
            {
                "name": "claude-code",
                "category": "code",
                "process_names": {"macos": ["claude"]},
            },
            {
                "name": "ollama",
                "category": "inference",
                "process_names": {"macos": ["ollama"]},
            },
        ]
    )


class TestWSLDisabledOnMacOS:
    """WSL detector is disabled on non-Windows platforms."""

    def test_disabled_on_macos(self, mocker):
        """WSL detector no-ops when platform is not Windows."""
        mocker.patch("ai_cost_observer.detectors.wsl.platform.system", return_value="Darwin")
        config = _make_config()
        telemetry = _DummyTelemetry()

        detector = WSLDetector(config, telemetry)
        assert detector._enabled is False

        detector.scan()  # Should no-op
        assert len(telemetry.cli_running.calls) == 0

    def test_disabled_on_linux(self, mocker):
        """WSL detector no-ops when platform is Linux."""
        mocker.patch("ai_cost_observer.detectors.wsl.platform.system", return_value="Linux")
        config = _make_config()
        telemetry = _DummyTelemetry()

        detector = WSLDetector(config, telemetry)
        assert detector._enabled is False


class TestWSLMultipleDistros:
    """WSL detector handles multiple simultaneous distributions."""

    def test_detects_tools_across_distros(self, mocker):
        """Different AI tools running in different WSL distros are all detected."""
        config = _make_config()
        telemetry = _DummyTelemetry()
        detector = WSLDetector(config, telemetry)
        detector._enabled = True

        mocker.patch.object(
            detector, "_get_running_distros", return_value=["Ubuntu", "Debian"]
        )

        ubuntu_output = (
            "USER PID %CPU %MEM VSZ RSS TTY STAT START TIME COMMAND\n"
            "user 1 0.0 0.1 1 1 ? S 00:00 00:00 claude\n"
        )
        debian_output = (
            "USER PID %CPU %MEM VSZ RSS TTY STAT START TIME COMMAND\n"
            "user 1 0.0 0.1 1 1 ? S 00:00 00:00 ollama serve\n"
        )

        def _fake_run(args, **kwargs):
            # Determine which distro is being queried
            if "Ubuntu" in args:
                return SimpleNamespace(returncode=0, stdout=ubuntu_output)
            elif "Debian" in args:
                return SimpleNamespace(returncode=0, stdout=debian_output)
            return SimpleNamespace(returncode=1, stdout="")

        mocker.patch("ai_cost_observer.detectors.wsl.subprocess.run", side_effect=_fake_run)

        detector.scan()

        values = [v for v, _ in telemetry.cli_running.calls]
        assert values == [1, 1]

        # Check labels
        labels_by_tool = {c[1]["cli.name"]: c[1] for c in telemetry.cli_running.calls}
        assert labels_by_tool["claude-code"]["wsl.distro"] == "Ubuntu"
        assert labels_by_tool["claude-code"]["runtime.environment"] == "wsl"
        assert labels_by_tool["ollama"]["wsl.distro"] == "Debian"

    def test_same_tool_multiple_distros(self, mocker):
        """Same tool in multiple distros generates separate running events."""
        config = _make_config()
        telemetry = _DummyTelemetry()
        detector = WSLDetector(config, telemetry)
        detector._enabled = True

        mocker.patch.object(
            detector, "_get_running_distros", return_value=["Ubuntu", "Fedora"]
        )

        ps_output = (
            "USER PID %CPU %MEM VSZ RSS TTY STAT START TIME COMMAND\n"
            "user 1 0.0 0.1 1 1 ? S 00:00 00:00 claude\n"
        )

        mocker.patch(
            "ai_cost_observer.detectors.wsl.subprocess.run",
            return_value=SimpleNamespace(returncode=0, stdout=ps_output),
        )

        detector.scan()

        # Should get two +1 events (claude in Ubuntu and claude in Fedora)
        values = [v for v, _ in telemetry.cli_running.calls]
        assert values == [1, 1]

        distros = {c[1]["wsl.distro"] for c in telemetry.cli_running.calls}
        assert distros == {"Ubuntu", "Fedora"}

    def test_tool_stops_in_one_distro(self, mocker):
        """When a tool stops in one distro, only that distro gets -1."""
        config = _make_config()
        telemetry = _DummyTelemetry()
        detector = WSLDetector(config, telemetry)
        detector._enabled = True

        mocker.patch.object(
            detector, "_get_running_distros", return_value=["Ubuntu", "Debian"]
        )

        ps_with_claude = (
            "USER PID %CPU %MEM VSZ RSS TTY STAT START TIME COMMAND\n"
            "user 1 0.0 0.1 1 1 ? S 00:00 00:00 claude\n"
        )
        ps_without_claude = (
            "USER PID %CPU %MEM VSZ RSS TTY STAT START TIME COMMAND\n"
            "user 1 0.0 0.1 1 1 ? S 00:00 00:00 bash\n"
        )

        # Scan 1: claude running in both
        mocker.patch(
            "ai_cost_observer.detectors.wsl.subprocess.run",
            return_value=SimpleNamespace(returncode=0, stdout=ps_with_claude),
        )
        detector.scan()

        assert len(telemetry.cli_running.calls) == 2
        telemetry.cli_running.calls.clear()

        # Scan 2: claude stops in Debian only
        call_count = [0]

        def _fake_run_selective(args, **kwargs):
            if "Debian" in args:
                return SimpleNamespace(returncode=0, stdout=ps_without_claude)
            return SimpleNamespace(returncode=0, stdout=ps_with_claude)

        mocker.patch(
            "ai_cost_observer.detectors.wsl.subprocess.run",
            side_effect=_fake_run_selective,
        )

        detector.scan()

        # Should get one -1 for Debian
        assert len(telemetry.cli_running.calls) == 1
        assert telemetry.cli_running.calls[0][0] == -1
        assert telemetry.cli_running.calls[0][1]["wsl.distro"] == "Debian"
