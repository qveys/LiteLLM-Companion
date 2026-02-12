# Targeted Audit: Performance, Security, PromQL, Install Scripts (Codex)

Date: 2026-02-12
Method: static audit of implementation/configuration + security guidance cross-check (Python Flask + JavaScript frontend patterns)

## Performance findings

1. **Major** — Duplicate full process scans every cycle.
References: `src/ai_cost_observer/detectors/desktop.py:60`, `src/ai_cost_observer/detectors/cli.py:49`.
Details: desktop and CLI detectors each iterate `psutil.process_iter(...)` independently on the same cadence.
Impact: avoidable CPU overhead; likely acceptable for MVP but scales poorly with large process tables.

2. **Major** — Browser history checkpointing is not failure-safe.
References: `src/ai_cost_observer/detectors/browser_history.py:35`, `src/ai_cost_observer/detectors/browser_history.py:36`, `src/ai_cost_observer/detectors/browser_history.py:43`.
Impact: parse failures can skip historical windows and permanently lose accounting data.

3. **Minor** — Desktop process-name map overwrite risk affects precision.
References: `src/ai_cost_observer/detectors/desktop.py:43`, `src/ai_cost_observer/data/ai_config.yaml:7`, `src/ai_cost_observer/data/ai_config.yaml:65`.
Impact: mis-attribution can distort per-tool totals.

## Security findings

Notes:
- This stack intentionally accepts insecure OTLP for personal MVP; lack of TLS is not flagged as an immediate defect in this report.

1. **Major** — Local metrics ingestion endpoint has no integrity guard beyond loopback binding.
References: `src/ai_cost_observer/server/http_receiver.py:27`, `src/ai_cost_observer/server/http_receiver.py:50`, `chrome-extension/manifest.json:12`.
Details: any local process can POST synthetic events.
Impact: local malware/rogue process can poison cost metrics.

2. **Major** — Bearer token at rest remains plaintext by default.
References: `src/ai_cost_observer/config.py:55`, `src/ai_cost_observer/config.py:72`, `docs/stories.md:248`.
Impact: token exposure risk on compromised workstation user profile.

3. **Minor** — Request payload lacks explicit bounds/type hardening on all numeric fields.
References: `src/ai_cost_observer/server/http_receiver.py:39`, `src/ai_cost_observer/server/http_receiver.py:40`, `src/ai_cost_observer/server/http_receiver.py:60`.
Impact: malformed/big local payloads can create noise or resource pressure.

## PromQL / dashboard findings

1. **Major** — Browser dashboard ignores active filter variables in 2 panels.
References: `infra/grafana/dashboards/browser-ai-usage.json:369`, `infra/grafana/dashboards/browser-ai-usage.json:427`.
Impact: inconsistent panel outputs under `$browser/$category/$source` filtering.

2. **Major** — "Cost Accumulation Over Time" uses rolling deltas, not cumulative totals.
Reference: `infra/grafana/dashboards/unified-cost.json:543`.
Impact: panel behavior does not match its label/description.

3. **Major** — Datasource UID mismatch between provisioning and dashboards.
References: `infra/grafana/provisioning/datasources/prometheus.yaml:6`, `infra/grafana/dashboards/ai-cost-overview.json:100`.
Details: provisioning defines `uid: prometheus-vps`, while dashboards reference `PBFA97CFB590B2093`.
Impact: freshly provisioned environments can load broken dashboards with missing datasource bindings.

## Install-script findings

1. **Major** — macOS launchd path remains environment-dependent.
References: `service/com.ai-cost-observer.plist:10`, `service/install-macos.sh:32`.
Details: service executes `/usr/bin/env python3` rather than pinning installer-resolved interpreter path.
Impact: wrong interpreter selection in multi-Python setups (`pyenv`, mixed system/Homebrew/venv).

2. **Minor** — Uninstall parity is now good.
References: `service/uninstall-macos.sh:1`, `service/uninstall-windows.ps1:1`.
Impact: improvement acknowledged; no issue.

3. **Minor** — Runtime log rotation is implemented in app layer.
Reference: `src/ai_cost_observer/main.py:41`.
Impact: mitigates long-lived log growth risk, especially on Windows.

## Recommended remediation sequence

1. Fix datasource UID mismatch and the 3 dashboard query issues.
2. Fix extension delivery semantics (HTTP status handling + idempotent popup accounting).
3. Make WSL and browser-history metric pipelines stateful/failure-safe.
4. Pin macOS daemon interpreter path during install.
5. Move token retrieval to OS credential stores (post-MVP item already tracked).
