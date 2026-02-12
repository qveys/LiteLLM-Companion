# Stories: AI Cost Observer

> Status tracking for all implementation stories.
> Update status after completing each story: `Pending` → `In Progress` → `Done`

## Overview

| # | Story | Status | Dependencies |
|---|-------|--------|-------------|
| 0 | Design Artifacts | **Done** | — |
| 1 | Infrastructure (Dokploy VPS) | **Done** | — |
| 2 | Python Skeleton + OTel Wiring | **Done** | Story 1 |
| 3 | Desktop App Detection + Active Window | **Done** | Story 2 |
| 4 | Browser History Parsing | **Done** | Story 2 |
| 5 | CLI Detection + Shell History + WSL | **Done** | Story 2 |
| 6 | HTTP Receiver + Chrome Extension | **Done** | Story 2 |
| 7 | Grafana Dashboards | **Done** | Stories 3-6 |
| 7b | Token Usage Dashboard | **Done** | Story 9 |
| 8 | Daemon Installation + README | **Done** | Story 7 |
| 9 | Token Tracking + Chrome Extension + Dashboards | **Done** | Story 8 |
| 10 | Optimisation globale (coverage, tests, dashboards) | **Done** | Story 9 |

---

## Story 0: Design Artifacts

**Status:** Done

**Scope:** Create 3 BMAD-inspired design docs.

**Files:**
- `docs/product-brief.md`
- `docs/architecture.md`
- `docs/stories.md` (this file)

**Acceptance criteria:**
- [x] `docs/product-brief.md` exists with problem statement, MVP features, success metrics
- [x] `docs/architecture.md` exists with data flow diagram, module table, metric naming table
- [x] `docs/stories.md` exists with all stories numbered, with status tracking

---

## Story 1: Infrastructure (Dokploy VPS)

**Status:** Done

**Scope:** Deploy OTel Collector + Prometheus + Grafana on Dokploy VPS (`vps.quentinveys.be`). Secure OTLP ingestion with TLS + bearer token auth.

**Files:**
- `infra/docker-compose.yml`
- `infra/otel-collector-config.yaml`
- `infra/prometheus.yml`
- `infra/grafana/provisioning/datasources/prometheus.yaml`
- `infra/grafana/provisioning/dashboards/dashboards.yaml`
- `infra/.env.example`

**Acceptance criteria:**
- [x] All 3 services running on Dokploy VPS
- [x] OTel Collector reachable from local machine on port 4317
- [x] Unauthenticated OTLP requests rejected (HTTP 401)
- [x] Authenticated OTLP requests accepted (bearer token)
- [x] Prometheus targets page shows collector UP
- [x] Grafana accessible via browser with Prometheus datasource
- [x] Data survives `docker compose restart` (persistent volumes configured)

**Dependencies:** None

---

## Story 2: Python Skeleton + OTel Wiring

**Status:** Done

**Scope:** Installable Python package with OTel metric export to remote VPS.

**Files:**
- `pyproject.toml`, `.gitignore`, `.python-version`
- `src/ai_cost_observer/__init__.py`, `__main__.py`
- `src/ai_cost_observer/config.py`
- `src/ai_cost_observer/telemetry.py`
- `src/ai_cost_observer/main.py`
- `src/ai_cost_observer/data/ai_config.yaml`
- Empty `__init__.py` for detectors/, exporters/, server/, platform/

**Acceptance criteria:**
- [x] `pip install -e .` succeeds
- [x] `python -m ai_cost_observer` starts, logs "Agent started"
- [x] Connects to VPS OTel Collector with bearer token (gRPC, insecure mode)
- [x] Test metric appears in Prometheus on VPS within 30s
- [x] Metrics include `host.name` resource attribute (`MacBook-Pro-de-Quentin.local`)
- [x] `Ctrl+C` triggers graceful shutdown
- [x] `ai_config.yaml` has 13 apps, 31 domains, 10 CLI tools

**Dependencies:** Story 1

---

## Story 3: Desktop App Detection + Active Window

**Status:** Done

**Scope:** Detect AI desktop apps, track foreground time.

**Files:**
- `src/ai_cost_observer/detectors/active_window.py`
- `src/ai_cost_observer/platform/macos.py`
- `src/ai_cost_observer/platform/windows.py`
- `src/ai_cost_observer/detectors/desktop.py`

**Acceptance criteria:**
- [x] AI desktop app detected within 15s of launch
- [x] `ai_app_running` = 1 in Prometheus
- [x] Foreground app increments `ai_app_active_duration_total`
- [x] Background app does NOT increment duration
- [x] Closed app returns `ai_app_running` to 0
- [x] CPU/memory histograms show non-zero values
- [x] Cost increments proportional to active time
- [x] psutil errors caught, never crash agent
- [x] osascript fallback works on macOS without pyobjc

