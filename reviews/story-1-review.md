# Story 1 Review Brief: Infrastructure (Dokploy VPS Deployment)

## What was built

- Deployed a 3-service Docker Compose stack on Dokploy VPS (`vps.quentinveys.be`):
  - **OTel Collector** (contrib v0.145.0): OTLP gRPC (:4317) + HTTP (:4318) receivers with `bearertokenauth` extension, Prometheus exporter (:8889)
  - **Prometheus** (v3.0.0): 30-day retention, scrapes OTel Collector on internal network
  - **Grafana** (v11.4.0): HTTPS via Traefik at `grafana-otel.quentinveys.be`, auto-provisioned Prometheus datasource
- Bearer token authentication on OTel Collector — unauthenticated requests return HTTP 401
- Grafana domain with Let's Encrypt TLS via Dokploy/Traefik
- Config files deployed via Dokploy File Mount feature (4 mounts)
- Environment variables managed through Dokploy compose env settings

### Files created/modified
- `infra/docker-compose.yml` — Compose file adapted for Dokploy (no container_name, ../files/ volumes, dokploy-network)
- `infra/otel-collector-config.yaml` — OTel Collector config (bearertokenauth, otlp receivers, prometheus exporter)
- `infra/prometheus.yml` — Prometheus scrape config targeting collector:8889
- `infra/grafana/provisioning/datasources/prometheus.yaml` — Auto-provisioned Prometheus datasource
- `infra/grafana/provisioning/dashboards/dashboards.yaml` — Dashboard provider config
- `infra/.env.example` — Template for required secrets

### Key design decisions
1. **Direct host port binding for OTLP (4317/4318)** instead of routing through Traefik — simpler for gRPC, avoids h2c proxy complexity
2. **Bearer token auth via OTel Collector extension** — built-in, no external auth layer needed
3. **Dokploy File Mount** for config files — persists across deployments, editable via UI
4. **Internal-only Prometheus** — not exposed externally, only accessible via Grafana
5. **`resource_to_telemetry_conversion: enabled`** on Prometheus exporter — promotes OTel resource attributes (host.name, service.name) to Prometheus labels

## Acceptance criteria results

- [x] All 3 services running on Dokploy VPS — **PASS** (all containers "running", deployment status "Done")
- [x] OTel Collector reachable from local machine on port 4317 — **PASS** (`nc -zv` succeeded)
- [x] Unauthenticated OTLP requests rejected — **PASS** (HTTP 401 on port 4318 without token)
- [x] Authenticated OTLP requests accepted — **PASS** (HTTP 200 with `{"partialSuccess":{}}`)
- [x] Prometheus targets show collector UP — **PASS** (`up{job="otel-collector"}` = 1)
- [x] Grafana accessible with Prometheus datasource — **PASS** (`https://grafana-otel.quentinveys.be` returns 200, datasource API returns Prometheus config)
- [x] Test metric flows end-to-end — **PASS** (`test_counter_total` visible in Prometheus via Grafana API)

## Review questions

1. **Security**: Port 4317/4318 are directly exposed on the VPS. The bearer token provides authentication, but is this sufficient? Should we add IP allowlisting or rate limiting at the firewall level?

2. **Architecture**: The `resource_to_telemetry_conversion` setting promotes ALL resource attributes to Prometheus labels. This means high-cardinality attributes could cause label explosion. Is this a concern for a personal-use single/few-device setup?

3. **Reliability**: The OTel Collector has no persistent queue — if it restarts while metrics are in-flight, they're lost. For personal use this seems acceptable, but should we enable `file_storage` extension for the exporter queue?

4. **Performance**: The Prometheus exporter has `metric_expiration: 5m`. If the agent stops sending a metric for 5 minutes, it disappears from Prometheus. Is this the right balance between stale data cleanup and dashboard gaps?

5. **Cross-platform**: The bearer token is stored in Dokploy env vars and will be placed in agent's local config. On Windows, should we recommend storing it in Windows Credential Manager instead of plaintext YAML?

## Deployment details

| Component | Version | Port | Network |
|-----------|---------|------|---------|
| OTel Collector | contrib v0.145.0 | 4317 (gRPC), 4318 (HTTP), 8889 (prom exporter) | otel-net + host |
| Prometheus | v3.0.0 | 9090 (internal only) | otel-net |
| Grafana | v11.4.0 | 3000 → Traefik HTTPS | otel-net + dokploy-network |

**Dokploy compose ID:** `nTmE0zBnlHajlo04MAZd7`
**Grafana URL:** `https://grafana-otel.quentinveys.be`
**OTLP endpoint:** `vps.quentinveys.be:4317` (gRPC) / `vps.quentinveys.be:4318` (HTTP)

## Gemini Review Conclusions

This review finds the infrastructure deployment successful and well-executed according to the acceptance criteria. The key design decisions are sound for an MVP. The following conclusions address the review questions:

1.  **Agent Token Storage (`Cross-platform` question)**
    - **Severity**: **Critical**
    - **Finding**: The proposal to store the bearer token in a plaintext YAML file on the agent's machine is a significant security vulnerability. This exposes the secret to accidental commits, file sharing, or local malware.
    - **Recommendation**: The agent's design **must be modified** to use the native OS credential manager for storing the OTLP bearer token. This includes using Keychain on macOS, Credential Manager on Windows, and a `Secret Service`/`Keyring` solution on Linux. This change should be considered a blocker for any wider distribution of the agent.

2.  **Endpoint Security (`Security` question)**
    - **Severity**: Suggestion
    - **Finding**: Direct exposure of OTLP ports protected only by a bearer token is an acceptable baseline for a personal project MVP, but it could be hardened.
    - **Recommendation**: As a future improvement, consider implementing firewall-level rate-limiting (e.g., using `ufw` or `fail2ban`) on ports 4317 and 4318 to mitigate the risk of brute-force attacks. IP allowlisting is likely too restrictive for personal use cases.

3.  **Resource Attribute Conversion (`Architecture` question)**
    - **Severity**: Suggestion
    - **Finding**: The risk of "label explosion" from `resource_to_telemetry_conversion` is negligible for the current scope, as the defined resource attributes are all low-cardinality.
    - **Recommendation**: To ensure long-term stability, consider adding a `filter` processor to the OTel Collector pipeline to explicitly specify which resource attributes can be promoted to labels. This would prevent future accidental additions of high-cardinality attributes.

4.  **Collector Reliability (`Reliability` question)**
    - **Severity**: Info
    - **Finding**: For a personal cost-awareness tool, losing small amounts of metric data during a collector restart is an acceptable trade-off for simplicity.
    - **Recommendation**: No action required. The current stateless collector design is appropriate.

5.  **Metric Expiration (`Performance` question)**
    - **Severity**: Info
    - **Finding**: The `metric_expiration: 5m` setting is a sensible default that ensures stale data is cleaned up promptly.
    - **Recommendation**: No action required.

**Overall:** The infrastructure is solid. The only critical action item is to redesign the agent's secret management strategy before proceeding further with its development.

## How to provide feedback

Argue against decisions, suggest alternatives, challenge assumptions.
Format: structured feedback with severity (Critical/Major/Minor/Suggestion).
