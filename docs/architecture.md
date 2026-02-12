# Architecture: AI Cost Observer

## System Overview

```
┌──────────────────────────────────────────────────┐
│                  Workstation (macOS / Windows)     │
│                                                    │
│  ┌──────────────────────────────────────────────┐ │
│  │           ai-cost-observer (Python agent)     │ │
│  │                                                │ │
│  │  ┌────────────┐ ┌──────────────┐ ┌──────────┐│ │
│  │  │  Desktop    │ │  Browser     │ │  CLI     ││ │
│  │  │  Detector   │ │  History     │ │  Detector││ │
│  │  │  (psutil +  │ │  Parser      │ │  (psutil)││ │
│  │  │  active_win)│ │  (SQLite)    │ │          ││ │
│  │  └─────┬──────┘ └──────┬───────┘ └────┬─────┘│ │
│  │        │               │               │      │ │
│  │  ┌─────┴───────────────┴───────────────┴────┐ │ │
│  │  │         TelemetryManager (OTel SDK)       │ │ │
│  │  │  MeterProvider → PeriodicExportingReader  │ │ │
│  │  │  → OTLPMetricExporter (gRPC + auth)        │ │ │
│  │  └──────────────────┬───────────────────────┘ │ │
│  │                     │                          │ │
│  │  ┌────────────────┐ │  ┌──────────────────┐   │ │
│  │  │ Shell History  │ │  │  HTTP Receiver    │   │ │
│  │  │ Parser (hourly)│ │  │  (Flask :8080)    │   │ │
│  │  └────────────────┘ │  └────────┬─────────┘   │ │
│  │                     │           │              │ │
│  └─────────────────────┼───────────┼──────────────┘ │
│                        │           │                 │
│  ┌─────────────────────┼───────────┘                │
│  │ Chrome Extension    │ (localhost POST /metrics)   │
│  │ (Manifest V3)       │                             │
│  └─────────────────────┘                             │
└──────────────────┬───────────────────────────────────┘
                   │ OTLP gRPC + Bearer token (insecure)
                   ↓
┌──────────────────────────────────────────────────────┐
│            vps.quentinveys.be (Dokploy)               │
│                                                        │
│  ┌──────────────────┐                                  │
│  │  OTel Collector   │ :4317 (gRPC, bearertokenauth)   │
│  │  → batch + resource processor                       │
│  │  → prometheus exporter :8889                        │
│  └────────┬─────────┘                                  │
│           ↓                                            │
│  ┌──────────────────┐                                  │
│  │  Prometheus       │ :9090 (internal)                 │
│  │  scrapes :8889    │ 30d retention                    │
│  └────────┬─────────┘                                  │
│           ↓                                            │
│  ┌──────────────────┐                                  │
│  │  Grafana          │ :3000 (exposed via Traefik)      │
│  │  4 dashboards     │ $host filter for multi-device    │
│  └──────────────────┘                                  │
└──────────────────────────────────────────────────────┘
```

## Module Responsibilities

| Module | File | Responsibility |
|--------|------|---------------|
| **config** | `src/ai_cost_observer/config.py` | Load YAML config, merge user overrides, provide `AppConfig` dataclass |
| **telemetry** | `src/ai_cost_observer/telemetry.py` | OTel SDK lifecycle: Resource, MeterProvider, all 16 metric instruments, OTLP exporter with bearer token auth |
| **main** | `src/ai_cost_observer/main.py` | Orchestration: main loop (15s), daemon threads, signal handling, graceful shutdown |
| **desktop detector** | `src/ai_cost_observer/detectors/desktop.py` | psutil process scan for AI desktop apps, stateful PID tracking, UpDownCounter management |
| **active window** | `src/ai_cost_observer/detectors/active_window.py` | OS-dispatch to get foreground app name (macOS → AppKit/osascript, Windows → win32gui) |
| **browser history** | `src/ai_cost_observer/detectors/browser_history.py` | SQLite parser for 8 browsers (Chrome, Edge, Brave, Arc, Vivaldi, Opera, Firefox, Safari), copy-to-temp strategy, session duration estimation |
| **CLI detector** | `src/ai_cost_observer/detectors/cli.py` | psutil scan for CLI AI processes (ollama, claude-code, aider, gemini-cli, codex-cli, vibe, etc.), case-sensitive dedup with desktop detector, PID tracking |
| **shell history** | `src/ai_cost_observer/detectors/shell_history.py` | Incremental parser for zsh/bash/PowerShell history, byte offset persistence |
| **WSL detector** | `src/ai_cost_observer/detectors/wsl.py` | Windows-only: detect AI processes inside WSL via `wsl -e ps aux`, read WSL shell history |
| **HTTP receiver** | `src/ai_cost_observer/server/http_receiver.py` | Flask endpoint on localhost:8080 for Chrome extension metrics, bridges to OTel |
| **platform/macos** | `src/ai_cost_observer/platform/macos.py` | NSWorkspace active window, osascript fallback |
| **token tracker** | `src/ai_cost_observer/detectors/token_tracker.py` | Parses CLI tool JSONL logs (Claude Code, Codex, Gemini) for token usage, maps to MODEL_PRICING for cost estimation |
| **platform/windows** | `src/ai_cost_observer/platform/windows.py` | win32gui active window |

