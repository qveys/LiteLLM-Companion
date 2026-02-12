# Phase 2: Endpoint Validation Reports

**Date:** 2026-02-13
**Validator:** Claude Opus 4.6 (automated)
**Total tests:** 314/314 passing
**Endpoints:** 9 validated

---

## Endpoint #1: Desktop Apps

### Files analyzed
- `/src/ai_cost_observer/detectors/desktop.py`
- `/src/ai_cost_observer/telemetry.py` (metric definitions)
- `/tests/detectors/test_desktop.py`
- `/tests/detectors/test_desktop_extended.py`

### Tests executed: 10/10 pass

### Data quality
- **Names:** OK -- Uses `ai.app.running` (ObservableGauge), `ai.app.active.duration` (Counter), `ai.app.cpu.usage` (Gauge), `ai.app.memory.usage` (Gauge), `ai.app.estimated.cost` (Counter). All in `ai.*` namespace.
- **Types:** OK -- `app_running` is ObservableGauge (Bug H1 fix verified), `cpu_usage`/`memory_usage` are Gauge (Bug C3 fix verified), `active_duration`/`estimated_cost` are Counters (monotonic, correct for cumulative values).
- **Attributes:** OK -- Labels are `app.name` and `app.category`, consistent across all metrics from this detector.
- **Units:** OK -- duration in `s`, cpu in `%`, memory in `MB`, cost in `USD`, running in `1`.
- **No double-counting:** OK -- Uses ObservableGauge with snapshot pattern; each scan pushes the complete set of running apps. No UpDownCounter drift risk.
- **Incremental:** OK -- `active_duration` and `estimated_cost` use `Counter.add()` with elapsed time between scans. Only foreground seconds are counted. First scan correctly skips duration (last_scan_time == 0).

### Test gaps
- No test for cost calculation accuracy (cost_per_hour * elapsed/3600)
- No test for multiple helper processes of same app (e.g., ChatGPT + ChatGPTHelper both matching)
- No test for `get_foreground_app()` exception handling (line 58-60)
- No test for case sensitivity of process name matching

### Verdict: VALIDE

---

## Endpoint #2: CLI Processes

### Files analyzed
- `/src/ai_cost_observer/detectors/cli.py`
- `/src/ai_cost_observer/telemetry.py` (metric definitions)
- `/tests/detectors/test_cli.py`
- `/tests/detectors/test_cli_extended.py`

### Tests executed: 7/7 pass

### Data quality
- **Names:** OK -- Uses `ai.cli.running` (ObservableGauge), `ai.cli.active.duration` (Counter), `ai.cli.estimated.cost` (Counter). All in `ai.*` namespace.
- **Types:** OK -- `cli_running` is ObservableGauge (Bug H1 fix verified). Duration and cost are Counters.
- **Attributes:** OK -- Labels are `cli.name` and `cli.category`, consistent across all metrics.
- **Units:** OK -- duration in `s`, cost in `USD`, running in `1`.
- **No double-counting:** OK -- PID-based dedup with desktop detector. When desktop_detector is provided, its `claimed_pids` are excluded. Fallback to name-based dedup when no desktop_detector reference is available. ObservableGauge snapshot pattern avoids drift.
- **Incremental:** OK -- Duration tracking uses elapsed between monotonic timestamps. First scan skips duration (last_scan_time == 0).

### Test gaps
- No test for PID-based dedup with desktop detector (the `desktop_detector` parameter is never tested with a real DesktopDetector mock providing claimed_pids)
- No test for CLI duration/cost calculation accuracy
- No test for cmdline_patterns fallback in CLI detector
- No test for name-based dedup (when process name overlaps with desktop config)

### Verdict: VALIDE

---

## Endpoint #3: Browser History

### Files analyzed
- `/src/ai_cost_observer/detectors/browser_history.py`
- `/src/ai_cost_observer/telemetry.py` (metric definitions)
- `/tests/detectors/test_browser_history.py`
- `/tests/detectors/test_browser_history_extended.py`

### Tests executed: 9/9 pass

### Data quality
- **Names:** OK -- Uses `ai.browser.domain.visit.count` (Counter), `ai.browser.domain.active.duration` (Counter), `ai.browser.domain.estimated.cost` (Counter). All in `ai.*` namespace.
- **Types:** OK -- All are Counters (monotonic cumulative values).
- **Attributes:** OK -- Labels include `ai.domain`, `ai.category`, `browser.name`, `usage.source` ("history_parser"). Cost labels use only `ai.domain` and `ai.category` (no browser.name, which is correct since cost is domain-level).
- **Units:** OK -- visit count in `1`, duration in `s`, cost in `USD`.
- **No double-counting:** OK -- Uses `_last_scan_time` per browser to only query visits since last successful scan. `since` parameter in SQL WHERE clause ensures no reprocessing.
- **Incremental:** OK -- Each scan updates `_last_scan_time[browser_name]` after successful processing. Only new visits since last scan are queried.

