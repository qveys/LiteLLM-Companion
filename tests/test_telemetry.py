"""Tests for the TelemetryManager — metric instruments, resource attributes, lifecycle."""

from __future__ import annotations

from unittest.mock import MagicMock, Mock, patch
import platform

import pytest

from ai_cost_observer.config import AppConfig


class TestTelemetryInstruments:
    """Verify all metric instruments are created on the TelemetryManager."""

    @patch("ai_cost_observer.telemetry.metrics")
    @patch("ai_cost_observer.telemetry.MeterProvider")
    @patch("ai_cost_observer.telemetry.PeriodicExportingMetricReader")
    @patch("ai_cost_observer.telemetry.Resource")
    def test_telemetry_creates_all_instruments(
        self, mock_resource, mock_reader_cls, mock_provider_cls, mock_metrics
    ):
        """Verify all 16 metric instruments are created."""
        from ai_cost_observer.telemetry import TelemetryManager

        mock_exporter = MagicMock()
        mock_meter = MagicMock()
        mock_provider_cls.return_value.get_meter.return_value = mock_meter

        config = AppConfig()
        config.otel_endpoint = "localhost:4317"
        config.host_name = "test-host"

        tm = TelemetryManager(config, exporter=mock_exporter)

        # Verify all 16 instruments exist
        assert tm.app_running is not None
        assert tm.app_active_duration is not None
        assert tm.app_cpu_usage is not None
        assert tm.app_memory_usage is not None
        assert tm.app_estimated_cost is not None
        assert tm.browser_domain_active_duration is not None
        assert tm.browser_domain_visit_count is not None
        assert tm.browser_domain_estimated_cost is not None
        assert tm.cli_running is not None
        assert tm.cli_active_duration is not None
        assert tm.cli_estimated_cost is not None
        assert tm.cli_command_count is not None
        assert tm.tokens_input_total is not None
        assert tm.tokens_output_total is not None
        assert tm.tokens_cost_usd_total is not None
        assert tm.prompt_count_total is not None

        # Verify meter was called to create instruments
        # Bug H1: app_running and cli_running are now ObservableGauges
        assert mock_meter.create_observable_gauge.call_count == 2
        assert mock_meter.create_counter.call_count == 12
        assert mock_meter.create_gauge.call_count == 2  # cpu, memory (Bug C3: was Histogram)

    @patch("ai_cost_observer.telemetry.metrics")
    @patch("ai_cost_observer.telemetry.MeterProvider")
    @patch("ai_cost_observer.telemetry.PeriodicExportingMetricReader")
    @patch("ai_cost_observer.telemetry.Resource")
    def test_telemetry_resource_attributes(
        self, mock_resource, mock_reader_cls, mock_provider_cls, mock_metrics
    ):
        """Verify resource attributes: service.name, host.name, os.type, etc."""
        from ai_cost_observer.telemetry import TelemetryManager
        from ai_cost_observer import __version__

        mock_exporter = MagicMock()
        mock_provider_cls.return_value.get_meter.return_value = MagicMock()

        config = AppConfig()
        config.host_name = "my-workstation"

        TelemetryManager(config, exporter=mock_exporter)

        mock_resource.create.assert_called_once()
        resource_attrs = mock_resource.create.call_args[0][0]

        assert resource_attrs["service.name"] == "ai-cost-observer"
        assert resource_attrs["service.version"] == __version__
        assert resource_attrs["host.name"] == "my-workstation"
        assert resource_attrs["os.type"] == platform.system().lower()
        assert resource_attrs["deployment.environment"] == "personal"

    @patch("ai_cost_observer.telemetry.metrics")
    @patch("ai_cost_observer.telemetry.MeterProvider")
    @patch("ai_cost_observer.telemetry.PeriodicExportingMetricReader")
    @patch("ai_cost_observer.telemetry.Resource")
    def test_telemetry_shutdown(
        self, mock_resource, mock_reader_cls, mock_provider_cls, mock_metrics
    ):
        """Verify provider.shutdown() is called on TelemetryManager.shutdown()."""
        from ai_cost_observer.telemetry import TelemetryManager

        mock_exporter = MagicMock()
        mock_provider = MagicMock()
        mock_provider_cls.return_value = mock_provider
        mock_provider.get_meter.return_value = MagicMock()

        config = AppConfig()
        tm = TelemetryManager(config, exporter=mock_exporter)
        tm.shutdown()

        mock_provider.shutdown.assert_called_once()

    @patch("ai_cost_observer.telemetry.metrics")
    @patch("ai_cost_observer.telemetry.MeterProvider")
    @patch("ai_cost_observer.telemetry.PeriodicExportingMetricReader")
    @patch("ai_cost_observer.telemetry.Resource")
    def test_telemetry_with_injected_exporter(
        self, mock_resource, mock_reader_cls, mock_provider_cls, mock_metrics
    ):
        """Verify custom exporter is used when injected (not the default)."""
        from ai_cost_observer.telemetry import TelemetryManager

        mock_exporter = MagicMock()
        mock_provider_cls.return_value.get_meter.return_value = MagicMock()

        config = AppConfig()
        tm = TelemetryManager(config, exporter=mock_exporter)

        # The injected exporter should be stored and passed to the reader
        assert tm.exporter is mock_exporter
        mock_reader_cls.assert_called_once_with(
            mock_exporter,
            export_interval_millis=config.scan_interval_seconds * 1000,
        )

    @patch("ai_cost_observer.telemetry.metrics")
    @patch("ai_cost_observer.telemetry.MeterProvider")
    @patch("ai_cost_observer.telemetry.PeriodicExportingMetricReader")
    @patch("ai_cost_observer.telemetry.Resource")
    def test_telemetry_grpc_exporter_selection(
        self, mock_resource, mock_reader_cls, mock_provider_cls, mock_metrics
    ):
        """Verify gRPC exporter is used by default when no exporter is injected."""
        from ai_cost_observer.telemetry import TelemetryManager

        mock_provider_cls.return_value.get_meter.return_value = MagicMock()

        with patch("ai_cost_observer.telemetry._create_exporter") as mock_create:
            mock_grpc_exporter = MagicMock()
            mock_create.return_value = mock_grpc_exporter

            config = AppConfig()
            config.otel_endpoint = "localhost:4317"
            tm = TelemetryManager(config)

            mock_create.assert_called_once_with(config)
            assert tm.exporter is mock_grpc_exporter

    @patch("ai_cost_observer.telemetry.metrics")
    @patch("ai_cost_observer.telemetry.MeterProvider")
    @patch("ai_cost_observer.telemetry.PeriodicExportingMetricReader")
    @patch("ai_cost_observer.telemetry.Resource")
    def test_cpu_memory_are_gauges_not_histograms(
        self, mock_resource, mock_reader_cls, mock_provider_cls, mock_metrics
    ):
        """Bug C3: cpu.usage and memory.usage must be Gauges, not Histograms.

        Histograms generate _bucket/_count/_sum metrics, but Grafana queries
        these as simple gauge values. Using Gauge produces a single value metric.
        """
        from ai_cost_observer.telemetry import TelemetryManager

        mock_exporter = MagicMock()
        mock_meter = MagicMock()
        mock_provider_cls.return_value.get_meter.return_value = mock_meter

        config = AppConfig()
        config.otel_endpoint = "localhost:4317"
        config.host_name = "test-host"

        TelemetryManager(config, exporter=mock_exporter)

        # cpu_usage and memory_usage should be created via create_gauge, not create_histogram
        gauge_names = [
            call.kwargs.get("name") or call.args[0]
            for call in mock_meter.create_gauge.call_args_list
        ]
        assert "ai.app.cpu.usage" in gauge_names, (
            "ai.app.cpu.usage should be a Gauge, not a Histogram"
        )
        assert "ai.app.memory.usage" in gauge_names, (
            "ai.app.memory.usage should be a Gauge, not a Histogram"
        )

        # Verify no Histograms are created for these metrics
        histogram_names = [
            call.kwargs.get("name") or call.args[0]
            for call in mock_meter.create_histogram.call_args_list
        ]
        assert "ai.app.cpu.usage" not in histogram_names, (
            "ai.app.cpu.usage should NOT be a Histogram"
        )
        assert "ai.app.memory.usage" not in histogram_names, (
            "ai.app.memory.usage should NOT be a Histogram"
        )

    @patch("ai_cost_observer.telemetry.metrics")
    @patch("ai_cost_observer.telemetry.MeterProvider")
    @patch("ai_cost_observer.telemetry.PeriodicExportingMetricReader")
    @patch("ai_cost_observer.telemetry.Resource")
    def test_running_counters_are_observable_gauges(
        self, mock_resource, mock_reader_cls, mock_provider_cls, mock_metrics
    ):
        """Bug H1: app_running and cli_running must be ObservableGauge, not UpDownCounter.

        UpDownCounter drifts on crash/restart because the decrement is never sent.
        ObservableGauge uses a callback that reports the current count at collection
        time, so a restart always starts from the correct state.
        """
        from ai_cost_observer.telemetry import TelemetryManager

        mock_exporter = MagicMock()
        mock_meter = MagicMock()
        mock_provider_cls.return_value.get_meter.return_value = mock_meter

        config = AppConfig()
        config.otel_endpoint = "localhost:4317"
        config.host_name = "test-host"

        TelemetryManager(config, exporter=mock_exporter)

        # Should use create_observable_gauge for running counters
        obs_gauge_names = [
            call.kwargs.get("name", call.args[0] if call.args else None)
            for call in mock_meter.create_observable_gauge.call_args_list
        ]
        assert "ai.app.running" in obs_gauge_names, (
            "ai.app.running must be an ObservableGauge"
        )
        assert "ai.cli.running" in obs_gauge_names, (
            "ai.cli.running must be an ObservableGauge"
        )

        # Should NOT use create_up_down_counter for these
        udc_names = [
            call.kwargs.get("name", call.args[0] if call.args else None)
            for call in mock_meter.create_up_down_counter.call_args_list
        ]
        assert "ai.app.running" not in udc_names, (
            "ai.app.running should NOT be an UpDownCounter"
        )
        assert "ai.cli.running" not in udc_names, (
            "ai.cli.running should NOT be an UpDownCounter"
        )

    @patch.dict("os.environ", {"OTEL_EXPORTER_OTLP_PROTOCOL": "http/json"})
    def test_telemetry_http_exporter_selection(self):
        """Verify HTTP exporter is used when protocol=http/json."""
        from ai_cost_observer.telemetry import _create_exporter

        config = AppConfig()
        config.otel_endpoint = "http://localhost:4318"
        config.otel_bearer_token = "test-token"

        mock_http_exporter = MagicMock()
        with patch.dict(
            "sys.modules",
            {"opentelemetry.exporter.otlp.proto.http.metric_exporter": MagicMock(
                OTLPMetricExporter=mock_http_exporter
            )}
        ):
            exporter = _create_exporter(config)

            mock_http_exporter.assert_called_once_with(
                endpoint="http://localhost:4318",
                headers={"authorization": "Bearer test-token"},
            )
