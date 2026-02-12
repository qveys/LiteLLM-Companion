"""Regression tests for WSL detector running-state accounting."""

from __future__ import annotations

from types import SimpleNamespace

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


def test_wsl_detector_emits_transition_deltas_only_once_per_state(mocker) -> None:
    config = AppConfig(
        ai_cli_tools=[
            {
                "name": "claude-code",
                "category": "code",
                "process_names": {"macos": ["claude"]},
            }
        ]
    )
    telemetry = _DummyTelemetry()
    detector = WSLDetector(config, telemetry)
    detector._enabled = True

    mocker.patch.object(detector, "_get_running_distros", return_value=["Ubuntu"])

    scans = [
        "USER PID %CPU %MEM VSZ RSS TTY STAT START TIME COMMAND\nq 1 0.0 0.1 1 1 ? S 00:00 00:00 claude\n",
        "USER PID %CPU %MEM VSZ RSS TTY STAT START TIME COMMAND\nq 1 0.0 0.1 1 1 ? S 00:00 00:00 claude\n",
        "USER PID %CPU %MEM VSZ RSS TTY STAT START TIME COMMAND\nq 1 0.0 0.1 1 1 ? S 00:00 00:00 bash\n",
    ]

    def _fake_run(*_args, **_kwargs):
        return SimpleNamespace(returncode=0, stdout=scans.pop(0))

    mocker.patch("ai_cost_observer.detectors.wsl.subprocess.run", side_effect=_fake_run)

    detector.scan()
    detector.scan()
    detector.scan()

    assert [value for value, _ in telemetry.cli_running.calls] == [1, -1]
    assert telemetry.cli_running.calls[0][1]["runtime.environment"] == "wsl"
    assert telemetry.cli_running.calls[0][1]["wsl.distro"] == "Ubuntu"
