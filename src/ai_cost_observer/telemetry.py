"""OpenTelemetry SDK setup — Resource, MeterProvider, all metric instruments."""

from __future__ import annotations

import os
import platform
from typing import Optional

from loguru import logger
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader, MetricExporter
from opentelemetry.sdk.resources import Resource

from ai_cost_observer import __version__
from ai_cost_observer.config import AppConfig


def _create_exporter(config: AppConfig) -> MetricExporter:
    """Create an OTLP metric exporter based on config and environment."""
    protocol = os.environ.get("OTEL_EXPORTER_OTLP_METRICS_PROTOCOL", 
                            os.environ.get("OTEL_EXPORTER_OTLP_PROTOCOL", "grpc"))

    headers = {}
    if config.otel_bearer_token:
        headers["authorization"] = f"Bearer {config.otel_bearer_token}"

    if protocol == "http/json":
        logger.debug("Using OTLP/HTTP JSON exporter.")
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
        return OTLPMetricExporter(endpoint=config.otel_endpoint, headers=headers)
    
    logger.debug("Using OTLP/gRPC exporter (default).")
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
    grpc_endpoint = config.otel_endpoint.replace("http://", "").replace("https://", "").split("/")[0]
    return OTLPMetricExporter(
        endpoint=grpc_endpoint,
        headers=tuple(headers.items()),
        insecure=config.otel_insecure,
    )


class TelemetryManager:
    """Manages OTel SDK lifecycle and provides all metric instruments."""

    def __init__(self, config: AppConfig, exporter: Optional[MetricExporter] = None) -> None:
        self.config = config
        self.resource = Resource.create({
            "service.name": "ai-cost-observer",
            "service.version": __version__,
            "host.name": config.host_name,
            "os.type": platform.system().lower(),
            "deployment.environment": "personal",
        })

        self.exporter = exporter if exporter is not None else _create_exporter(config)

        self.reader = PeriodicExportingMetricReader(
            self.exporter,
            export_interval_millis=config.scan_interval_seconds * 1000,
        )
        self.provider = MeterProvider(resource=self.resource, metric_readers=[self.reader])
        metrics.set_meter_provider(self.provider)
        self.meter = self.provider.get_meter("ai-cost-observer", __version__)

        # --- Metric Instruments ---
        self.app_running = self.meter.create_up_down_counter(name="ai.app.running", unit="1")
        self.app_active_duration = self.meter.create_counter(name="ai.app.active.duration", unit="s")
        self.app_cpu_usage = self.meter.create_gauge(name="ai.app.cpu.usage", unit="%")
        self.app_memory_usage = self.meter.create_gauge(name="ai.app.memory.usage", unit="MB")
        self.app_estimated_cost = self.meter.create_counter(name="ai.app.estimated.cost", unit="USD")
        self.browser_domain_active_duration = self.meter.create_counter(name="ai.browser.domain.active.duration", unit="s")
        self.browser_domain_visit_count = self.meter.create_counter(name="ai.browser.domain.visit.count", unit="1")
        self.browser_domain_estimated_cost = self.meter.create_counter(name="ai.browser.domain.estimated.cost", unit="USD")
        self.cli_running = self.meter.create_up_down_counter(name="ai.cli.running", unit="1")
        self.cli_active_duration = self.meter.create_counter(name="ai.cli.active.duration", unit="s")
        self.cli_estimated_cost = self.meter.create_counter(name="ai.cli.estimated.cost", unit="USD")
        self.cli_command_count = self.meter.create_counter(name="ai.cli.command.count", unit="1")
        self.tokens_input_total = self.meter.create_counter(name="ai.tokens.input_total", unit="1")
        self.tokens_output_total = self.meter.create_counter(name="ai.tokens.output_total", unit="1")
        self.tokens_cost_usd_total = self.meter.create_counter(name="ai.tokens.cost_usd_total", unit="1")
        self.prompt_count_total = self.meter.create_counter(name="ai.prompt.count_total", unit="1")

        logger.debug("TelemetryManager initialized.")

    def shutdown(self) -> None:
        """Flush pending metrics and shut down the provider."""
        logger.info("Flushing metrics and shutting down OTel provider...")
        self.provider.shutdown()
        logger.info("OTel provider shut down.")