**Dependencies:** Story 2

---

## Story 4: Browser History Parsing

**Status:** Done

**Scope:** Parse Chrome/Firefox/Safari SQLite history for AI domains.

**Files:**
- `src/ai_cost_observer/detectors/browser_history.py`

**Acceptance criteria:**
- [x] Chrome history parsed (Chrome epoch conversion correct)
- [x] Firefox history parsed (microsecond timestamps, JOIN)
- [x] Safari skipped gracefully if Full Disk Access denied
- [x] Copy-to-temp works while browser is running
- [x] Parameterized SQL queries (no f-strings)
- [x] Metrics labeled `usage.source: "history_parser"`
- [x] Domain metrics visible in Prometheus
- [x] Session gaps > 30min treated as separate sessions
- [x] OS-aware paths (macOS + Windows)

**Dependencies:** Story 2

---

## Story 5: CLI Detection + Shell History + WSL

**Status:** Done

**Scope:** CLI AI process detection, shell history parsing, WSL support.

**Files:**
- `src/ai_cost_observer/detectors/cli.py`
- `src/ai_cost_observer/detectors/shell_history.py`
- `src/ai_cost_observer/detectors/wsl.py`

**Acceptance criteria:**
- [x] ollama detected within 15s, `ai_cli_running` = 1
- [x] Stopped process returns to 0 within 30s
- [x] Duration and cost counters increment correctly
- [x] zsh history parsed (`: timestamp:flags;command` format)
- [x] bash history parsed (plain format)
- [x] PowerShell history parsed (Windows)
- [x] Incremental parsing (byte offset persisted)
- [x] `ai_cli_command_count_total` correct per tool
- [x] Encoding errors handled (`errors="replace"`)
- [x] WSL detection works on Windows (no-ops on macOS)
- [x] WSL metrics labeled with `runtime.environment: "wsl"`

**Dependencies:** Story 2

---

## Story 6: HTTP Receiver + Chrome Extension

**Status:** Done

**Scope:** Real-time browser tracking via Chrome extension.

**Files:**
- `src/ai_cost_observer/server/http_receiver.py`
- `chrome-extension/manifest.json`
- `chrome-extension/background.js`
- `chrome-extension/popup.html`, `popup.js`
- `chrome-extension/icons/`

**Acceptance criteria:**
- [x] Flask on :8080, daemon thread, no blocking
- [x] `GET /health` returns healthy
- [x] `POST /metrics/browser` accepts JSON, labels `usage.source: "extension"`
- [x] Extension installs unpacked without errors
- [x] AI domain detection + timing works
- [x] Tab switching saves/starts sessions
- [x] Popup shows today's usage (time + cost)
- [x] Extension sends deltas every 60s
- [x] Silent retry if agent is down
- [x] `use_reloader=False` on Flask

**Dependencies:** Story 2

---

## Story 7: Grafana Dashboards

**Status:** Done

**Scope:** 4 pre-provisioned dashboards with `$host` filter.

**Files:**
- `infra/grafana/dashboards/ai-cost-overview.json`
- `infra/grafana/dashboards/browser-ai-usage.json`
- `infra/grafana/dashboards/unified-cost.json`
- `infra/grafana/dashboards/token-usage.json`

**Acceptance criteria:**
- [x] All 3 dashboards auto-appear after deployment (deployed via Grafana API)
- [x] Overview: cost today/month (stat), duration by app (timeseries), browser breakdown (piechart), running apps table — 9 panels
- [x] Browser: $browser, $ai_category, $source filters with 5 panels
- [x] Unified: pie chart Desktop vs Browser vs CLI cost breakdown
- [x] `$host` variable filters by device (label_values query)
- [x] PromQL uses correct Prometheus metric names (verified against live metrics)
- [ ] Non-zero data after 30+ min of agent running (pending extended test)

**Dependencies:** Stories 3-6

---

## Story 8: Daemon Installation + README

**Status:** Done

**Scope:** Auto-start daemon, documentation.

**Files:**
- `service/com.ai-cost-observer.plist`
- `service/install-macos.sh`
- `service/install-windows.ps1`, `uninstall-windows.ps1`
- `README.md`

**Acceptance criteria:**
- [x] macOS: launchd plist with RunAtLoad, KeepAlive on failure, install script
- [x] Windows: Task Scheduler with logon trigger, 3 retries, windowless, install/uninstall scripts
- [x] README: prerequisites, quick start (macOS + Windows), backend setup, config guide, troubleshooting, development section

**Dependencies:** Story 7

---

## Story 9: Token Tracking + Chrome Extension + Dashboards

**Status:** Done

**Scope:** Add token-level cost tracking from CLI tools (Claude Code, Codex, Gemini), fix CLI detection, enhance Chrome extension, add Token Usage dashboard.

