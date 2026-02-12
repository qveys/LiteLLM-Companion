# Story 2 Review Brief: Python Skeleton + OTel Wiring

## What was built

- Installable Python package (`ai-cost-observer`) with `pyproject.toml` (hatchling build)
- `AppConfig` dataclass with 3-level config hierarchy: built-in YAML → user file → env vars
- `TelemetryManager` class managing OTel SDK lifecycle: Resource, MeterProvider, 12 metric instruments, OTLP gRPC exporter with bearer token auth
- Main loop with signal handling (SIGTERM/SIGINT) and graceful shutdown (flush + exit)
- Comprehensive `ai_config.yaml` with 12 desktop apps, 21 browser domains, 7 CLI tools

### Files created
- `pyproject.toml` — hatchling build, all deps, entry point
- `.gitignore`, `.python-version`
- `src/ai_cost_observer/__init__.py` — version string
- `src/ai_cost_observer/__main__.py` — `python -m` entry
- `src/ai_cost_observer/config.py` — `AppConfig` dataclass + `load_config()`
- `src/ai_cost_observer/telemetry.py` — `TelemetryManager` with all 12 OTel instruments
- `src/ai_cost_observer/main.py` — main loop, signal handling, lifecycle
- `src/ai_cost_observer/data/ai_config.yaml` — AI tool definitions
- `src/ai_cost_observer/{detectors,exporters,server,platform}/__init__.py` — empty subpackages
- `tests/__init__.py`, `tests/conftest.py`

### Key design decisions
1. **`insecure=True` for gRPC** — The VPS exposes port 4317 without TLS (raw gRPC). TLS would need cert setup on the collector side. For personal use, bearer token + insecure gRPC is pragmatic.
2. **`importlib.resources.files`** for package data — avoids `pkg_resources` deprecation, works with editable installs.
3. **Config env var override** — `OTEL_ENDPOINT`, `OTEL_BEARER_TOKEN`, `OTEL_INSECURE` override YAML config for CI/testing flexibility.
4. **PeriodicExportingMetricReader** interval matches scan interval (15s) — metrics export immediately after each scan.

## Acceptance criteria results

- [x] `pip install -e .` succeeds — **PASS**
- [x] `python -m ai_cost_observer` starts, logs "Agent started" — **PASS**
- [x] Connects to VPS OTel Collector with bearer token — **PASS** (no connection errors in logs)
- [x] Test metric appears in Prometheus on VPS within 30s — **PASS** (`ai_app_running` and `ai_app_active_duration_seconds_total` visible)
- [x] Metrics include `host.name` resource attribute — **PASS** (`host_name: "MacBook-Pro-de-Quentin.local"`)
- [x] `Ctrl+C` triggers graceful shutdown — **PASS** (logs "Shutting down", "Agent stopped")
- [x] `ai_config.yaml` has 12 apps, 21 domains, 7 CLI tools — **PASS**

## Review questions

1. **Architecture**: The `TelemetryManager` creates all 12 instruments upfront. Detectors that aren't active still have instruments allocated. Is lazy instrument creation worth the complexity?

2. **Security**: Bearer token is passed via env var or plaintext YAML (`~/.config/ai-cost-observer/config.yaml`). Is there a better approach for secrets management on a personal workstation?

3. **Performance**: The gRPC exporter uses `insecure=True` over the internet. Should we require TLS for production use, even for personal deployments?

4. **Cross-platform**: The `socket.gethostname()` on Windows returns the NetBIOS name. Is this reliable enough as a device identifier, or should we use a more stable ID?

5. **Config design**: User config merges at the top level only (no deep merge of ai_apps lists). Users must use `extra_ai_apps` to add entries. Is this clear enough, or will users try to override the built-in list?

## Prometheus label verification

Actual labels on `ai_app_running` metric:
```
app_category="test"
app_name="test-app"
deployment_environment="personal"
host_name="MacBook-Pro-de-Quentin.local"
os_type="darwin"
service_name="ai-cost-observer"
service_version="1.0.0"
telemetry_sdk_language="python"
telemetry_sdk_version="1.39.1"
```

## Gemini Review Conclusions (Revised)

After re-reading all project documentation, my previous analysis is superseded. The documents have been updated to resolve prior contradictions. This new review is based on the current, consistent state of the design.

1.  **Insecure Secret Transmission & Storage**
    - **Severity**: Major (Risk Accepted for MVP)
    - **Finding**: The project has made a conscious design decision to accept two security risks for the MVP:
        1.  **Transmission**: Using an insecure gRPC channel to send the bearer token, as now documented in `architecture.md` and `product-brief.md`.
        2.  **Storage**: Storing the token in a plaintext YAML file, with the fix explicitly deferred to a post-MVP "Refinement" story (`stories.md`).
    - **Recommendation**: While these practices are not recommended, they are now consistent with the documented project plan. The "Critical" severity is downgraded to "Major" because the project has formally acknowledged and accepted the risk for the initial MVP. The "Blocked" status is lifted.

2.  **Host Identifier (`Cross-platform` question)**
    - **Severity**: Minor
    - **Finding**: `socket.gethostname()` can be unstable.
    - **Recommendation**: Acceptable for the MVP. A future version should consider a more stable machine identifier to improve long-term data consistency.

3.  **Instrument Creation (`Architecture` question)**
    - **Severity**: Info
    - **Finding**: Eagerly creating all OTel instruments upfront is a sound design choice that favors simplicity and has no significant performance cost.
    - **Recommendation**: No action required.

4.  **Config Merging (`Config design` question)**
    - **Severity**: Info
    - **Finding**: The shallow-merge strategy is a clear and predictable design choice.
    - **Recommendation**: No action required. Ensure this behavior is explained in the user-facing documentation.

**Overall Verdict**: **Approved for MVP.** The implementation aligns with the (now updated) design documents and acceptance criteria. The project is knowingly carrying significant technical debt regarding security, but this has been formally captured in a future refinement story. Development on subsequent stories can proceed.

## How to provide feedback

Argue against decisions, suggest alternatives, challenge assumptions.
Format: structured feedback with severity (Critical/Major/Minor/Suggestion).
