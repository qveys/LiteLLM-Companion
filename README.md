# AI Cost Observer

A cross-platform (macOS/Windows) Python agent that tracks personal AI tool spending across desktop apps, browsers, and CLI tools. Metrics are shipped via OpenTelemetry to a centralized Prometheus + Grafana stack, providing unified cost visibility across all your devices.

## What it tracks

| Source | What | How |
|--------|------|-----|
| Desktop apps | 13 apps: ChatGPT, Claude, Cursor, Copilot, Windsurf, Perplexity, LM Studio, etc. | psutil process scan + OS active window API |
| Browser history | 31 AI domains across 8 browsers (Chrome, Edge, Brave, Arc, Vivaldi, Opera, Firefox, Safari) | SQLite history parsing (copy-to-temp strategy) |
| Chrome extension | Real-time AI domain tracking + API call interception (10 providers) | Manifest V3 service worker, sends to local agent |
| CLI tools | 10 tools: ollama, claude-code, aider, gemini-cli, codex-cli, vibe, etc. | psutil scan + shell history parsing |
| Token tracking | API token costs from Claude Code, Codex, Gemini CLI | JSONL log parsing + model pricing (20+ models) |

## Architecture

```
Workstation (Python agent)              VPS (Dokploy)
┌───────────────────────┐              ┌─────────────────────────┐
│ Desktop Detector      │   OTLP gRPC  │ OTel Collector :4317    │
│ Browser History (8 DB)│──────────────│  → Prometheus :9090     │
│ CLI Detector          │  + Bearer    │  → Grafana :3000        │
│ Shell History Parser  │    token     │    (4 dashboards)       │
│ Token Tracker         │              └─────────────────────────┘
│ HTTP Receiver :8080   │
│  ← Chrome Extension   │
└───────────────────────┘
```

The Chrome extension sends data to the **local agent** (localhost:8080), which relays everything to the VPS via OTLP gRPC. The extension never talks directly to the VPS.

## Prerequisites

- **Python 3.12** (pinned in `.python-version`; minimum supported: 3.10, see `requires-python` in `pyproject.toml`)
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- Chromium-based browser or Firefox/Safari (for extension and history)
- VPS with Docker (for backend stack)

## Quick Start

### 1. Install the agent

```bash
git clone https://github.com/your-repo/opentelemetry.git
cd opentelemetry

# Install with uv (recommended)
uv sync

# macOS: install optional native window tracking
uv sync --extra macos

# Windows: install optional native window tracking
uv sync --extra windows
```

### 2. Configure

Create `~/.config/ai-cost-observer/config.yaml`:

```yaml
otel_endpoint: "your-vps.example.com:4317"
otel_bearer_token: "your-secret-token"
otel_insecure: true  # set false if using TLS
```

Or use environment variables:

```bash
export OTEL_ENDPOINT="your-vps.example.com:4317"
export OTEL_BEARER_TOKEN="your-secret-token"
export OTEL_INSECURE=true
```

### 3. Run

```bash
uv run python -m ai_cost_observer           # normal mode = only important events are logged (app detected/stopped, extension connected)
uv run python -m ai_cost_observer --debug   # verbose logging = detailed per-scan output
```

Verify the agent is running by opening `http://127.0.0.1:8080` in your browser.

### 4. Install Chrome extension

1. Open `chrome://extensions/`
2. Enable "Developer mode"
3. Click "Load unpacked"
4. Select the `chrome-extension/` directory
5. The extension icon appears in the toolbar

**Configure the extension:** Click the extension icon, then the gear icon in the footer to open Settings. The default agent URL is `http://127.0.0.1:8080`. Change it if you run the agent on a different port.

**What the extension does:**
- Tracks time spent on 31 AI domains (chatgpt.com, claude.ai, deepseek.com, etc.)
- Intercepts API calls to 10 AI providers (Anthropic, OpenAI, Google, DeepSeek, Groq, Cohere, Together.ai, HuggingFace, Mistral, Perplexity) for token usage tracking
- Sends delta metrics to the local agent every 60s
- Shows today's usage summary in the popup (time, cost, domains)

## Backend Setup (VPS)

The backend stack (OTel Collector + Prometheus + Grafana) runs on a VPS via Docker Compose.

```bash
cd infra

# Copy and edit environment file
cp .env.example .env
# Edit .env: set OTEL_BEARER_TOKEN and GF_SECURITY_ADMIN_PASSWORD

docker compose up -d
```

Grafana is accessible at `http://your-vps:3000` (or via Traefik reverse proxy).

Four dashboards are auto-provisioned:
- **AI Cost Overview** -- total costs, running apps, duration charts, CPU/memory usage
- **Browser AI Usage** -- domain-level tracking with source filter (extension vs history)
- **Unified Cost** -- combined Desktop + Browser + CLI cost breakdown
- **Token Usage** -- per-model token consumption and cost (treemap + timeseries)

