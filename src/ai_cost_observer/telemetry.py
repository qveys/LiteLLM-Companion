"""OpenTelemetry SDK setup — Resource, MeterProvider, all metric instruments."""

from __future__ import annotations

import logging
import os
import platform
from typing import Optional

from loguru import logger
from opentelemetry import metrics
from opentelemetry._logs import set_logger_provider
from opentelemetry.metrics import Observation
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    MetricExporter,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.resources import Resource

from ai_cost_observer import __version__
from ai_cost_observer.config import AppConfig


def _create_exporter(config: AppConfig) -> MetricExporter:
    """Create an OTLP metric exporter based on config and environment."""
    protocol = os.environ.get(
        "OTEL_EXPORTER_OTLP_METRICS_PROTOCOL", os.environ.get("OTEL_EXPORTER_OTLP_PROTOCOL", "grpc")
    )

    headers = {}
    if config.otel_bearer_token:
        headers["authorization"] = f"Bearer {config.otel_bearer_token}"

    if protocol == "http/json":
        logger.debug("Using OTLP/HTTP JSON exporter.")
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter

        return OTLPMetricExporter(endpoint=config.otel_endpoint, headers=headers)

    logger.debug("Using OTLP/gRPC exporter (default).")
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter

    grpc_endpoint = (
        config.otel_endpoint.replace("http://", "").replace("https://", "").split("/")[0]
    )
    return OTLPMetricExporter(
        endpoint=grpc_endpoint,
        headers=tuple(headers.items()),
        insecure=config.otel_insecure,
    )


def _create_log_exporter(config: AppConfig):
    """Create an OTLP log exporter matching the metric exporter protocol."""
    protocol = os.environ.get(
        "OTEL_EXPORTER_OTLP_LOGS_PROTOCOL",
        os.environ.get("OTEL_EXPORTER_OTLP_PROTOCOL", "grpc"),
    )

    headers = {}
    if config.otel_bearer_token:
        headers["authorization"] = f"Bearer {config.otel_bearer_token}"

    if protocol == "http/json":
        from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter

        return OTLPLogExporter(endpoint=config.otel_endpoint, headers=headers)

    from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter

    grpc_endpoint = (
        config.otel_endpoint.replace("http://", "").replace("https://", "").split("/")[0]
    )
    return OTLPLogExporter(
        endpoint=grpc_endpoint,
        headers=tuple(headers.items()),
        insecure=config.otel_insecure,
    )


