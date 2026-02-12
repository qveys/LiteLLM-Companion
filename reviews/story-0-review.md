# Story 0 Review Brief: Design Artifacts

## What was built

- `docs/product-brief.md` — Problem statement, target user (personal developer), MVP scope (3 detection sources + centralized VPS backend), success metrics (< 5% CPU, < 200MB RAM), constraints (privacy-first, non-invasive).
- `docs/architecture.md` — Full system design: ASCII data flow diagram (workstation agents → OTLP gRPC + TLS → VPS OTel Collector → Prometheus → Grafana), module responsibility table (12 modules), OTel metric naming convention table (12 metrics with Prometheus name mapping), cross-platform strategy matrix, security model, threading model, error handling philosophy.
- `docs/stories.md` — 9 stories (0-8) with scope, files, acceptance criteria, dependencies, and status tracking. Overview table for quick scanning.

**Key design decisions:**
1. Centralized VPS (Dokploy) instead of local Docker stack — unified view across devices, no local Docker needed
2. TLS + bearer token auth on OTel Collector — prevents unauthorized ingestion
3. `host.name` resource attribute on all metrics — enables per-device filtering in Grafana
4. BMAD-inspired methodology — versioned design docs as persistent context for multi-session development

## Acceptance criteria results

- [x] `docs/product-brief.md` exists with problem statement, MVP features list, and measurable success criteria — **PASS**
- [x] `docs/architecture.md` exists with data flow diagram (text), module responsibilities, and OTel metric naming table — **PASS**
- [x] `docs/stories.md` exists with all stories, numbered, with status field (Pending/In Progress/Done) — **PASS**

## Review questions

1. **Architecture**: Is the centralized VPS-only approach correct, or should we add a local fallback for edge cases (e.g., VPN blocking, VPS downtime)?
2. **Metric naming**: The OTel → Prometheus name mapping assumes `resource_to_telemetry_conversion: true` in the collector config. Is this the right approach vs. using `target_info` metrics?
3. **Security**: Is bearer token auth sufficient for a personal project, or should we consider mTLS (mutual TLS) for stronger authentication?
4. **Cross-platform**: The Windows process names (`.exe` suffix) are assumed. Should we verify actual process names on a Windows machine before hardcoding in `ai_config.yaml`?
5. **Metric cardinality**: With `host.name`, `app.name`, `ai.domain`, `browser.name`, `usage.source` labels, could we hit Prometheus cardinality issues? The total unique label combinations should be < 500 for a personal setup, but worth validating.
6. **Cost estimation model**: We use fixed `cost_per_hour` rates from YAML config. Is this a useful abstraction, or should we offer more granular models (e.g., token-based estimates)?

## Conclusions (Codex Review)

### Findings by severity

1. **Critical — TLS/security contradiction across design artifacts**
   - The docs require OTLP over TLS, but Story 2 acceptance criteria validate gRPC with `insecure` mode.
   - References: `docs/product-brief.md` (OTLP TLS requirement), `docs/architecture.md` (OTLP gRPC + TLS), `docs/stories.md` (Story 2 insecure criterion).
   - Risk: bearer token exposure if traffic crosses untrusted networks.

2. **Major — Metric naming contract mismatch**
   - Architecture expects prefixed Prometheus names (e.g., `ai_cost_observer_ai_app_running`), while story acceptance criteria and prior review notes use short names like `ai_app_running`.
   - References: `docs/architecture.md` metric naming table, `docs/stories.md` Story 3/5 criteria, `reviews/story-2-review.md`.
   - Risk: false negatives in verification and broken dashboard queries.

3. **Major — Design-vs-implementation ambiguity**
   - Story 0 is design-only, but architecture text can be read as already implemented runtime behavior (threads/modules), which may cause planning confusion.
   - References: `docs/stories.md` (Story 0 scope), `docs/architecture.md` (threading/module responsibility sections).
   - Risk: reviewers and implementers may assume delivered behavior that is still pending.

4. **Minor — OTLP auth acceptance test wording is protocol-ambiguous**
   - Criteria mention HTTP 401 while the primary transport is OTLP gRPC.
   - References: `docs/stories.md` Story 1 acceptance criteria.
   - Risk: inconsistent QA outcomes depending on transport path used for testing.

5. **Suggestion — Add explicit cardinality budget and guardrail**
   - Keep the current label model, but define a concrete max-series target and a simple check procedure.
   - References: `docs/architecture.md` metric labels, review question #5 above.

### Recommended actions (priority order)

1. **Unify transport security policy**: choose one truth for MVP (`TLS required` vs `insecure allowed for bootstrap`) and update all docs accordingly.
2. **Lock a single Prometheus naming source of truth**: capture real scraped names from collector output and align Story acceptance criteria + dashboard specs.
3. **Mark architecture sections explicitly as `Target Design` where not yet implemented** to avoid scope drift and review ambiguity.
4. **Clarify auth tests per protocol**: add separate acceptance checks for OTLP gRPC and OTLP HTTP auth behavior.

## Gemini Review Verification

All findings presented in the `Conclusions (Codex Review)` section have been programmatically and manually verified against the design artifacts (`docs/architecture.md`, `docs/product-brief.md`, `docs/stories.md`).

The conclusions are **accurate and confirmed**. The identified contradictions represent real risks to the project's implementation and testing phases. The recommended actions are appropriate and should be prioritized to synchronize the design documents before proceeding with further implementation stories.

This verification completes the review for Story 0.

## Code excerpts for review

No code written in this story — design documents only. See:
- `docs/product-brief.md` for scope and constraints
- `docs/architecture.md` for technical design
- `docs/stories.md` for implementation plan

## How to provide feedback

Argue against decisions, suggest alternatives, challenge assumptions.
Format: structured feedback with severity (Critical/Major/Minor/Suggestion).

Focus areas:
- **Codex**: Are the module boundaries clean? Is the threading model sound? Any Python anti-patterns in the proposed design?
- **Gemini**: Is the centralized VPS architecture optimal? Are there simpler alternatives for OTLP auth? Is the metric naming convention aligned with OTel semantic conventions?
