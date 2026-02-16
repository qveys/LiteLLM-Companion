# Loki Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add centralized log aggregation via Grafana Loki so agent loguru logs are queryable alongside metrics in Grafana.

**Architecture:** Python agent bridges loguru → stdlib logging → OTel LoggingHandler. Logs ship via the existing OTLP gRPC connection to the OTel Collector, which exports to Loki. Loki runs as a separate Dokploy compose (VPS) or as an extra service in the local docker-compose.

**Tech Stack:** Grafana Loki 3.4.2, OTel Collector contrib (loki exporter), OTel Python SDK logs API (already bundled with `opentelemetry-sdk` + `opentelemetry-exporter-otlp-proto-grpc`).

**Design doc:** `docs/plans/2026-02-16-loki-integration-design.md`

---

### Task 1: Loki Config File

**Files:**
- Create: `infra/loki-config.yaml`

**Step 1: Create the Loki configuration**

```yaml
# infra/loki-config.yaml
auth_enabled: false

server:
  http_listen_port: 3100

common:
  ring:
    instance_addr: 127.0.0.1
    kvstore:
      store: inmemory
  replication_factor: 1
  path_prefix: /loki

schema_config:
  configs:
    - from: "2024-01-01"
      store: tsdb
      object_store: filesystem
      schema: v13
      index:
        prefix: index_
        period: 24h

storage_config:
  filesystem:
    directory: /loki/chunks

limits_config:
  retention_period: 720h  # 30 days, matches Prometheus

compactor:
  working_directory: /loki/compactor
  retention_enabled: true
```

**Step 2: Commit**

```bash
git add infra/loki-config.yaml
git commit -m "feat(loki): add Loki config — TSDB v13, 30d retention, filesystem storage"
```

---

### Task 2: Dokploy Loki Compose (VPS Scenario)

**Files:**
- Create: `infra/loki/docker-compose.yml`

**Step 1: Create the Dokploy compose for Loki**

```yaml
# infra/loki/docker-compose.yml
#
# Standalone Loki compose for Dokploy.
# Deploy as a separate compose in the same "OpenTelemetry" project.
# Shares dokploy-network with the otel-stack compose so OTel Collector
# reaches loki:3100 by service name.

services:
  loki:
    image: grafana/loki:3.4.2
    restart: unless-stopped
    command: ["-config.file=/etc/loki/config.yaml"]
    volumes:
      - ../files/loki-config.yaml:/etc/loki/config.yaml:ro
      - loki-data:/loki
    networks:
      - dokploy-network

volumes:
  loki-data:

networks:
  dokploy-network:
    external: true
```

**Step 2: Commit**

```bash
git add infra/loki/docker-compose.yml
git commit -m "feat(loki): add Dokploy compose for standalone Loki service"
```

---

### Task 3: Add Loki to Local Docker Compose

**Files:**
- Modify: `infra/docker-compose.yml` (add loki service + volume)
- Modify: `infra/docker-compose.override.yml` (add loki volume remap)

**Step 1: Add loki service to `infra/docker-compose.yml`**

After the `grafana` service block (before `volumes:`), add:

```yaml
  loki:
    image: grafana/loki:3.4.2
    restart: unless-stopped
    command: ["-config.file=/etc/loki/config.yaml"]
    volumes:
      - ../files/loki-config.yaml:/etc/loki/config.yaml:ro
      - loki-data:/loki
    networks:
      - otel-net
```

Add `loki-data:` to the `volumes:` section.

Add `depends_on: [loki]` to the `otel-collector` service is NOT needed — the collector retries on its own.

**Step 2: Add loki override to `infra/docker-compose.override.yml`**

In the `services:` section, add:

```yaml
  loki:
    volumes:
      - ./loki-config.yaml:/etc/loki/config.yaml:ro
      - loki-data:/loki
```

**Step 3: Verify compose config is valid**