class TelemetryManager:
    """Manages OTel SDK lifecycle and provides all metric instruments."""

    def __init__(self, config: AppConfig, exporter: Optional[MetricExporter] = None) -> None:
        self.config = config
        self.resource = Resource.create(
            {
                "service.name": "ai-cost-observer",
                "service.version": __version__,
                "host.name": config.host_name,
                "os.type": platform.system().lower(),
                "deployment.environment": "personal",
            }
        )

        self.exporter = exporter if exporter is not None else _create_exporter(config)

        self.reader = PeriodicExportingMetricReader(
            self.exporter,
            export_interval_millis=config.scan_interval_seconds * 1000,
        )
        self.provider = MeterProvider(resource=self.resource, metric_readers=[self.reader])
        metrics.set_meter_provider(self.provider)
        self.meter = self.provider.get_meter("ai-cost-observer", __version__)

        # --- Log pipeline: loguru → stdlib logging → OTel ---
        log_exporter = _create_log_exporter(config)
        self._log_provider = LoggerProvider(resource=self.resource)
        self._log_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))
        set_logger_provider(self._log_provider)

        otel_handler = LoggingHandler(level=logging.DEBUG, logger_provider=self._log_provider)
        logger.add(otel_handler, level="INFO", format="{message}")

        # --- Snapshots for ObservableGauge callbacks (Bug H1) ---
        # Detectors write to these dicts; ObservableGauge callbacks read them.
        # Key = app/tool name, Value = OTel attribute dict (labels).
        self._running_apps: dict[str, dict] = {}
        self._running_cli: dict[str, dict] = {}
        self._running_wsl: dict[str, dict] = {}
        self._prev_running_apps: dict[str, dict] = {}
        self._prev_running_cli: dict[str, dict] = {}

        # --- Metric Instruments ---
        self.app_running = self.meter.create_observable_gauge(
            name="ai.app.running",
            callbacks=[self._observe_app_running],
        )
        self.app_active_duration = self.meter.create_counter(
            name="ai.app.active.duration",
            unit="s",
        )
        self.app_cpu_usage = self.meter.create_gauge(
            name="ai.app.cpu.usage",
            unit="%",
        )
        self.app_memory_usage = self.meter.create_gauge(
            name="ai.app.memory.usage",
            unit="MB",
        )
        self.app_estimated_cost = self.meter.create_counter(
            name="ai.app.estimated.cost",
            unit="USD",
        )
        self.browser_domain_active_duration = self.meter.create_counter(
            name="ai.browser.domain.active.duration",
            unit="s",
        )
        self.browser_domain_visit_count = self.meter.create_counter(
            name="ai.browser.domain.visit.count",
            unit="1",
        )
        self.browser_domain_estimated_cost = self.meter.create_counter(
            name="ai.browser.domain.estimated.cost",
            unit="USD",
        )
        self.cli_running = self.meter.create_observable_gauge(
            name="ai.cli.running",
            callbacks=[self._observe_cli_running],
        )
        self.cli_active_duration = self.meter.create_counter(
            name="ai.cli.active.duration",
            unit="s",
        )
        self.cli_estimated_cost = self.meter.create_counter(
            name="ai.cli.estimated.cost",
            unit="USD",
        )
        self.cli_command_count = self.meter.create_counter(
            name="ai.cli.command.count",
            unit="1",
        )
        self.tokens_input_total = self.meter.create_counter(
            name="ai.tokens.input",
            unit="1",
        )
        self.tokens_output_total = self.meter.create_counter(
            name="ai.tokens.output",
            unit="1",
        )
        self.tokens_cost_usd_total = self.meter.create_counter(
            name="ai.tokens.cost_usd",
            unit="1",
        )
        self.prompt_count_total = self.meter.create_counter(
            name="ai.prompt.count",
            unit="1",
        )

        logger.debug("TelemetryManager initialized.")

    def set_running_apps(self, running: dict[str, dict]) -> None:
        """Update the snapshot of currently running desktop AI apps.

        Called by DesktopDetector after each scan. The dict maps
        app_name -> attribute labels used in the ObservableGauge callback.
        """
        self._running_apps = dict(running)

    def set_running_cli(self, running: dict[str, dict]) -> None:
        """Update the snapshot of currently running CLI AI tools.

        Called by CLIDetector after each scan.
        """
        self._running_cli = dict(running)

    def set_running_wsl(self, running: dict[str, dict]) -> None:
        """Update the snapshot of currently running WSL AI tools.

        Called by WSLDetector after each scan.
        """
        self._running_wsl = dict(running)

    def _observe_app_running(self, options):
        """ObservableGauge callback: yield one Observation per running app.

        Emits 0 for apps that were running last cycle but stopped, so
        Prometheus drops the stale series instead of keeping the last value.
        """
        for _name, labels in self._running_apps.items():
            yield Observation(1, labels)
        for name, labels in self._prev_running_apps.items():
            if name not in self._running_apps:
                yield Observation(0, labels)
        self._prev_running_apps = dict(self._running_apps)

    def _observe_cli_running(self, options):
        """ObservableGauge callback: yield one Observation per running CLI tool."""
        current = {**self._running_cli, **self._running_wsl}
        for _name, labels in current.items():
            yield Observation(1, labels)
        for name, labels in self._prev_running_cli.items():
            if name not in current:
                yield Observation(0, labels)
        self._prev_running_cli = dict(current)

    def shutdown(self) -> None:
        """Flush pending metrics and shut down the provider."""
        logger.info("Flushing metrics and shutting down OTel provider...")
        self._log_provider.shutdown()
        self.provider.shutdown()
        logger.info("OTel provider shut down.")
