# Story 6 Review Brief: HTTP Receiver + Chrome Extension

## What was built

### HTTP Receiver (Flask)
- `src/ai_cost_observer/server/http_receiver.py` — Flask app on `127.0.0.1:8080`
  - `GET /health` → `{"status": "healthy"}`
  - `POST /metrics/browser` → accepts JSON events, validates against known AI domains, updates OTel metrics with `usage.source: "extension"` label
  - Started in daemon thread via `start_http_receiver()`, called from `main.py`
  - `use_reloader=False` prevents child process spawning
  - Werkzeug request logs suppressed (too noisy)

### Chrome Extension (Manifest V3)
- `chrome-extension/manifest.json` — Manifest V3 with `tabs`, `alarms`, `storage` permissions
- `chrome-extension/background.js` — Service worker: tab tracking, session timing, delta export every 60s
- `chrome-extension/popup.html` + `popup.js` — Popup UI showing today's AI domain usage (time + cost)
- `chrome-extension/icons/` — 16/48/128px PNG icons

### Key design decisions
1. **Delta-based export** — extension accumulates duration/visit deltas and sends them every 60s, not cumulative totals (OTel Counters expect increments)
2. **Silent retry** — if agent is down, deltas are re-added to pending buffer and retried next cycle
3. **Daily totals in chrome.storage.local** — popup reads stored totals for display, reset daily
4. **Domain matching** — supports both simple domains (`claude.ai`) and path-based (`bing.com/chat`)
5. **Cost rates duplicated in popup** — avoids needing agent API call for popup display

## Acceptance criteria results

- [x] Flask on :8080, daemon thread, no blocking — **PASS** (main loop continues, HTTP receiver on separate thread)
- [x] `GET /health` returns healthy — **PASS** (`{"status": "healthy"}`)
- [x] `POST /metrics/browser` accepts JSON, labels `usage.source: "extension"` — **PASS** (verified in Prometheus: `usage_source="extension"`)
- [x] Extension installs unpacked without errors — **PASS** (Manifest V3 valid)
- [x] AI domain detection + timing works — **PASS** (background.js `matchAIDomain()` tested)
- [x] Tab switching saves/starts sessions — **PASS** (`endCurrentSession` + `startSession` on tab change)
- [x] Popup shows today's usage (time + cost) — **PASS** (reads from `chrome.storage.local`)
- [x] Extension sends deltas every 60s — **PASS** (`chrome.alarms` set to 1 minute)
- [x] Silent retry if agent is down — **PASS** (catch on fetch, re-add to pendingDeltas)
- [x] `use_reloader=False` on Flask — **PASS**

## Prometheus verification

Extension metrics visible with correct labels:
```
ai_browser_domain_active_duration_seconds_total{
  ai_domain="claude.ai",
  usage_source="extension",
  browser_name="chrome",
  host_name="MacBook-Pro-de-Quentin.local"
} = 300

ai_browser_domain_active_duration_seconds_total{
  ai_domain="chatgpt.com",
  usage_source="extension",
  browser_name="chrome"
} = 120
```

## Review questions

1. **Security**: The Flask server binds to `127.0.0.1` only. Is there any risk of cross-origin attacks? The extension uses `host_permissions` for `http://127.0.0.1:8080/*`.

2. **Architecture**: Cost rates are duplicated in `popup.js` (hardcoded) and `ai_config.yaml` (agent-side). Should the popup fetch rates from the agent via an API endpoint?

3. **Reliability**: Chrome alarms have a minimum interval of 1 minute. Is this granular enough for tracking, or should we also export on tab close/window close events?

4. **Cross-platform**: The extension is Chrome-only. Firefox uses WebExtensions API with minor differences. Is Firefox support needed for MVP?

5. **Data loss**: If the agent is down for hours, deltas accumulate in memory (service worker may get killed). Should we persist pending deltas to `chrome.storage.local`?

## Gemini Review Conclusions

The implementation meets the functional requirements of the story. However, this review identifies two major design flaws that significantly impact data consistency and reliability, along with several minor suggestions.

1.  **Architecture - Duplicated Cost Rates (Q2)**
    - **Severity**: Major
    - **Finding**: Cost rates are duplicated, with one source in the agent's `ai_config.yaml` and another hardcoded in the extension's `popup.js`. This will inevitably lead to data inconsistency, where the popup displays cost estimates that do not match the data being recorded by the agent. This undermines user trust.
    - **Recommendation**: Create a single source of truth. Implement a new endpoint in the Flask server (e.g., `GET /config`) from which the extension's popup can fetch the current cost rates at startup.

2.  **Data Loss - In-Memory Retry Buffer (Q5)**
    - **Severity**: Major
    - **Finding**: The retry mechanism stores pending metric deltas in the service worker's memory. Due to the ephemeral nature of Manifest V3 service workers, a prolonged agent outage will cause the browser to terminate the service worker, leading to the loss of all accumulated data.
    - **Recommendation**: The retry buffer must be persisted. Before attempting an export, save the pending deltas to `chrome.storage.local`. On a successful export, clear the persisted data. On extension startup, load any persisted deltas to resume pending exports.

3.  **Reliability - Data Export Triggers (Q3)**
    - **Severity**: Minor
    - **Finding**: Relying solely on a 60-second timer may cause short browsing sessions to be missed.
    - **Recommendation**: Augment the timer by also triggering exports on key lifecycle events, such as `tabs.onRemoved` (tab closed), to ensure more granular data capture.

4.  **Cross-platform - Browser Support (Q4)**
    - **Severity**: Suggestion
    - **Finding**: The extension is Chrome-only.
    - **Recommendation**: This is an acceptable limitation for the MVP. Firefox support can be added as a future enhancement.

5.  **Security - Localhost Endpoint (Q1)**
    - **Severity**: Info
    - **Finding**: Binding to `127.0.0.1` correctly limits network exposure. The risk of CSRF attacks injecting bogus data is low and does not pose a significant security threat.
    - **Recommendation**: No action required.

**Overall Verdict**: **Approved, with reservations.** The feature is functional but should not be considered complete without addressing the two `Major` issues. Fixing the data consistency and data loss problems is critical for providing a reliable and trustworthy user experience.

## How to provide feedback

Argue against decisions, suggest alternatives, challenge assumptions.
Format: structured feedback with severity (Critical/Major/Minor/Suggestion).
