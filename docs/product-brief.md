# Product Brief: AI Cost Observer

## Problem Statement

As AI tools proliferate across desktop apps (ChatGPT, Claude, Cursor), web interfaces (claude.ai, chatgpt.com, perplexity.ai), and CLI tools (claude-code, ollama, gemini), personal users have **zero visibility** into their aggregate AI spending. Subscription costs, pay-per-use charges, and compute time are scattered across multiple billing systems with no unified view.

There is no tool that answers: *"How much am I actually spending on AI tools today/this week/this month, and where is that money going?"*

## Target User

- **Primary:** Individual developer/power user running multiple AI tools daily on macOS or Windows
- **Use case:** Personal cost awareness and optimization, not enterprise billing
- **Technical level:** Comfortable with Docker, pip, browser extensions

## MVP Scope

Lightweight agents running on each workstation (macOS, Windows) monitor AI tool usage across 3 sources and ship metrics to a centralized observability stack on a Dokploy VPS, where Grafana dashboards visualize estimated costs across all devices.

### In Scope (MVP)

| Source | What we track | How |
|--------|--------------|-----|
| Desktop apps | Running state, foreground time, CPU/memory | psutil process scan + OS active window API |
| Web browsers | AI domain visits, session duration | SQLite history parsing + Chrome extension |
| CLI tools | Running processes, command counts | psutil scan + shell history parsing |

- **Centralized backend on Dokploy VPS** (`vps.quentinveys.be`): OTel Collector → Prometheus → Grafana
- OTLP gRPC with bearer token authentication (insecure channel for personal use; TLS optional)
- Multi-device support: `host.name` label distinguishes macOS (home) from Windows (work)
- Pre-provisioned Grafana dashboards (3 dashboards, auto-loaded) with `$host` filter variable
- Configurable cost rates per tool (YAML config)
- Cross-platform agents: macOS primary, Windows with WSL support
- Chrome extension for real-time browser tracking
- Auto-start daemon (launchd on macOS, Task Scheduler on Windows)

### Out of Scope (MVP)

- Actual API billing data (requires vendor API keys)
- Content capture or network inspection
- Multi-user / team / enterprise features
- Mobile device tracking
- Token-level usage tracking (would require API interception)
- Local/offline fallback stack (if offline, no AI usage to track)

## Success Metrics

| Metric | Target |
|--------|--------|
| CPU usage | < 5% average |
| Memory usage | < 200 MB RSS |
| Scan latency | < 2s per cycle |
| Time to first dashboard | < 15 min from clone to Grafana |
| Detection coverage | All 3 sources (desktop, browser, CLI) visible in Unified Cost dashboard |
| Cross-platform | Works on macOS and Windows (with WSL) |

## Constraints

- **Privacy-first:** No content capture, no TLS inspection, no process injection. Track usage metadata only (app names, domains, durations).
- **Personal VPS only:** Metrics shipped to your own Dokploy VPS over TLS. No third-party data sharing. Bearer token auth prevents unauthorized ingestion.
- **Non-invasive:** No kernel extensions, no root access required (macOS may need Accessibility permission for active window).
- **Lightweight:** Must not impact daily work. Background agent should be invisible.

## AI Tools Tracked (Initial Set)

### Desktop Apps
ChatGPT Desktop, Claude Desktop, Cursor, GitHub Copilot, Windsurf, Tabnine, JetBrains AI, Pieces, Raycast AI, Warp AI, Notion AI, Obsidian (Copilot plugin)

### Browser Domains
chat.openai.com, chatgpt.com, claude.ai, gemini.google.com, perplexity.ai, poe.com, huggingface.co, you.com, phind.com, copilot.microsoft.com, bolt.new, lovable.dev, v0.dev, replit.com, colab.research.google.com, aistudio.google.com, labs.google

### CLI Tools
claude-code / cc, ollama, gemini-cli, github-copilot-cli, aider, open-interpreter, llm (Simon Willison), sgpt, fabric
