# AI Cost Observer — Contexte Projet

> **Ce document est la reference obligatoire pour tout agent travaillant sur ce projet.**
> Lis-le en entier avant de commencer toute mission.

---

## 1. Qu'est-ce que AI Cost Observer ?

Un agent Python cross-platform (macOS/Windows) qui traque les depenses personnelles en outils IA. Il detecte l'utilisation d'apps desktop, sites web, et outils CLI, puis envoie les metriques via OpenTelemetry (OTLP gRPC + TLS + bearer token) vers un VPS centralise (OTel Collector -> Prometheus -> Grafana).

## 2. Architecture

```
Workstation (Python agent)              VPS (vps.quentinveys.be)
+---------------------------+          +---------------------------+
| Detectors:                |   OTLP   | OTel Collector :4317      |
|   desktop (psutil+window) |---gRPC-->|   -> Prometheus :9090     |
|   browser_history (8 DBs) |  +TLS    |   -> Grafana :3000        |
|   cli (psutil+dedup)      |  +token  |      (4 dashboards)       |
|   shell_history (hourly)  |          +---------------------------+
|   token_tracker (JSONL)   |
|   wsl (Windows only)      |
| HTTP Receiver :8080       |<--- Chrome Extension (localhost)
| TelemetryManager (OTel)   |
+---------------------------+
```

## 3. Structure des fichiers

```
src/ai_cost_observer/           # Package Python principal
  __init__.py                   # Version: 1.0.0
  config.py                     # Configuration (YAML hierarchy)
  telemetry.py                  # OTel SDK: 16 instruments, Resource, MeterProvider
  main.py                       # Orchestrateur: main loop, threading, lifecycle
  data/ai_config.yaml           # Definitions outils IA (13 apps, 31 domaines, 10 CLI)
  detectors/
    desktop.py                  # Detection apps desktop (5 metriques)
    cli.py                      # Detection CLI (3 metriques)
    browser_history.py          # Historique navigateurs (3 metriques)
    shell_history.py            # Historique shell (1 metrique)
    token_tracker.py            # Tokens Claude/Codex/Gemini (4 metriques)
    wsl.py                      # WSL Windows only (1 metrique)
    active_window.py            # Dispatch fenetre active macOS/Windows
  server/
    http_receiver.py            # Flask :8080 pour Chrome Extension
  storage/
    prompt_db.py                # SQLite stockage prompts (chiffre)
  platform/
    macos.py                    # NSWorkspace + osascript
    windows.py                  # win32gui

infra/                          # Docker Compose VPS
  docker-compose.yml            # OTel Collector + Prometheus + Grafana
  otel-collector-config.yaml    # Receivers, processors, exporters
  prometheus.yml                # Scrape config, 30d retention
  grafana/provisioning/         # Datasources + dashboards (4 JSON)

chrome-extension/               # Manifest V3
  background.js                 # Tracking domaines + interception API
  popup.html/js                 # Affichage usage du jour
  options.html/js               # Config (URL agent, port)

service/                        # Installation daemon
  com.ai-cost-observer.plist    # macOS launchd
  install-macos.sh / uninstall
  install-windows.ps1 / uninstall

tests/                          # 281 tests (28 fichiers)
docs/                           # product-brief, architecture, stories
```

## 4. Les 16 metriques OTel