## Auto-Start as Daemon

### macOS (launchd)

```bash
chmod +x service/install-macos.sh
./service/install-macos.sh
```

The agent starts at login and auto-restarts on failure. Logs at `/tmp/ai-cost-observer.stderr.log`.

```bash
# Check status
launchctl list | grep ai-cost

# Stop
launchctl unload ~/Library/LaunchAgents/com.ai-cost-observer.plist

# View logs
tail -f /tmp/ai-cost-observer.stderr.log
```

### Windows (Task Scheduler)

Run PowerShell as Administrator:

```powershell
.\service\install-windows.ps1
```

The agent runs at logon (windowless) and restarts up to 3 times on failure.

```powershell
# Start immediately
Start-ScheduledTask -TaskName "AI Cost Observer"

# Check status
Get-ScheduledTask -TaskName "AI Cost Observer"

# Remove
.\service\uninstall-windows.ps1
```

## Configuration

### Agent config (`~/.config/ai-cost-observer/config.yaml`)

```yaml
# Connection
otel_endpoint: "vps.example.com:4317"
otel_bearer_token: "your-token"
otel_insecure: true

# Scan intervals
scan_interval_seconds: 15        # Desktop + CLI scan
browser_history_interval_seconds: 60    # Browser history parse
shell_history_interval_seconds: 3600    # Shell history parse

# HTTP receiver
http_receiver_port: 8080

# Add custom AI tools
extra_ai_apps:
  - name: "My Custom AI"
    category: "custom"
    cost_per_hour: 5.0
    process_names:
      macos: ["MyAI"]
      windows: ["MyAI.exe"]

extra_ai_domains:
  - domain: "my-ai-tool.com"
    category: "custom"
    cost_per_hour: 10.0

extra_ai_cli_tools:
  - name: "my-cli"
    category: "custom"
    cost_per_hour: 0.0
    process_names:
      macos: ["my-cli"]
      windows: ["my-cli.exe"]
    command_patterns: ["my-cli"]
```

### Environment variable overrides

| Variable | Description |
|----------|-------------|
| `OTEL_ENDPOINT` | OTel Collector endpoint (host:port) |
| `OTEL_BEARER_TOKEN` | Bearer token for authentication |
| `OTEL_INSECURE` | `true` to disable TLS on gRPC |

## Troubleshooting

### Agent won't connect to VPS

```bash
# Test gRPC port reachability
nc -zv your-vps.example.com 4317

# Check token works (HTTP endpoint)
curl -X POST https://your-vps.example.com:4318/v1/metrics \
  -H "Authorization: Bearer your-token" \
  -H "Content-Type: application/json" \
  -d '{}'
```

### Port 8080 already in use

If the agent crashes with "Address already in use", another process is using port 8080:

```bash
# Find what's using the port
lsof -i :8080

# Option 1: Kill the other process
kill <PID>

# Option 2: Change the agent port in config
# ~/.config/ai-cost-observer/config.yaml
http_receiver_port: 8081
```

If you change the port, update the Chrome extension settings to match (click gear icon in popup).

### No desktop apps detected

- Verify process names match: `ps aux | grep -i chatgpt`
- Check `ai_config.yaml` has correct `process_names` for your OS
- macOS: install pyobjc for native window tracking: `uv sync --extra macos`

### Safari history "Permission denied"

Safari requires Full Disk Access for history reading. Go to System Settings > Privacy & Security > Full Disk Access and add Terminal/iTerm.

### Chrome extension not connecting

- Verify agent is running: open `http://127.0.0.1:8080` in your browser (should return JSON)
- If the popup shows "Connection refused — is the agent running?", start the agent first
- Check the extension settings (gear icon) point to the correct agent URL and port
- Check extension permissions at `chrome://extensions/`
- Look for errors in the extension service worker console (click "Inspect views: service worker" on the extensions page)

### Metrics not appearing in Grafana

- Check Prometheus targets: Grafana > Explore > `up{job="otel-collector"}`
- Verify metric names: `curl http://your-vps:9090/api/v1/label/__name__/values`
- Ensure `host_name` label filter in dashboards matches your hostname

## Development

```bash
# Install dev dependencies (pytest, ruff, pytest-mock)
uv sync --extra dev

# Run all tests (281 tests)
uv run python -m pytest

# Run single test file
uv run python -m pytest tests/test_desktop.py -v

# Lint
uv run ruff check src/

# Run agent
uv run python -m ai_cost_observer

# Run agent in debug mode (verbose logging: every scan, every request, every metric)
uv run python -m ai_cost_observer --debug
```

Note: The agent automatically kills any process occupying its HTTP port (default 8080) on startup.

## License

MIT
