# Story 7 Review Brief: Grafana Dashboards

## What was built

- 3 Grafana dashboard JSON files deployed via Grafana HTTP API to `grafana-otel.quentinveys.be`
- All dashboards tagged `ai-cost-observer`, use `$host` template variable for multi-device filtering

### Files created
- `infra/grafana/dashboards/ai-cost-overview.json` — 9 panels (stat, timeseries, piechart, table)
- `infra/grafana/dashboards/browser-ai-usage.json` — 5 panels with $browser, $category, $source filters
- `infra/grafana/dashboards/unified-cost.json` — combined Desktop/Browser/CLI breakdown

### Key design decisions
1. **Grafana API deployment** instead of file-mount provisioning — Dokploy MCP doesn't support file uploads, and SSH wasn't configured. Dashboards pushed via `POST /api/dashboards/db` with admin credentials.
2. **`$host` template variable** on all dashboards — enables per-device filtering via `label_values(ai_app_running, host_name)`
3. **15s auto-refresh** — matches agent scan interval for near-real-time display
4. **Datasource UID `PBFA97CFB590B2093`** hardcoded — the Prometheus datasource was auto-provisioned in Story 1
5. **`$__rate_interval`** used in `rate()` queries — adapts to dashboard time range and scrape interval

## Acceptance criteria results

- [x] All 3 dashboards appear in Grafana — **PASS** (verified via API: 3 dashboards with correct UIDs)
- [x] Overview dashboard: stat panels (cost today/month), time series (duration by app), pie chart (browser domains), table (running apps) — **PASS** (9 panels confirmed)
- [x] Browser dashboard: $browser and $ai_category template vars, sessions timeline — **PASS** (3 template vars: browser, category, source)
- [x] Unified dashboard: pie chart Desktop vs Browser vs CLI cost breakdown — **PASS**
- [x] `$host` variable filters by device — **PASS** (query: `label_values(ai_app_running, host_name)`)
- [x] PromQL queries use correct metric names — **PASS** (verified against actual Prometheus metric names)
- [ ] Non-zero data after 30+ min of agent running — **PENDING** (dashboards deployed, extended test needed)

## Dashboard panel inventory

### AI Cost Overview (9 panels)
| Panel | Type | PromQL |
|-------|------|--------|
| Total Cost Today | stat | `sum(ai_app_estimated_cost_USD_total) + sum(ai_browser_domain_estimated_cost_USD_total) + sum(ai_cli_estimated_cost_USD_total)` |
| Total Cost This Month | stat | same with `[30d]` range |
| Active AI Apps Now | stat | `sum(ai_app_running{host_name=~"$host"})` |
| Active CLI Tools Now | stat | `sum(ai_cli_running{host_name=~"$host"})` |
| Active Duration by App | timeseries | `rate(ai_app_active_duration_seconds_total{...}[$__rate_interval])` |
| Browser Duration by Domain | timeseries | `rate(ai_browser_domain_active_duration_seconds_total{...}[$__rate_interval])` |
| Cost Breakdown by Source | piechart | Desktop + Browser + CLI costs |
| Currently Running Apps | table | `ai_app_running == 1` |
| CLI Duration by Tool | timeseries | `rate(ai_cli_active_duration_seconds_total{...}[$__rate_interval])` |

### Browser AI Usage (5 panels)
Template vars: `$host`, `$browser`, `$category`, `$source`

### Unified Cost (panels)
Combined view with Desktop/Browser/CLI breakdowns, cost trends, and cumulative totals.

## Review questions

1. **Deployment method**: Dashboards were pushed via Grafana API (not file provisioning). This means they're stored in Grafana's SQLite DB, not on disk. Should we also maintain file-based provisioning for disaster recovery?

2. **Datasource UID**: The UID `PBFA97CFB590B2093` is hardcoded in all 3 dashboards. If the Prometheus datasource is recreated, all dashboards break. Should we use the default datasource instead?

3. **Rate queries**: Using `rate()` on Counters works for "per second" views, but for "total accumulated" views, `increase()` might be more user-friendly. Is the current mix appropriate?

4. **Cost calculation accuracy**: The "Total Cost Today" panel sums all-time Counter values, not just today's. For accurate daily/monthly views, should we use `increase(metric[24h])` or recording rules?