| # | Nom OTel | Type | Unite | Prometheus | Detecteur |
|---|----------|------|-------|------------|-----------|
| 1 | ai.app.running | UpDownCounter | 1 | ai_app_running | desktop |
| 2 | ai.app.active.duration | Counter | s | ai_app_active_duration_seconds_total | desktop |
| 3 | ai.app.cpu.usage | Histogram | % | ai_app_cpu_usage_percent_* | desktop |
| 4 | ai.app.memory.usage | Histogram | MB | ai_app_memory_usage_MB_* | desktop |
| 5 | ai.app.estimated.cost | Counter | USD | ai_app_estimated_cost_USD_total | desktop |
| 6 | ai.browser.domain.active.duration | Counter | s | ai_browser_domain_active_duration_seconds_total | browser_history, http_receiver |
| 7 | ai.browser.domain.visit.count | Counter | 1 | ai_browser_domain_visit_count_total | browser_history, http_receiver |
| 8 | ai.browser.domain.estimated.cost | Counter | USD | ai_browser_domain_estimated_cost_USD_total | browser_history, http_receiver |
| 9 | ai.cli.running | UpDownCounter | 1 | ai_cli_running | cli, wsl |
| 10 | ai.cli.active.duration | Counter | s | ai_cli_active_duration_seconds_total | cli |
| 11 | ai.cli.estimated.cost | Counter | USD | ai_cli_estimated_cost_USD_total | cli |
| 12 | ai.cli.command.count | Counter | 1 | ai_cli_command_count_total | shell_history |
| 13 | ai.tokens.input_total | Counter | 1 | ai_tokens_input_total | token_tracker, http_receiver |
| 14 | ai.tokens.output_total | Counter | 1 | ai_tokens_output_total | token_tracker, http_receiver |
| 15 | ai.tokens.cost_usd_total | Counter | 1 | ai_tokens_cost_usd_total | token_tracker, http_receiver |
| 16 | ai.prompt.count_total | Counter | 1 | ai_prompt_count_total | token_tracker, http_receiver |

**Resource attributes** (sur toutes les metriques):
`service.name=ai-cost-observer`, `service.version=1.0.0`, `host.name`, `os.type`, `deployment.environment=personal`

## 5. Threading model

- **Main thread**: boucle 15s (desktop + CLI scan)
- **Daemon thread 1**: Flask HTTP receiver (continu)
- **Daemon thread 2**: Browser history (60s)
- **Daemon thread 3**: Shell history (3600s)
- **Daemon thread 4**: Token tracker (300s)
- **OTel**: PeriodicExportingMetricReader (15s)

## 6. Configuration

Hierarchie: `src/ai_cost_observer/data/ai_config.yaml` (built-in)
-> `~/.config/ai-cost-observer/config.yaml` (user)
-> variables d'environnement (`OTEL_ENDPOINT`, `OTEL_BEARER_TOKEN`)

## 7. Conventions

- **Commits**: emoji + conventional commits (`feat:`, `fix:`, `chore:`, etc.)
- **Tests**: `uv run python -m pytest` (281 tests, tous passent)
- **Lint**: `uv run ruff check src/` + `uv run ruff format --check src/`
- **Metriques**: namespace `ai.*`, dots -> underscores en Prometheus
- **Erreurs**: jamais crasher la boucle principale, try/except partout
- **SQL**: requetes parametrees obligatoires (pas de f-strings)

## 8. Bugs connus (audit du pipeline)

Un audit complet a identifie 21 bugs. Les 3 critiques:

1. **Codex double-counting** (`token_tracker.py:245`): `_scan_codex()` re-traite TOUTES les sessions a chaque cycle de 5 min. Pas de tracking de rowid.
2. **Claude Code offsets non persistes** (`token_tracker.py:85`): `_file_offsets` en memoire seulement, re-comptage total au restart.
3. **CPU/Memory Histogram** (`telemetry.py:69-70`): Definis comme Histogram, requetes comme Gauge dans Grafana -> panels vides.

7 bugs HIGH, 6 MEDIUM, 4 LOW documentes dans les issues GitHub.

## 9. Commandes essentielles

```bash
# Installation
uv sync --extra dev --extra macos

# Tests
uv run python -m pytest                              # tous
uv run python -m pytest tests/test_desktop.py         # un fichier
uv run python -m pytest tests/test_desktop.py::test_fn # une fonction

# Lint
uv run ruff check src/
uv run ruff format --check src/

# Run
python -m ai_cost_observer

# Infrastructure
cd infra && docker compose up -d
```

## 10. Grafana Dashboards (4)

1. **AI Cost Overview** — vue globale: couts, apps actives, durations
2. **Browser AI Usage** — detail par domaine, navigateur, source
3. **Token Usage** — tokens in/out, couts reels, par modele/outil
4. **Unified Cost** — consolidation couts desktop + browser + CLI + tokens
