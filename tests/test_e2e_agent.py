"""
End-to-end style test that runs the agent's main loop in-process.
"""

import os
import time
from pathlib import Path
from threading import Event, Thread
from unittest.mock import Mock

import pytest
from flask import Flask, jsonify, request
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import (
    ExportMetricsServiceRequest,
)

from ai_cost_observer.config import load_config
from ai_cost_observer.detectors.browser_history import BrowserHistoryParser
from ai_cost_observer.detectors.cli import CLIDetector
from ai_cost_observer.detectors.desktop import DesktopDetector
from ai_cost_observer.detectors.shell_history import ShellHistoryParser
from ai_cost_observer.detectors.wsl import WSLDetector
from ai_cost_observer.main import _run_periodic, run_main_loop
from ai_cost_observer.telemetry import TelemetryManager


# --- Mock OTLP/HTTP Server (parses protobuf) ---
class OTLPMockServer:
    def __init__(self, port=4318):
        self.app = Flask(__name__)
        self.port = port
        self.received_requests: list[ExportMetricsServiceRequest] = []
        self._server_thread = Thread(
            target=self.app.run, kwargs={"host": "127.0.0.1", "port": self.port}
        )
        self._server_thread.daemon = True

        @self.app.route("/v1/metrics", methods=["POST"])
        def metrics_endpoint():
            raw_body = request.data
            if raw_body:
                parsed = ExportMetricsServiceRequest()
                parsed.ParseFromString(raw_body)
                self.received_requests.append(parsed)
            return jsonify({}), 200

    def start(self):
        self._server_thread.start()
        time.sleep(0.1)

    def get_metric_data_points(self, metric_name: str) -> list:
        """Finds and returns all data points for a given metric name."""
        points = []
        for req in self.received_requests:
            for rm in req.resource_metrics:
                for sm in rm.scope_metrics:
                    for metric in sm.metrics:
                        if metric.name == metric_name:
                            for dp in metric.sum.data_points:
                                points.append(dp)
        return points


@pytest.fixture
def mock_server():
    server = OTLPMockServer()
    server.start()
    yield server


def test_e2e_main_loop_sends_metrics(
    tmp_path: Path, mocker, mock_server: OTLPMockServer
):
    """
    Runs the main loop in-process and verifies that metrics are sent.
    This test focuses on the shell history detector to confirm the E2E pipeline.
    """
    # --- Setup ---
    history_file = tmp_path / "test.zsh_history"
    history_file.write_text(": 123:0;ollama one\n: 124:0;ollama two\n")

    mocker.patch(
        "ai_cost_observer.config._load_builtin_ai_config",
        return_value={"ai_cli_tools": [{"name": "Ollama", "command_patterns": ["ollama"]}]},
    )
    mocker.patch("ai_cost_observer.config._load_user_config", return_value={})
    mocker.patch(
        "ai_cost_observer.detectors.shell_history.ShellHistoryParser._get_history_files",
        return_value=[(str(history_file), "zsh")],
    )

    config = load_config()
    config.scan_interval_seconds = 0.5

    # Inject the HTTP exporter directly to avoid gRPC/protocol issues
    exporter = OTLPMetricExporter(
        endpoint=f"http://127.0.0.1:{mock_server.port}/v1/metrics"
    )
    telemetry = TelemetryManager(config, exporter=exporter)

    detectors = {
        "desktop": Mock(spec=DesktopDetector),
        "cli": Mock(spec=CLIDetector),
        "wsl": Mock(spec=WSLDetector),
        "browser_history": Mock(spec=BrowserHistoryParser),
        "shell_history": ShellHistoryParser(config, telemetry),
    }

    # --- Execution ---
    stop_event = Event()

    shell_thread = Thread(
        target=_run_periodic,
        args=("shell_history", detectors["shell_history"].scan, 0.5, stop_event),
        daemon=True,
    )
    shell_thread.start()

    main_thread = Thread(target=run_main_loop, args=(stop_event, config, detectors))
    main_thread.daemon = True
    main_thread.start()

    time.sleep(2)  # Let it run for a few scan cycles

    stop_event.set()
    main_thread.join(timeout=5)
    shell_thread.join(timeout=2)

    # --- Assertions ---
    assert not main_thread.is_alive(), "Main loop thread did not terminate"
    assert len(mock_server.received_requests) > 0, "Mock server received no metrics"

    command_counts = mock_server.get_metric_data_points("ai.cli.command.count")
    assert len(command_counts) > 0, "ai.cli.command.count metric not found"

    # Find the specific data point for Ollama via protobuf attributes
    ollama_dp = None
    for dp in command_counts:
        for attr in dp.attributes:
            if attr.key == "cli.name" and attr.value.string_value == "Ollama":
                ollama_dp = dp
                break

    assert ollama_dp is not None, "Data point for 'Ollama' not found"
    assert ollama_dp.as_int == 2, f"Ollama command count should be 2, got {ollama_dp.as_int}"