**Files:**
- `src/ai_cost_observer/detectors/token_tracker.py` — NEW: JSONL log parser with MODEL_PRICING
- `src/ai_cost_observer/telemetry.py` — +4 token metrics (input, output, cost, prompt count)
- `src/ai_cost_observer/detectors/cli.py` — Fix detection for interpreted scripts (cmdline_patterns)
- `chrome-extension/background.js`, `popup.html`, `popup.js` — Enhanced extension UI
- `infra/grafana/dashboards/token-usage.json` — NEW: Token Usage dashboard

**Acceptance criteria:**
- [x] Claude Code JSONL logs parsed for token usage
- [x] MODEL_PRICING maps model names to $/1M token costs
- [x] 4 new OTel metrics: tokens input/output, cost USD, prompt count
- [x] CLI detection works for interpreted scripts via cmdline_patterns
- [x] Chrome extension shows per-domain time and cost in popup
- [x] Token Usage dashboard with 6 panels (treemap, timeseries, stat, table)
- [x] All existing tests pass + new tests added

**Dependencies:** Story 8

---

## Story 10: Optimisation globale — Couverture maximale, Tests robustes, Dashboards optimisés

**Status:** Done

**Scope:** Full audit and optimization across 4 axes: coverage, tests, dashboards, detection accuracy. Executed by 4 parallel agent teams.

**Files changed (coverage):**
- `src/ai_cost_observer/data/ai_config.yaml` — +10 AI domains, +3 desktop apps, removed fake apps (Gemini desktop, Codex desktop, DALL-E)
- `src/ai_cost_observer/detectors/browser_history.py` — +5 Chromium browsers (Edge, Brave, Arc, Vivaldi, Opera), fixed Firefox/Safari SQL aliases
- `src/ai_cost_observer/detectors/token_tracker.py` — +11 models in MODEL_PRICING
- `chrome-extension/background.js` — +10 domains synced
- `chrome-extension/popup.js` — +10 domains in COST_RATES

**Files changed (dashboards):**
- `src/ai_cost_observer/telemetry.py` — Fix unit `"USD"` → `"1"` on tokens_cost_usd_total (prevent double suffix)
- `infra/docker-compose.yml` — Removed 3 unused Grafana plugins
- `infra/grafana/dashboards/ai-cost-overview.json` — +3 panels (CPU, Memory, CLI Commands), fixed thresholds
- `infra/grafana/dashboards/token-usage.json` — Fixed metric name, treemap config
- `infra/grafana/dashboards/unified-cost.json` — Fixed metric name, thresholds
- `infra/grafana/dashboards/browser-ai-usage.json` — Fixed allValue on template variables

**Files changed (detection):**
- `src/ai_cost_observer/detectors/cli.py` — Case-sensitive desktop dedup to prevent double-counting
- `src/ai_cost_observer/data/ai_config.yaml` — Tightened codex-cli cmdline_patterns

**Tests added (281 total):**
- `tests/conftest.py` — Shared fixtures (mock_telemetry, mock_config)
- `tests/test_telemetry.py` — 6 TelemetryManager tests
- `tests/detectors/test_browser_history_extended.py` — Firefox, Safari, Edge, Brave, DB locked
- `tests/detectors/test_desktop_extended.py` — Foreground, cmdline, AccessDenied
- `tests/detectors/test_cli_extended.py` — Multiple instances, AccessDenied
- `tests/test_shell_history_extended.py` — Bash, PowerShell, malformed, empty
- `tests/test_wsl_extended.py` — Disabled macOS, multiple distros
- `tests/test_metric_name_audit.py` — 25 tests for OTel→Prometheus→PromQL pipeline
- `tests/test_real_detection.py` — 10 tests for real process detection
- `tests/test_dashboard_completeness.py` — 24 tests for dashboard validation
- `tests/test_detection_dedup.py` — 9 tests for detection dedup fixes

**Acceptance criteria:**
- [x] 31 AI domains, 13 desktop apps, 10 CLI tools, 8 browsers
- [x] All 16 OTel metrics have correct Prometheus names (no double suffixes)
- [x] All 4 dashboards use correct PromQL metric names
- [x] No desktop/CLI double-counting (case-sensitive dedup)
- [x] 281 tests pass, 4 dashboard JSONs valid
- [x] Extension domains synced with ai_config.yaml

**Dependencies:** Story 9

---

## Refinement: Keychain-based Token Storage

**Status:** Pending (post-MVP)

**Scope:** Replace plaintext YAML token storage with OS-native credential management (macOS Keychain, Windows Credential Manager). Raised in Story 1 review as Critical for wider distribution.

**Files:**
- `src/ai_cost_observer/config.py` — add keychain lookup before file-based fallback

**Dependencies:** Story 8