### Test gaps
- No test for `_url_matches_domain()` with subdomain matching (e.g., `api.chatgpt.com` matching `chatgpt.com`)
- No test for domain-with-path matching (e.g., `github.com/copilot`)
- No test for multiple browsers in a single scan cycle
- No test for session gap algorithm with >30min gap producing multiple sessions
- No test for incremental behavior across multiple scans (only one scan per test)
- No test for Vivaldi, Opera, or Arc browsers specifically

### Verdict: VALIDE

---

## Endpoint #4: Shell History

### Files analyzed
- `/src/ai_cost_observer/detectors/shell_history.py`
- `/src/ai_cost_observer/telemetry.py` (metric definitions)
- `/tests/test_shell_history.py`
- `/tests/test_shell_history_extended.py`

### Tests executed: 11/11 pass

### Data quality
- **Names:** OK -- Uses `ai.cli.command.count` (Counter). In `ai.*` namespace.
- **Types:** OK -- Counter (monotonic, accumulates command counts).
- **Attributes:** OK -- Labels use `cli.name` (the tool name from config).
- **Units:** OK -- count in `1`.
- **No double-counting:** OK -- Uses byte offset tracking per history file. Reads only new bytes since last offset. Handles file truncation/rotation by resetting offset.
- **Incremental:** OK -- Offsets are persisted to `shell_history_offsets.txt` in state_dir. Tested with incremental parsing test.

### Test gaps
- No test for offset persistence across parser restarts (new ShellHistoryParser instance)
- No test for file truncation/rotation handling (file_size < offset case)
- No test for binary/encoding errors in history file
- No test verifying that the `command_patterns` regex correctly handles piped commands (e.g., `cat file | claude`)

### Verdict: VALIDE

---

## Endpoint #5: Token Tracker (Claude Code JSONL)

### Files analyzed
- `/src/ai_cost_observer/detectors/token_tracker.py` (specifically `_scan_claude_code` and `_process_claude_jsonl`)
- `/src/ai_cost_observer/telemetry.py` (metric definitions)
- `/tests/test_token_tracker.py` (TestEstimateCost, TestTokenTrackerClaudeCode, TestTokenTrackerCacheCostInScan, TestTokenTrackerOffsetPersistence)

### Tests executed: 17/17 pass (Claude Code-related tests from the 20 total)

### Data quality
- **Names:** OK -- Uses `ai.tokens.input_total` (Counter), `ai.tokens.output_total` (Counter), `ai.tokens.cost_usd_total` (Counter), `ai.prompt.count_total` (Counter). All in `ai.*` namespace.
- **Types:** OK -- All Counters (monotonic cumulative token/cost/prompt counts).
- **Attributes:** OK -- Labels use `tool.name` ("claude-code") and `model.name` (from JSONL entry). Prompt count uses `tool.name` and `source` ("cli").
- **Units:** OK -- Token counts use `1`, cost uses `1` (to avoid double `_USD_total` suffix in Prometheus).
- **No double-counting:** OK -- File offset tracking ensures each JSONL entry is processed exactly once. Entries without usage data or with zero tokens are skipped.
- **Incremental:** OK -- File offsets persisted in `token_tracker_state.json`. Tested: incremental reading, offset persistence across restarts, new data after restart.

### Test gaps
- No test for malformed JSONL lines (partially written entries)
- No test for nested usage under `message.usage` path
- No test for the prompt_db integration (insert_prompt calls)
- No test for concurrent file access (JSONL being written while reading)

### Verdict: VALIDE

---

## Endpoint #6: Token Tracker (Codex SQLite)

### Files analyzed
- `/src/ai_cost_observer/detectors/token_tracker.py` (specifically `_scan_codex`)
- `/src/ai_cost_observer/telemetry.py` (metric definitions)
- `/tests/test_token_tracker.py` (TestCodexScannerIncremental)

### Tests executed: 3/3 pass (Codex-specific tests)

### Data quality
- **Names:** OK -- Uses same metrics as Claude Code: `ai.tokens.input_total`, `ai.tokens.output_total`, `ai.tokens.cost_usd_total`, `ai.prompt.count_total`. All in `ai.*` namespace.
- **Types:** OK -- All Counters.
- **Attributes:** OK -- Labels use `tool.name` ("codex-cli") and `model.name` (from DB row). Prompt count uses `tool.name` and `source` ("cli").
- **Units:** OK -- Same as Claude Code endpoint.
- **No double-counting:** OK -- Uses `rowid > last_rowid` WHERE clause to only process new rows. Last rowid is tracked and persisted.
- **Incremental:** OK -- `_codex_last_rowid` persisted in `token_tracker_state.json`. Tested: no reprocessing on second scan, only new rows processed, rowid survives restart.

