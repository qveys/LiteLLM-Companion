# Independent PR-Style Review (Codex)

Date: 2026-02-12
Mode: full snapshot review (no `HEAD` baseline available in this repository state)

## Findings

1. **Critical** — WSL running counter can drift upward indefinitely.
References: `src/ai_cost_observer/detectors/wsl.py:81`.
Details: `cli_running.add(1, ...)` is emitted on detections but there is no state tracking and no decrement path for stopped processes.
Impact: `ai_cli_running` loses semantic meaning ("currently running") and can become arbitrarily large over time.

2. **Major** — Extension retry logic treats HTTP failures as success.
References: `chrome-extension/background.js:180`, `chrome-extension/background.js:185`.
Details: only network exceptions are retried; non-2xx responses are not checked and batches are dropped.
Impact: silent metric loss when local agent returns `4xx/5xx`.

3. **Major** — Popup totals can overcount during retries.
References: `chrome-extension/background.js:177`, `chrome-extension/background.js:188`, `chrome-extension/background.js:201`.
Details: popup totals are updated before POST success is known; failed events are re-queued and counted again later.
Impact: popup values diverge from ingested backend metrics.

4. **Major** — Browser history checkpoint can skip events after transient parser failures.
References: `src/ai_cost_observer/detectors/browser_history.py:35`, `src/ai_cost_observer/detectors/browser_history.py:36`, `src/ai_cost_observer/detectors/browser_history.py:43`.
Details: `_last_scan_time` advances before parsing all browsers.
Impact: lock/permission/sql failures can permanently drop part of the time window.

5. **Major** — Extension domain and cost models diverge from agent source of truth.
References: `chrome-extension/background.js:12`, `chrome-extension/popup.js:9`, `src/ai_cost_observer/server/http_receiver.py:21`, `src/ai_cost_observer/data/ai_config.yaml:94`.
Details: extension tracks domains/rates that do not match `ai_config.yaml`; receiver drops unknown domains by exact lookup.
Impact: backend under-ingests extension activity; popup cost/time can disagree with Prometheus/Grafana.

6. **Minor** — Desktop process mapping has ambiguous collisions.
References: `src/ai_cost_observer/detectors/desktop.py:43`, `src/ai_cost_observer/data/ai_config.yaml:7`, `src/ai_cost_observer/data/ai_config.yaml:65`.
Details: duplicate process names map to a single app entry (`dict` overwrite).
Impact: attribution may be incorrect when multiple logical tools share one executable name.

7. **Minor** — Test suite mostly validates review markdown, not runtime behavior.
References: `tests/test_story_2_review.py:35`, `tests/test_story_3_review.py:36`, `tests/test_story_1_review.py:35`.
Details: many tests assert document content and recommendations rather than agent detector/receiver correctness.
Impact: regressions in production logic can pass CI undetected.

## Validation summary

- `pytest -q`: 99 passed.
- JSON parsing sanity check: all dashboard/manifest JSON files parse successfully.
- Residual risk remains high on metric correctness despite passing tests, due to low runtime coverage of critical detector/export paths.

## Recommended priority order

1. Fix WSL counter state transitions.
2. Make extension delivery idempotent and HTTP-status aware.
3. Align extension domain/rate catalog with `ai_config.yaml` source of truth.
4. Make browser history checkpoint advancement transactional.
5. Add runtime tests for detectors and extension receiver behavior.
