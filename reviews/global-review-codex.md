# Global Review (Codex)

Date: 2026-02-12
Scope: Stories 0-8 (design, infra, detectors, HTTP receiver + extension, dashboards, daemon scripts)

## Executive verdict

The project is functionally complete for MVP, but analytics correctness is not yet reliable enough to treat dashboard values as a trusted source of truth.

Release recommendation: **Approve for personal beta only**, with mandatory fixes on metric correctness and dashboard query consistency before broader usage.

## Findings by severity

1. **Critical** — WSL running metric can inflate indefinitely.
Reference: `src/ai_cost_observer/detectors/wsl.py:81`.
Why: `cli_running.add(1, ...)` is emitted on each scan without state tracking and without a matching decrement path.
Impact: `ai_cli_running` can drift upward over time, breaking "currently running" semantics.

2. **Major** — Browser dashboard panels ignore global filters.
References: `infra/grafana/dashboards/browser-ai-usage.json:369`, `infra/grafana/dashboards/browser-ai-usage.json:427`.
Why: `Duration by Category` and `Domain Details` filter only on `host_name`, while dashboard variables include `$browser`, `$category`, `$source`.
Impact: dashboard sections disagree under filtering, leading to misleading analysis.

3. **Major** — "Cost Accumulation Over Time" is not a true running total.
Reference: `infra/grafana/dashboards/unified-cost.json:438`.
Why: `increase(...[$__rate_interval])` returns a rolling delta, not a monotonic cumulative series.
Impact: panel title/description overpromise behavior; readers can misinterpret cost trends.

4. **Major** — Extension retry logic does not handle HTTP error responses.
Reference: `chrome-extension/background.js:180`, `chrome-extension/background.js:185`.
Why: only network exceptions trigger re-queue; non-2xx responses are treated as success.
Impact: data loss when agent returns validation/server errors.

5. **Major** — Popup totals can be overcounted when retries occur.
References: `chrome-extension/background.js:177`, `chrome-extension/background.js:188`, `chrome-extension/background.js:201`.
Why: daily totals are updated before delivery confirmation, then failed batches are re-queued and counted again on next attempt.
Impact: UI totals diverge from ingested backend metrics.

6. **Major** — Browser history scanner can skip intervals after transient parse failures.
References: `src/ai_cost_observer/detectors/browser_history.py:35`, `src/ai_cost_observer/detectors/browser_history.py:36`, `src/ai_cost_observer/detectors/browser_history.py:43`.
Why: `_last_scan_time` is advanced before parsing each browser.
Impact: on lock/permission/sql errors, events in the failed window can be permanently missed.

7. **Minor** — Desktop process mapping has name collisions.
References: `src/ai_cost_observer/detectors/desktop.py:43`, `src/ai_cost_observer/data/ai_config.yaml:7`, `src/ai_cost_observer/data/ai_config.yaml:65`.
Why: identical process names (e.g., ChatGPT process reused by DALL-E profile) are overwritten in lookup map.
Impact: attribution can be wrong for overlapping tools.

8. **Minor** — Extension endpoint is hardcoded while agent port is configurable.
References: `chrome-extension/background.js:7`, `chrome-extension/popup.js:6`, `src/ai_cost_observer/config.py:37`.
Impact: extension breaks if `http_receiver_port` changes.

## Recommended remediation order

1. Fix WSL detector statefulness (`+1/-1` transitions only).
2. Patch dashboard queries in `browser-ai-usage.json` to include `$browser`, `$category`, `$source` everywhere.
3. Rework `Cost Accumulation Over Time` query semantics or rename panel to delta-based wording.
4. Make extension delivery idempotent:
   - treat non-2xx as failure,
   - only update popup totals after successful POST,
   - persist pending deltas in `chrome.storage.local`.
5. Make browser history watermark update transactional (advance checkpoint only after successful processing).
6. Resolve process-name collisions via multi-match strategy or explicit priority rules.

## What is already strong

- Good modular boundaries between config/telemetry/detectors/server.
- Sensible cross-platform split (`platform/macos.py`, `platform/windows.py`).
- Clear metric naming convergence in docs and implementation.
- Service install scripts and README are practical for personal deployment.

## Final opinion

This is a solid MVP architecture with good momentum, but current observability correctness has several high-impact edge cases.
Once the 6 remediation items above are applied, the dashboards can be considered operationally trustworthy.
