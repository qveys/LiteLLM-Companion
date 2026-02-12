# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**AI Cost Observer** — a cross-platform (macOS/Windows) Python agent that tracks personal AI tool spending across desktop apps, browsers, and CLI tools. Metrics are shipped via OpenTelemetry (OTLP gRPC + TLS + bearer token) to a centralized VPS running OTel Collector → Prometheus → Grafana.

## Project Status

V0 release (tag v0.1.0). 336 tests passing. 19/21 bugs fixed. CI/CD active.
See `docs/consolidation-report.md` for full status and `docs/roadmap-v1.md` for next steps.

**Open issues:** #44 (WSL ObservableGauge compat), #45 (HTTP tokens fallback cost).

## Build & Run Commands

```bash
# Install
uv sync                    # or: pip install -e .
uv sync --extra macos      # macOS native window tracking
uv sync --extra windows    # Windows native window tracking

# Run agent
python -m ai_cost_observer

# Install dev deps
uv sync --extra dev

# Tests (336 tests)
uv run python -m pytest
uv run python -m pytest tests/test_desktop.py           # single test file
uv run python -m pytest tests/test_desktop.py::test_fn  # single test function

# Infrastructure (VPS)
cd infra && docker compose up -d
```

## Architecture

```
Workstation (Python agent)          VPS (vps.quentinveys.be / Dokploy)
┌─────────────────────────┐        ┌───────────────────────────┐
│ Detectors:              │  OTLP  │ OTel Collector :4317      │
│  desktop (psutil+window)│──gRPC──│  → Prometheus :9090       │
│  browser_history (8 DBs)│ +TLS  │  → Grafana :3000          │
│  cli (psutil+dedup)     │ +token │    (4 dashboards)         │
│  shell_history (hourly) │        └───────────────────────────┘
│  token_tracker (JSONL)  │
│  wsl (Windows only)     │
│ HTTP Receiver :8080     │←── Chrome Extension (localhost)
│ TelemetryManager (OTel) │
└─────────────────────────┘
```

**Threading model:** Main loop (desktop+CLI scan, 15s) + Flask HTTP receiver (daemon thread) + browser history scanner (daemon, 60s) + shell history parser (daemon, 3600s) + token tracker (daemon, 300s) + OTel PeriodicExportingMetricReader (15s).

**Config hierarchy:** Built-in `src/ai_cost_observer/data/ai_config.yaml` → user `~/.config/ai-cost-observer/config.yaml` → env vars (`OTEL_ENDPOINT`, `OTEL_BEARER_TOKEN`).

## Key Directories

- `src/ai_cost_observer/` — Python package (detectors/, server/, platform/, data/)
- `infra/` — Docker Compose stack for VPS (OTel Collector, Prometheus, Grafana)
- `chrome-extension/` — Manifest V3 extension for real-time browser tracking
- `service/` — Daemon install scripts (launchd plist, Task Scheduler)
- `docs/` — Design docs (product-brief, architecture, stories)

## OTel Metric Naming

All metrics use `ai.` namespace. Prometheus names are auto-converted: `ai.app.running` → `ai_app_running` (no `ai_cost_observer_` prefix; scope name goes to `otel_scope_name` label).

16 metrics across 4 categories: `ai.app.*` (desktop), `ai.browser.domain.*` (browser), `ai.cli.*` (CLI), `ai.tokens.*` / `ai.prompt.*` (token tracking). Cost metrics use `unit="1"` to avoid double `_USD_total` suffix. Token/prompt counters use names without `_total` suffix (e.g., `ai.tokens.input` not `ai.tokens.input_total`) — Prometheus adds `_total` automatically. `ai.app.running` and `ai.cli.running` are ObservableGauge (not UpDownCounter). `ai.app.cpu.usage` and `ai.app.memory.usage` are Gauge (not Histogram). See `docs/architecture.md` for the full metric table.

Resource attributes on all metrics: `service.name=ai-cost-observer`, `host.name`, `os.type`, `service.version`, `deployment.environment=personal`.

## Cross-Platform Patterns

- Active window: `NSWorkspace` (macOS, via pyobjc) / `win32gui` (Windows, via pywin32) / `osascript` fallback
- Process names differ: `ChatGPT` vs `ChatGPT.exe`
- Browser history paths are OS-specific (see `docs/architecture.md`)
- WSL detector is Windows-only, no-ops on macOS
- Platform deps are optional: `pyobjc-framework-Cocoa` (macOS), `pywin32` (Windows)

## Error Handling Conventions

- **Never crash the main loop.** Each detector scan is wrapped in try/except; log and continue.
- psutil errors (`NoSuchProcess`, `AccessDenied`, `ZombieProcess`) are expected — catch at every process access.
- Browser history DB may be locked — copy-to-temp strategy, log warnings, return empty.
- OTel export failures are transient — built-in retry, agent continues if VPS is down.
- SQL queries must use parameterized statements (no f-strings).

## Infrastructure

- **VPS:** Dokploy on `vps.quentinveys.be` with Traefik
- **Auth:** Bearer token on OTel Collector (`bearertokenauth` extension)
- **Retention:** Prometheus 30d TSDB retention
- **Ports:** 4317 (OTLP gRPC), 4318 (OTLP HTTP), 3000 (Grafana), 8889 (Prometheus exporter, internal)



===

### Note

When you complete a task, send me a push notification:

```curl
curl -X POST https://api.getmoshi.app/api/webhook \
  -H "Content-Type: application/json" \
  -d '{"token": "WjwEOBwl3AxCfvkiW0wUG6OuZaRF04EF", "title": "Done", "message": "Brief summary", "image": "optional http url"}'
```
