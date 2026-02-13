"""Regression tests for WSL detector running-state accounting."""

from __future__ import annotations

from types import SimpleNamespace

from ai_cost_observer.config import AppConfig
from ai_cost_observer.detectors.wsl import WSLDetector


class _DummyTelemetry:
    def __init__(self) -> None:
        self._wsl_snapshots: list[dict[str, dict]] = []

    def set_running_wsl(self, running: dict[str, dict]) -> None:
        self._wsl_snapshots.append(dict(running))


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

    hdr = "USER PID %CPU %MEM VSZ RSS TTY STAT START TIME COMMAND\n"
    scans = [
        hdr + "q 1 0.0 0.1 1 1 ? S 00:00 00:00 claude\n",
        hdr + "q 1 0.0 0.1 1 1 ? S 00:00 00:00 claude\n",
        hdr + "q 1 0.0 0.1 1 1 ? S 00:00 00:00 bash\n",
    ]

    def _fake_run(*_args, **_kwargs):
        return SimpleNamespace(returncode=0, stdout=scans.pop(0))

    mocker.patch("ai_cost_observer.detectors.wsl.subprocess.run", side_effect=_fake_run)

    detector.scan()
    detector.scan()
    detector.scan()

    # Scan 1: claude detected → snapshot has 1 entry
    assert len(telemetry._wsl_snapshots[0]) == 1
    labels = list(telemetry._wsl_snapshots[0].values())[0]
    assert labels["runtime.environment"] == "wsl"
    assert labels["wsl.distro"] == "Ubuntu"

    # Scan 2: claude still running → snapshot still has 1 entry
    assert len(telemetry._wsl_snapshots[1]) == 1

    # Scan 3: claude stopped → snapshot is empty
    assert len(telemetry._wsl_snapshots[2]) == 0