## Data Flow

```
1. Detectors (every 15s):
   desktop.scan() → list[DesktopSnapshot]
   cli.scan()     → list[CLISnapshot]

2. Background threads:
   browser_history (every 60s) → list[BrowserVisit]
   shell_history (every 3600s) → dict[tool_name, count]
   token_tracker (every 300s) → dict[tool_name, TokenUsage]
   http_receiver (continuous)  → BrowserExtensionPayload

3. All detector outputs → TelemetryManager.meter instruments
   → PeriodicExportingMetricReader (every 15s)
   → OTLPMetricExporter (gRPC to vps.quentinveys.be:4317)
   → OTel Collector (batch + resource processor)
   → Prometheus exporter (:8889)
   → Prometheus scrapes → Grafana queries
```

## OTel Metric Naming Convention

All metrics use the `ai.` namespace. The OTel Collector's Prometheus exporter converts dots to underscores. Unit suffixes are appended automatically by the OTel SDK (e.g., `_seconds_total`, `_percent_bucket`). Cost metrics use `unit="1"` to avoid double suffixes (the metric name already contains `_usd`).

> **Note:** Prometheus names below are verified against actual scraped output from the collector (no `ai_cost_observer_` prefix — the scope name is exported as the `otel_scope_name` label instead).

| OTel Metric Name | Type | Unit | Prometheus Name (verified) | Labels |
|-------------------|------|------|---------------------------|--------|
| `ai.app.running` | UpDownCounter | 1 | `ai_app_running` | `app_name`, `app_category` |
| `ai.app.active.duration` | Counter | s | `ai_app_active_duration_seconds_total` | `app_name`, `app_category` |
| `ai.app.cpu.usage` | Histogram | % | `ai_app_cpu_usage_percent_bucket` | `app_name`, `app_category` |
| `ai.app.memory.usage` | Histogram | MB | `ai_app_memory_usage_MB_bucket` | `app_name`, `app_category` |
| `ai.app.estimated.cost` | Counter | USD | `ai_app_estimated_cost_USD_total` | `app_name`, `app_category` |
| `ai.browser.domain.active.duration` | Counter | s | `ai_browser_domain_active_duration_seconds_total` | `ai_domain`, `ai_category`, `browser_name`, `usage_source` |
| `ai.browser.domain.visit.count` | Counter | 1 | `ai_browser_domain_visit_count_total` | `ai_domain`, `ai_category`, `browser_name`, `usage_source` |
| `ai.browser.domain.estimated.cost` | Counter | USD | `ai_browser_domain_estimated_cost_USD_total` | `ai_domain`, `ai_category` |
| `ai.cli.running` | UpDownCounter | 1 | `ai_cli_running` | `cli_name`, `cli_category` |
| `ai.cli.active.duration` | Counter | s | `ai_cli_active_duration_seconds_total` | `cli_name`, `cli_category` |
| `ai.cli.estimated.cost` | Counter | USD | `ai_cli_estimated_cost_USD_total` | `cli_name`, `cli_category` |
| `ai.cli.command.count` | Counter | 1 | `ai_cli_command_count_total` | `cli_name` |
| `ai.tokens.input.total` | Counter | 1 | `ai_tokens_input_total` | `cli_name` |
| `ai.tokens.output.total` | Counter | 1 | `ai_tokens_output_total` | `cli_name` |
| `ai.tokens.cost_usd_total` | Counter | 1 | `ai_tokens_cost_usd_total` | `cli_name` |
| `ai.prompt.count.total` | Counter | 1 | `ai_prompt_count_total` | `cli_name` |