### Test gaps
- No test for Codex DB with missing columns (e.g., no `output_tokens` or `model` column)
- No test for Codex DB with missing `sessions` table (returns early, but untested)
- No test for SQLite read-only mode failure
- No test for Codex DB schema changes (adaptive column detection is present but untested)

### Verdict: VALIDE

---

## Endpoint #7: HTTP Receiver Browser

### Files analyzed
- `/src/ai_cost_observer/server/http_receiver.py` (specifically `/metrics/browser` route)
- `/src/ai_cost_observer/telemetry.py` (metric definitions)
- `/tests/test_http_receiver_values.py`

### Tests executed: 2/2 pass

### Data quality
- **Names:** OK -- Uses `ai.browser.domain.active.duration` (Counter), `ai.browser.domain.visit.count` (Counter), `ai.browser.domain.estimated.cost` (Counter). All in `ai.*` namespace.
- **Types:** OK -- All Counters (monotonic cumulative).
- **Attributes:** OK -- Labels include `ai.domain`, `ai.category`, `browser.name`, `usage.source` ("extension"). Cost labels use only `ai.domain` and `ai.category`.
- **Units:** OK -- Duration in `s`, visit count in `1`, cost in `USD`.
- **No double-counting:** OK -- Each POST from the Chrome extension contains delta values (duration_seconds and visit_count since last report). The receiver adds them as increments. No server-side state accumulation.
- **Incremental:** OK -- Extension sends deltas; server just forwards to OTel counters.

### Test gaps
- No test for malformed event data (missing duration_seconds, non-numeric values)
- No test for zero duration_seconds (should not add to counter, verified in code but not tested)
- No test for zero visit_count behavior
- No test for multiple events in a single POST
- No test for concurrent POST requests
- No test for the `/api/extension-config` endpoint

### Verdict: VALIDE

---

## Endpoint #8: HTTP Receiver Tokens

### Files analyzed
- `/src/ai_cost_observer/server/http_receiver.py` (specifically `/api/tokens` route)
- `/src/ai_cost_observer/telemetry.py` (metric definitions)
- `/tests/test_http_tokens.py`

### Tests executed: 5/5 pass

### Data quality
- **Names:** OK -- Uses `ai.tokens.input_total` (Counter), `ai.tokens.output_total` (Counter), `ai.prompt.count_total` (Counter). Cost is computed via `estimate_cost()` when going through the token_tracker path. When no token_tracker is present, cost is NOT recorded (only input/output/prompt_count) -- this is a minor gap.
- **Types:** OK -- All Counters.
- **Attributes:** OK -- Labels use `tool.name` and `model.name`. Prompt count uses `tool.name` and `source` ("browser").
- **Units:** OK -- Token counts in `1`.
- **No double-counting:** OK -- Each POST event is processed once. No server-side dedup needed since events are unique API intercepts.
- **Incremental:** OK -- Each event is a one-time intercept, no reprocessing.

### Test gaps
- No test for cost calculation via token_tracker.record_api_intercept (cost is computed there but not verified)
- No test for events with type != "api_intercept" (should be ignored, but untested)
- No test for missing fields in token event (e.g., no tool, no model)
- No test for the fallback path cost computation (without token_tracker, `tokens_cost_usd_total` is never called)

### Verdict: INVALIDE
### Issue: HTTP receiver `/api/tokens` fallback path does not record cost metric

**Description:** When `_token_tracker` is None (no token tracker configured), the `/api/tokens` endpoint records `tokens_input_total`, `tokens_output_total`, and `prompt_count_total` but does NOT compute or record `tokens_cost_usd_total`. This means token cost data is silently lost when the token tracker is not initialized. The code at lines 148-157 of `http_receiver.py` skips cost estimation entirely, while the `record_api_intercept` path (line 329 of `token_tracker.py`) correctly calls `estimate_cost()` and records the cost metric.

**Impact:** Medium -- if token_tracker initialization fails or is not configured, all browser-intercepted token costs are lost. In practice, token_tracker is always initialized in `main.py`, so this only affects edge cases and the direct-telemetry fallback path.

---

## Endpoint #9: WSL Detector

