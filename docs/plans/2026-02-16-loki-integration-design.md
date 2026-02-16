# Loki Integration Design

**Date:** 2026-02-16
**Status:** Approved

## Goal

Add centralized log aggregation to the AI Cost Observer stack via Grafana Loki, so agent logs (loguru) are queryable alongside metrics in Grafana.

## Architecture

```
Mac / Windows / Linux (Agent Python)
┌──────────────────────────────┐
│ loguru handlers:             │    OTLP gRPC (+TLS +bearer)
│  • stderr (local, unchanged) │──────────────────────────────┐
│  • OTel LoggingHandler (new) │                              │
│                              │                              │
│ Metrics (unchanged)          │──────────────────────────────┤
└──────────────────────────────┘                              │
                                                              ▼
                                              ┌── OTel Collector :4317 ──┐
                                              │  metrics pipeline:       │
                                              │    otlp → prometheus     │
                                              │  logs pipeline (new):    │
                                              │    otlp → loki           │
                                              └──────────┬───────────────┘
                                                         │
                          ┌──────────────────────────────┐│
                          ▼                              ▼│
                       Prometheus :9090           Loki :3100
                          │                              │
                          └──────────┬───────────────────┘
                                     ▼
                                  Grafana :3000
                                  (Prometheus + Loki datasources)
```

## Deployment Scenarios

### A. VPS / Dokploy (production)

Loki runs as a **separate compose** in the same Dokploy project "OpenTelemetry". Both composes share `dokploy-network`, so OTel Collector reaches `loki:3100` by service name.

- `otel-stack` compose: OTel Collector + Prometheus + Grafana (existing)
- `loki` compose: Loki standalone (new)

### B. Docker local (self-hosted, no VPS)

Loki is added as a service in the existing `infra/docker-compose.yml`. Everything runs on `localhost` in a single compose.

## Components

### 1. Loki Container

- **Image:** `grafana/loki:3.4.2`
- **Storage:** filesystem (single-node, personal use)
- **Retention:** 30 days (matches Prometheus)
- **Auth:** disabled (internal network only)
- **Schema:** TSDB v13

### 2. OTel Collector — Logs Pipeline

Add to existing `otel-collector-config.yaml`:

```yaml
exporters:
  loki:
    endpoint: http://loki:3100/loki/api/v1/push

service:
  pipelines:
    logs:
      receivers: [otlp]
      processors: [batch, resource]
      exporters: [loki]
```

The OTLP receiver already accepts logs on both gRPC and HTTP. Same bearer token auth. The `contrib` collector image includes the Loki exporter natively.

### 3. Agent Python — Loguru to OTel Bridge

In `telemetry.py`, add an OTel LoggerProvider that ships logs via OTLP:

```python
from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor

# In TelemetryManager.__init__:
log_exporter = _create_log_exporter(config)
log_provider = LoggerProvider(resource=self.resource)
log_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))
set_logger_provider(log_provider)

# Bridge: loguru → stdlib logging → OTel
otel_handler = LoggingHandler(level=logging.DEBUG, logger_provider=log_provider)
loguru_logger.add(otel_handler, level="INFO", format="{message}")
```

This is fully cross-platform (macOS, Windows, Linux). All 12 source files using `from loguru import logger` are automatically covered.

### 4. Grafana Datasource Provisioning

New file `grafana/provisioning/datasources/loki.yaml`:

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

### 5. Dependencies

Verify `opentelemetry-exporter-otlp-proto-grpc` covers log export (it does since SDK 1.20+). No new PyPI dependency needed.

## File Changes

| File | Action |
|------|--------|
| `infra/loki/docker-compose.yml` | New — Dokploy compose for Loki |
| `infra/loki-config.yaml` | New — Loki config (shared both scenarios) |
| `infra/docker-compose.yml` | Add loki service (local scenario) |
| `infra/docker-compose.override.yml` | Add loki volume remap |
| `infra/otel-collector-config.yaml` | Add loki exporter + logs pipeline |
| `infra/grafana/provisioning/datasources/loki.yaml` | New — Loki datasource |
| `src/ai_cost_observer/telemetry.py` | Add LoggerProvider + loguru OTel handler |

## Out of Scope (V1)

- Docker log driver for VPS container logs
- Dedicated logs dashboard (Grafana Explore suffices)
- Log-based alerting
- Structured log fields beyond severity/message
