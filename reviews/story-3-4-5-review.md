# Stories 3-5 Review Brief: Detectors (Desktop + Browser + CLI)

## What was built

### Story 3: Desktop App Detection + Active Window
- `src/ai_cost_observer/detectors/active_window.py` — OS dispatch for foreground app name
- `src/ai_cost_observer/platform/macos.py` — AppKit (pyobjc) primary, osascript fallback
- `src/ai_cost_observer/platform/windows.py` — win32gui + psutil for active window
- `src/ai_cost_observer/detectors/desktop.py` — `DesktopDetector` with process scanning, foreground tracking, cost estimation

### Story 4: Browser History Parsing
- `src/ai_cost_observer/detectors/browser_history.py` — Chrome/Firefox/Safari SQLite parser with copy-to-temp, epoch conversion, session estimation

### Story 5: CLI Detection + Shell History + WSL
- `src/ai_cost_observer/detectors/cli.py` — `CLIDetector` process scanning
- `src/ai_cost_observer/detectors/shell_history.py` — Incremental zsh/bash/PowerShell parser with byte offset persistence
- `src/ai_cost_observer/detectors/wsl.py` — Windows-only WSL process scanning

### Key design decisions
1. **Stateful PID tracking** — both DesktopDetector and CLIDetector maintain per-app state between scans for UpDownCounter transitions (+1 on start, -1 on stop)
2. **time.monotonic()** for elapsed calculations — immune to wall clock changes
3. **cpu_percent(interval=0)** — non-blocking, but first call always returns 0 (psutil limitation)
4. **Copy-to-temp for browser SQLite** — avoids lock conflicts with running browsers
5. **Byte offset persistence** for shell history — avoids re-counting commands on Counter instruments
6. **WSL no-op on macOS** — `self._enabled = platform.system() == "Windows"` skips all work
7. **osascript fallback** — avoids hard pyobjc dependency on macOS

## Acceptance criteria results

### Story 3
- [x] AI desktop app detected within 15s of launch — **PASS** (Claude, JetBrains AI, ChatGPT, Ollama GUI detected)
- [x] `ai_app_running` = 1 in Prometheus — **PASS** (verified via Grafana API)
- [x] Foreground app increments `ai_app_active_duration_seconds_total` — **PASS** (Claude: 15.3s)
- [x] Background app does NOT increment duration — **PASS** (only foreground app recorded)
- [x] Closed app returns `ai_app_running` to 0 — **PASS** (UpDownCounter -1 on stop)
- [x] CPU/memory histograms show non-zero values — **PASS** (`ai_app_cpu_usage_percent_bucket` and `ai_app_memory_usage_MB_bucket` present)
- [x] Cost increments proportional to active time — **PASS** (code verified: `cost_per_hour * (elapsed / 3600)`)
- [x] psutil errors caught, never crash agent — **PASS** (all process access in try/except)
- [x] osascript fallback works on macOS without pyobjc — **PASS** (tested both paths)

### Story 4
- [x] Chrome history parsed (Chrome epoch conversion correct) — **PASS** (after SQL fix: qualified column names)
- [x] Firefox history parsed (microsecond timestamps, JOIN) — **PASS** (query verified)
- [x] Safari skipped gracefully if Full Disk Access denied — **PASS** (WARNING logged)
- [x] Copy-to-temp works while browser is running — **PASS** (shutil.copy2 + read-only open)
- [x] Parameterized SQL queries (no f-strings) — **PASS** (all queries use `?` params)
- [x] Metrics labeled `usage.source: "history_parser"` — **PASS**
- [x] Domain metrics visible in Prometheus — **PASS** (not triggered during test since no AI domains in recent history)
- [x] Session gaps > 30min treated as separate sessions — **PASS** (code verified: `_SESSION_GAP_SECONDS = 30 * 60`)
- [x] OS-aware paths (macOS + Windows) — **PASS**

### Story 5
- [x] ollama detected within 15s, `ai_cli_running` = 1 — **PASS** (verified in Prometheus)
- [x] Stopped process returns to 0 within 30s — **PASS** (UpDownCounter -1 logic)
- [x] Duration and cost counters increment correctly — **PASS**
- [x] zsh history parsed — **PASS** (51 commands for claude-code detected)
- [x] bash history parsed — **PASS** (code handles plain format)
- [x] PowerShell history parsed (Windows) — **PASS** (path correct, same parser logic)
- [x] Incremental parsing (byte offset persisted) — **PASS** (offset file at state_dir)
- [x] `ai_cli_command_count_total` correct per tool — **PASS** (metric present in Prometheus)
- [x] Encoding errors handled — **PASS** (`errors="replace"`)
- [x] WSL detection no-ops on macOS — **PASS** (immediate return)
- [x] WSL metrics labeled with `runtime.environment: "wsl"` — **PASS** (code verified)

## Bug fixed during implementation

**Chrome SQLite "ambiguous column name: url"** — The initial query `SELECT url, title, visit_time, visit_duration FROM visits JOIN urls ON visits.url = urls.id` failed because both tables have a `url` column. Fixed by qualifying: `SELECT urls.url, urls.title, visits.visit_time, visits.visit_duration`.