### Files analyzed
- `/src/ai_cost_observer/detectors/wsl.py`
- `/src/ai_cost_observer/telemetry.py` (metric definitions)
- `/tests/test_wsl_detector.py`
- `/tests/test_wsl_extended.py`

### Tests executed: 6/6 pass

### Data quality
- **Names:** NOK -- Uses `self.telemetry.cli_running.add(1, labels)` and `self.telemetry.cli_running.add(-1, labels)`, but `cli_running` is now an **ObservableGauge** (Bug H1 fix). ObservableGauge does not have an `.add()` method -- it uses a callback-based pattern. The WSL detector was NOT updated for the Bug H1 fix.
- **Types:** NOK -- Calls `.add()` on what should be an ObservableGauge. In the real TelemetryManager, `cli_running` is created via `create_observable_gauge()`, which returns an `ObservableGauge` instance. The ObservableGauge API does NOT support `.add()`. This code will either silently fail or raise an AttributeError at runtime on Windows.
- **Attributes:** OK -- Labels include `cli.name`, `cli.category`, `runtime.environment` ("wsl"), `wsl.distro`. Extra WSL-specific context attributes are a good addition.
- **Units:** N/A (uses parent metric).
- **No double-counting:** OK -- Set-based transition tracking (started = current - previous, stopped = previous - current) ensures each start/stop is emitted exactly once.
- **Incremental:** NOK -- Uses UpDownCounter pattern (+1/-1) which is incompatible with the ObservableGauge pattern used by the main CLI detector. The WSL detector should instead feed into the `set_running_cli()` snapshot or use its own snapshot-based approach.

### Test gaps
- Tests pass because they use a custom `_Recorder` mock (not the real TelemetryManager), so the `.add()` call is accepted by the mock
- No integration test that verifies WSL detector works with the real TelemetryManager
- No test for `FileNotFoundError` when wsl.exe is not found (self._enabled = False path)
- No test for subprocess timeout handling

### Verdict: INVALIDE
### Issue: WSL detector uses UpDownCounter `.add()` pattern on ObservableGauge metric

**Description:** The WSL detector (`wsl.py`, lines 96-101) calls `self.telemetry.cli_running.add(1, labels)` and `self.telemetry.cli_running.add(-1, labels)` for start/stop transitions. However, after the Bug H1 fix, `cli_running` is an `ObservableGauge` created via `self.meter.create_observable_gauge()` in `telemetry.py` (line 103). `ObservableGauge` does not support the `.add()` API -- it uses a callback (`_observe_cli_running`) that yields `Observation` objects based on the `_running_cli` snapshot.

The WSL detector needs to be refactored to feed its running tools into the `set_running_cli()` snapshot mechanism (or maintain its own snapshot that the CLI ObservableGauge callback can merge), instead of calling `.add()` directly.

**Impact:** High on Windows -- the WSL detector will silently fail or raise an error at runtime when it tries to call `.add()` on the ObservableGauge. All WSL tool detection is broken on Windows. Does not affect macOS/Linux since the detector is disabled (no-op) on those platforms.

---

# Summary

| # | Endpoint | Tests | Verdict |
|---|----------|-------|---------|
| 1 | Desktop apps | 10/10 | VALIDE |
| 2 | CLI processes | 7/7 | VALIDE |
| 3 | Browser history | 9/9 | VALIDE |
| 4 | Shell history | 11/11 | VALIDE |
| 5 | Token tracker (Claude Code JSONL) | 17/17 | VALIDE |
| 6 | Token tracker (Codex SQLite) | 3/3 | VALIDE |
| 7 | HTTP receiver browser | 2/2 | VALIDE |
| 8 | HTTP receiver tokens | 5/5 | INVALIDE |
| 9 | WSL detector | 6/6 | INVALIDE |

**Totals:**
- **VALIDE:** 7 endpoints
- **INVALIDE:** 2 endpoints
- **Tests passing:** 314/314 (all pass, but 2 endpoints have issues not caught by tests because tests use mocks that mask the bugs)

## Architecture Doc Discrepancies

The `docs/architecture.md` metric table (lines 107-122) is outdated:
1. `ai.app.running` is listed as UpDownCounter -- should be ObservableGauge (Bug H1 fix)
2. `ai.cli.running` is listed as UpDownCounter -- should be ObservableGauge (Bug H1 fix)
3. `ai.app.cpu.usage` is listed as Histogram -- should be Gauge (Bug C3 fix)
4. `ai.app.memory.usage` is listed as Histogram -- should be Gauge (Bug C3 fix)
5. Token metric labels in the doc say `cli_name` but code uses `tool.name` and `model.name`
6. Metric name `ai.tokens.input.total` in doc has dots but code uses `ai.tokens.input_total` (underscore)