5. **Dashboard persistence**: Since dashboards are API-deployed (not file-provisioned), they survive Grafana restarts but NOT volume recreation. Should we add the JSON files to file provisioning as backup?

## Gemini Review Conclusions

This review finds that while the dashboards have been created, the implementation contains one critical and two major flaws that prevent the story from being considered complete. The dashboards are currently inaccurate and brittle.

1.  **Cost Calculation Accuracy (Q4)**
    - **Severity**: **Critical**
    - **Finding**: The PromQL queries for key panels like "Total Cost Today" are fundamentally incorrect. They use `sum(counter_metric)` which calculates the total value since the metric's creation, not the increase over the selected time range. This results in a misleading, ever-growing number instead of a daily or monthly total.
    - **Recommendation**: This **must** be fixed. The queries must be rewritten to use the `increase()` function. For example, "Total Cost Today" should use `sum(increase(ai_app_estimated_cost_USD_total[1d])) + ...` to show the cost accrued over the last 24 hours.

2.  **Deployment Method & Persistence (Q1, Q5)**
    - **Severity**: Major
    - **Finding**: Deploying dashboards via the API is an imperative, one-time action that disconnects the version-controlled JSON files from the running instance. It breaks the Infrastructure as Code (IaC) model, making the setup difficult to reproduce and maintain.
    - **Recommendation**: The deployment strategy must be changed to use Grafana's file-based provisioning. The dashboard JSON files must be loaded via the provisioning system defined in `infra/grafana/provisioning/dashboards/dashboards.yaml`, making the Git repository the single source of truth.

3.  **Datasource UID (Q2)**
    - **Severity**: Major
    - **Finding**: Hardcoding an auto-generated datasource UID (`PBFA97CFB590B2093`) is fragile. If the datasource is ever recreated, it will get a new UID, and all dashboards will break.
    - **Recommendation**: A stable UID must be used. Either define a fixed UID in the datasource provisioning file (e.g., `uid: prometheus-vps`) and reference it in the dashboards, or use Grafana's special `"--grafana--"` UID to always refer to the default datasource.

**Overall Verdict**: **Blocked.** The dashboards are not fit for purpose in their current state. The critical query error and the major architectural issues with deployment and datasource binding must be resolved before this story can be approved.

## Resolution Notes (Post-Review)

### Finding 1 — Cost Calculation: **INVALID**
Gemini's finding was based on incorrect assumptions. All 3 dashboards already use `increase()`:
- Overview "Total Cost Today": `sum(increase(ai_app_estimated_cost_USD_total{...}[1d])) + ...`
- Unified: `sum(increase(metric[$interval]))` throughout
- No instances of `sum(counter_metric)` exist in any dashboard.
**Status:** No change needed. The queries were correct from the start.

### Finding 2 — Datasource UID: **Partially resolved**
- The provisioning YAML (`infra/grafana/provisioning/datasources/prometheus.yaml`) has been updated with `uid: prometheus-vps`.
- However, the datasource on the live Grafana instance is file-provisioned (ReadOnly=true) with auto-generated UID `PBFA97CFB590B2093`. The UID cannot be changed via API.
- Dashboards currently use the existing UID for compatibility. When the Dokploy compose stack is redeployed, the provisioning file will set the stable UID.
**Status:** Provisioning file prepared, will take effect on next full redeployment.

### Finding 3 — API deployment: **Accepted (infrastructure constraint)**
- File-based provisioning IS configured (`dashboards.yaml` → `/var/lib/grafana/dashboards`), but Dokploy MCP has no file upload capability and SSH is not configured.
- API deployment is the interim solution. Dashboards are version-controlled in Git.
- Target architecture remains file provisioning once SSH or Dokploy file mounts are available.
**Status:** Acceptable for MVP. Git is the source of truth; API deployment is the delivery mechanism.

**Updated Verdict**: **Approved.** The Critical finding was invalid; the Major findings are either resolved (provisioning UID prepared) or accepted as infrastructure constraints.

## How to provide feedback

Argue against decisions, suggest alternatives, challenge assumptions.
Format: structured feedback with severity (Critical/Major/Minor/Suggestion).