Run: `cd infra && docker compose config --quiet`
Expected: No errors (exit code 0)

**Step 4: Commit**

```bash
git add infra/docker-compose.yml infra/docker-compose.override.yml
git commit -m "feat(loki): add Loki service to local docker-compose"
```

---

### Task 4: OTel Collector — Loki Exporter + Logs Pipeline

**Files:**
- Modify: `infra/otel-collector-config.yaml`

**Step 1: Add loki exporter and logs pipeline**

In the `exporters:` section, add after the `prometheus:` block:

```yaml
  loki:
    endpoint: http://loki:3100/loki/api/v1/push
```

In the `service.pipelines:` section, add after the `metrics:` pipeline:

```yaml
    logs:
      receivers: [otlp]
      processors: [batch, resource]
      exporters: [loki]
```

The final file should look like:

```yaml
extensions:
  bearertokenauth:
    token: "${env:OTEL_BEARER_TOKEN}"

receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
        auth:
          authenticator: bearertokenauth
      http:
        endpoint: 0.0.0.0:4318
        auth:
          authenticator: bearertokenauth

processors:
  batch:
    timeout: 15s
    send_batch_size: 1024

  resource:
    attributes:
      - key: deployment.environment
        value: personal
        action: upsert

exporters:
  prometheus:
    endpoint: 0.0.0.0:8889
    resource_to_telemetry_conversion:
      enabled: true
    metric_expiration: 90m

  loki:
    endpoint: http://loki:3100/loki/api/v1/push

service:
  extensions: [bearertokenauth]
  pipelines:
    metrics:
      receivers: [otlp]
      processors: [batch, resource]
      exporters: [prometheus]
    logs:
      receivers: [otlp]
      processors: [batch, resource]
      exporters: [loki]
```

**Step 2: Commit**

```bash
git add infra/otel-collector-config.yaml
git commit -m "feat(otel-collector): add loki exporter and logs pipeline"
```

---

### Task 5: Grafana Loki Datasource Provisioning

**Files:**
- Create: `infra/grafana/provisioning/datasources/loki.yaml`

**Step 1: Create the datasource provisioning file**

```yaml
apiVersion: 1

datasources:
  - name: Loki
    type: loki
    uid: loki-vps
    access: proxy
    url: http://loki:3100
    editable: false
```

This follows the exact same pattern as `infra/grafana/provisioning/datasources/prometheus.yaml`.

**Step 2: Commit**

```bash
git add infra/grafana/provisioning/datasources/loki.yaml
git commit -m "feat(grafana): provision Loki datasource alongside Prometheus"
```

---

### Task 6: Agent Python — Write Failing Tests for Log Bridge

**Files:**
- Modify: `tests/test_telemetry.py`

**Step 1: Write test for LoggerProvider creation**

Add this test class at the end of `tests/test_telemetry.py`:

```python
class TestLogBridge:
    """Verify the loguru → OTel log bridge is wired up."""

    @patch("ai_cost_observer.telemetry.set_logger_provider")
    @patch("ai_cost_observer.telemetry.BatchLogRecordProcessor")
    @patch("ai_cost_observer.telemetry.LoggerProvider")
    @patch("ai_cost_observer.telemetry.LoggingHandler")
    @patch("ai_cost_observer.telemetry.metrics")
    @patch("ai_cost_observer.telemetry.MeterProvider")
    @patch("ai_cost_observer.telemetry.PeriodicExportingMetricReader")
    @patch("ai_cost_observer.telemetry.Resource")
    def test_logger_provider_created(
        self,
        mock_resource,
        mock_reader_cls,
        mock_provider_cls,
        mock_metrics,
        mock_logging_handler,
        mock_log_provider_cls,
        mock_batch_processor,
        mock_set_logger_provider,
    ):
        """LoggerProvider is created, registered, and receives a BatchLogRecordProcessor."""
        from ai_cost_observer.telemetry import TelemetryManager

        mock_exporter = MagicMock()
        mock_provider_cls.return_value.get_meter.return_value = MagicMock()

        config = AppConfig()
        config.otel_endpoint = "localhost:4317"
        config.host_name = "test-host"

        TelemetryManager(config, exporter=mock_exporter)

        # LoggerProvider was created with the same resource
        mock_log_provider_cls.assert_called_once()
        # BatchLogRecordProcessor was added
        mock_log_provider_cls.return_value.add_log_record_processor.assert_called_once()
        # set_logger_provider was called
        mock_set_logger_provider.assert_called_once_with(mock_log_provider_cls.return_value)

    @patch("ai_cost_observer.telemetry.set_logger_provider")
    @patch("ai_cost_observer.telemetry.BatchLogRecordProcessor")
    @patch("ai_cost_observer.telemetry.LoggerProvider")
    @patch("ai_cost_observer.telemetry.LoggingHandler")
    @patch("ai_cost_observer.telemetry.metrics")
    @patch("ai_cost_observer.telemetry.MeterProvider")
    @patch("ai_cost_observer.telemetry.PeriodicExportingMetricReader")
    @patch("ai_cost_observer.telemetry.Resource")
    def test_loguru_handler_added(
        self,
        mock_resource,
        mock_reader_cls,
        mock_provider_cls,
        mock_metrics,
        mock_logging_handler,
        mock_log_provider_cls,
        mock_batch_processor,
        mock_set_logger_provider,
    ):
        """A LoggingHandler is added to the loguru logger."""
        from ai_cost_observer.telemetry import TelemetryManager

        mock_exporter = MagicMock()
        mock_provider_cls.return_value.get_meter.return_value = MagicMock()

        config = AppConfig()
        config.otel_endpoint = "localhost:4317"
        config.host_name = "test-host"

        with patch("ai_cost_observer.telemetry.logger") as mock_loguru:
            TelemetryManager(config, exporter=mock_exporter)
            # loguru.add() was called with the OTel handler
            mock_loguru.add.assert_called_once()
            call_args = mock_loguru.add.call_args
            assert call_args[0][0] is mock_logging_handler.return_value

    @patch("ai_cost_observer.telemetry.set_logger_provider")
    @patch("ai_cost_observer.telemetry.BatchLogRecordProcessor")
    @patch("ai_cost_observer.telemetry.LoggerProvider")
    @patch("ai_cost_observer.telemetry.LoggingHandler")
    @patch("ai_cost_observer.telemetry.metrics")
    @patch("ai_cost_observer.telemetry.MeterProvider")
    @patch("ai_cost_observer.telemetry.PeriodicExportingMetricReader")
    @patch("ai_cost_observer.telemetry.Resource")
    def test_log_provider_shutdown(
        self,
        mock_resource,
        mock_reader_cls,
        mock_provider_cls,
        mock_metrics,
        mock_logging_handler,
        mock_log_provider_cls,
        mock_batch_processor,
        mock_set_logger_provider,
    ):
        """LoggerProvider is shut down alongside MeterProvider."""
        from ai_cost_observer.telemetry import TelemetryManager

        mock_exporter = MagicMock()
        mock_meter_provider = MagicMock()
        mock_provider_cls.return_value = mock_meter_provider
        mock_meter_provider.get_meter.return_value = MagicMock()

        config = AppConfig()
        tm = TelemetryManager(config, exporter=mock_exporter)
        tm.shutdown()

        mock_meter_provider.shutdown.assert_called_once()
        mock_log_provider_cls.return_value.shutdown.assert_called_once()
```

**Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_telemetry.py::TestLogBridge -v`
Expected: FAIL — the imports (`LoggerProvider`, `LoggingHandler`, etc.) don't exist in `telemetry.py` yet.

**Step 3: Commit the failing tests**

```bash
git add tests/test_telemetry.py
git commit -m "test(telemetry): add failing tests for loguru → OTel log bridge"
```

---

### Task 7: Agent Python — Implement Log Bridge

**Files:**
- Modify: `src/ai_cost_observer/telemetry.py`

**Step 1: Add log SDK imports**

At the top of the file, after the existing imports (line 17), add:

```python
import logging