**Resource attributes** promoted to Prometheus labels (via `resource_to_telemetry_conversion: enabled` on collector):

**Resource attributes** (attached to all metrics via OTel Resource):
- `service.name`: `ai-cost-observer`
- `service.version`: `1.0.0`
- `deployment.environment`: `personal`
- `host.name`: `<hostname>` (e.g., `macbook-home`, `windows-work`)
- `os.type`: `darwin` or `windows`

## Cross-Platform Strategy

| Concern | macOS | Windows |
|---------|-------|---------|
| Active window | `NSWorkspace.sharedWorkspace().activeApplication()` via pyobjc; fallback: `osascript` | `win32gui.GetForegroundWindow()` via pywin32 |
| Process names | e.g., `ChatGPT`, `Claude`, `Cursor` | e.g., `ChatGPT.exe`, `Claude.exe`, `Cursor.exe` |
| Browser history paths | `~/Library/Application Support/Google/Chrome/Default/History` | `%LOCALAPPDATA%\Google\Chrome\User Data\Default\History` |
| Shell history | `~/.zsh_history`, `~/.bash_history` | `%APPDATA%\Microsoft\Windows\PowerShell\PSReadLine\ConsoleHost_history.txt` |
| State directory | `~/.local/state/ai-cost-observer/` | `%LOCALAPPDATA%\ai-cost-observer\` |
| Daemon | launchd (plist in `~/Library/LaunchAgents/`) | Task Scheduler (`schtasks` / `Register-ScheduledTask`) |
| WSL detection | N/A (no-op) | `wsl.exe` process check → `wsl -e ps aux` → UNC path `\\wsl$\` for history |
| Platform deps | `pyobjc-framework-Cocoa` (optional extra) | `pywin32` (optional extra) |

## Security Model

- **Agent → VPS**: OTLP gRPC over insecure channel (port 4317 exposed directly, no TLS termination). Bearer token in `Authorization` header provides authentication. Token stored in user config (`~/.config/ai-cost-observer/config.yaml`), never in git. **Note:** For a personal single-user setup, bearer token over insecure gRPC is pragmatic. For production or multi-tenant use, TLS should be configured on the collector.
- **OTel Collector**: `bearertokenauth` extension validates incoming tokens. Rejects unauthenticated requests.
- **Grafana**: Behind Dokploy's Traefik with its own admin auth. Not publicly writable.
- **Prometheus**: Internal only (not exposed to internet). Only accessible from Collector and Grafana within the Docker network.
- **Chrome extension → Agent**: Localhost HTTP only (127.0.0.1:8080). No external exposure. No CORS issues (service worker exempt).

## Configuration Hierarchy

1. **Built-in defaults** (`src/ai_cost_observer/data/ai_config.yaml`) — ships with package
2. **User overrides** (`~/.config/ai-cost-observer/config.yaml`) — optional, partial overrides merged on top
3. **Environment variables** — `OTEL_ENDPOINT`, `OTEL_BEARER_TOKEN` override config file values

## Threading Model

```
Main thread:     main loop (desktop scan + CLI scan, every 15s)
Thread 1:        Flask HTTP receiver (daemon, continuous)
Thread 2:        Browser history scanner (daemon, every 60s)
Thread 3:        Shell history parser (daemon, every 3600s)
Thread 4:        Token tracker (daemon, every 300s)
OTel internal:   PeriodicExportingMetricReader (every 15s, managed by SDK)
```

All threads are daemon threads — they die with the main process. Signal handlers (SIGTERM, SIGINT) on the main thread trigger graceful shutdown: `telemetry.shutdown()` flushes pending metrics, then `sys.exit(0)`.

## Error Handling Philosophy

- **Never crash the main loop.** Each detector scan wrapped in try/except. Log and continue.
- **psutil errors are expected.** Catch `NoSuchProcess`, `AccessDenied`, `ZombieProcess` at every process access.
- **Browser history access may fail.** DB locked, file missing, permissions denied. Log at WARNING, return empty.
- **OTel export failures are transient.** OTLP exporter has built-in retry. If VPS is down, metrics are dropped silently. Agent continues scanning.
- **HTTP receiver binding failure.** If port 8080 is in use, log ERROR and continue without receiver. Browser history fallback still works.