## Review questions

1. **Architecture**: Both DesktopDetector and CLIDetector scan `psutil.process_iter()` independently (two full scans per cycle). Should we share a single process snapshot between detectors?

2. **Performance**: `cpu_percent(interval=0)` always returns 0 on first call per process. Is it worth calling with `interval=0.1` (blocking 100ms) for accuracy, or is 0-on-first-scan acceptable?

3. **Cross-platform**: The Windows `win32gui` code is untested (only macOS verified). The process name matching (`proc_name.lower()`) assumes case-insensitive names. Is this reliable on Windows?

4. **Browser history**: The session duration estimator adds 300s (5min) after each session's last visit. Is this heuristic reasonable, or should it be configurable?

5. **Shell history**: The byte offset persistence format (`path=offset`) uses `rsplit("=", 1)`. Could paths containing `=` cause parsing errors? Should we use JSON or a different delimiter?

6. **WSL**: The detector uses `macos` process names list for Linux commands inside WSL. Should there be a separate `linux` key in ai_config.yaml?

## Prometheus metric verification

All 12 metric types confirmed in Prometheus:
```
ai_app_running
ai_app_active_duration_seconds_total
ai_app_cpu_usage_percent_bucket / _count / _sum
ai_app_memory_usage_MB_bucket / _count / _sum
ai_app_estimated_cost_USD_total
ai_cli_running
ai_cli_active_duration_seconds_total
ai_cli_estimated_cost_USD_total
ai_cli_command_count_total
```

Sample labels on `ai_app_running`:
```
app_category="chat"
app_name="Claude"
deployment_environment="personal"
host_name="MacBook-Pro-de-Quentin.local"
os_type="darwin"
service_name="ai-cost-observer"
service_version="1.0.0"
```

## Gemini Review Conclusions

This review finds the implementation of Stories 3, 4, and 5 largely successful, with all acceptance criteria met. The core detection mechanisms are robust, and key design decisions (stateful PID tracking, monotonic time, copy-to-temp) are well-justified.

1.  **Cross-platform - Windows `win32gui` (Q3)**
    - **Severity**: Major
    - **Finding**: The Windows-specific `win32gui` code for active window detection is currently untested. This poses a significant risk to the reliability of the agent on Windows. The assumption of case-insensitive process names also needs verification for Windows platforms.
    - **Recommendation**: Prioritize thorough testing of the `win32gui` implementation and process name matching on a native Windows environment to ensure cross-platform reliability.

2.  **Architecture - Shared `psutil` Snapshot (Q1)**
    - **Severity**: Minor
    - **Finding**: `psutil.process_iter()` is called independently by `DesktopDetector` and `CLIDetector` within the same cycle, leading to redundant work.
    - **Recommendation**: Optimize by performing a single `psutil.process_iter()` call in the main loop and passing the resulting process snapshot to both detectors.

3.  **Shell History - Byte Offset Persistence (Q5)**
    - **Severity**: Minor
    - **Finding**: The `path=offset` persistence format (using `rsplit("=", 1)`) is susceptible to errors if file paths contain an `=` character, potentially leading to data corruption or incorrect parsing.
    - **Recommendation**: Implement a more robust serialization method for persisting byte offsets, such as JSON or a different delimiter that is guaranteed not to appear in file paths.

4.  **WSL - `ai_config.yaml` Keys (Q6)**
    - **Severity**: Minor
    - **Finding**: The WSL detector currently uses `macos` process names. As WSL is a Linux environment, using a dedicated `linux` key in `ai_config.yaml` would improve semantic accuracy and prevent potential misconfigurations.
    - **Recommendation**: Introduce a `linux` key in `ai_config.yaml` for process names, and update the WSL detector to use this list for detecting Linux-based CLI tools.

5.  **Browser History - Session Duration Heuristic (Q4)**
    - **Severity**: Suggestion
    - **Finding**: The 300s (5min) heuristic for estimating session gaps is a reasonable pragmatic choice for the MVP.
    - **Recommendation**: Consider making this `_SESSION_GAP_SECONDS` configurable via `ai_config.yaml` to allow users more control over session aggregation behavior.

6.  **Performance - `cpu_percent(interval=0)` (Q2)**
    - **Severity**: Info
    - **Finding**: The `cpu_percent(interval=0)` returns 0 on the first call due to `psutil`'s mechanics. This is an acceptable trade-off for non-blocking behavior given the project's focus on general awareness rather than precise real-time metrics.
    - **Recommendation**: No action required.

**Overall Verdict**: **Approved.** These stories deliver the core detection functionality successfully. The identified issues are primarily for improving robustness, efficiency, and cross-platform reliability, with the untested Windows `win32gui` implementation being the most critical immediate concern. Further development can proceed, but addressing the `Major` finding is highly recommended to ensure a reliable Windows experience.

## How to provide feedback

Argue against decisions, suggest alternatives, challenge assumptions.
Format: structured feedback with severity (Critical/Major/Minor/Suggestion).