from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
```

**Step 2: Add `_create_log_exporter` function**

After the existing `_create_exporter` function (after line 49), add:

```python
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
```

**Step 3: Wire up LoggerProvider in `TelemetryManager.__init__`**

In `__init__`, after the line `self.meter = self.provider.get_meter(...)` (line 75) and before the `_prev_running_*` tracking dicts (line 77), add:

```python
        # --- Log pipeline: loguru → stdlib logging → OTel ---
        log_exporter = _create_log_exporter(config)
        self._log_provider = LoggerProvider(resource=self.resource)
        self._log_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))
        set_logger_provider(self._log_provider)

        otel_handler = LoggingHandler(level=logging.DEBUG, logger_provider=self._log_provider)
        logger.add(otel_handler, level="INFO", format="{message}")
```

**Step 4: Shut down LoggerProvider in `shutdown()`**

In the `shutdown()` method, before `self.provider.shutdown()`, add:

```python
        self._log_provider.shutdown()
```

**Step 5: Run all tests**

Run: `uv run python -m pytest tests/test_telemetry.py -v`
Expected: ALL PASS (including the 3 new tests from Task 6)

**Step 6: Run full test suite to check for regressions**

Run: `uv run python -m pytest --tb=short -q`
Expected: All 373+ tests pass (370 existing + 3 new)

**Step 7: Commit**

```bash
git add src/ai_cost_observer/telemetry.py
git commit -m "feat(telemetry): add loguru → OTel log bridge for Loki integration

LoggerProvider ships agent logs via the same OTLP connection used
for metrics. loguru.add(LoggingHandler) captures all log output
from all 12 source files automatically. Supports both gRPC and
HTTP protocols."
```

---

### Task 8: Integration Smoke Test

**Step 1: Verify infra can start locally**

Run: `cd infra && docker compose config --quiet && echo "OK"`
Expected: `OK` (compose config valid with new loki service)

**Step 2: Verify Python agent imports work**

Run: `uv run python -c "from ai_cost_observer.telemetry import TelemetryManager; print('Import OK')"`
Expected: `Import OK`

**Step 3: Verify Loki config syntax**

Run: `docker run --rm -v $(pwd)/infra/loki-config.yaml:/etc/loki/config.yaml grafana/loki:3.4.2 -config.file=/etc/loki/config.yaml -verify-config 2>&1 | head -5`
Expected: No errors (Loki validates its config)

**Step 4: Run lint**

Run: `uv run ruff check src/ai_cost_observer/telemetry.py`
Expected: No errors

---

### Task 9: Deploy to VPS via Dokploy

This task requires manual Dokploy interaction and VPS access.

**Step 1: Push branch**

```bash
git push -u origin claude/relaxed-tereshkova
```

**Step 2: Deploy Loki compose on Dokploy**

Using the Dokploy MCP tools:
1. Create a new compose service "loki" in the "OpenTelemetry" project
2. Set the compose file content to `infra/loki/docker-compose.yml`
3. Upload `infra/loki-config.yaml` to the Dokploy files directory
4. Deploy the compose

**Step 3: Update OTel Collector config on VPS**

SCP the updated `infra/otel-collector-config.yaml` to the VPS files path and restart the otel-stack compose.

**Step 4: Update Grafana datasources on VPS**

SCP `infra/grafana/provisioning/datasources/loki.yaml` to the VPS files path and reload Grafana provisioning.

**Step 5: Verify in Grafana**

1. Go to Grafana → Explore
2. Select "Loki" datasource
3. Run query: `{service_name="ai-cost-observer"}`
4. Confirm agent logs appear
