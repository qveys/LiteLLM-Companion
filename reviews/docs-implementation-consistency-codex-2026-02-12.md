# Docs vs Implementation Consistency Audit (Codex)

Date: 2026-02-12
Scope: `docs/*`, `README.md`, infra configs, runtime Python/JS implementation

## Findings

1. **Major** — TLS posture is contradictory across official docs.
References: `docs/product-brief.md:28`, `docs/product-brief.md:59`, `docs/stories.md:44`, `docs/architecture.md:142`.
Details: one section says insecure OTLP is acceptable for personal use, another says metrics are shipped over TLS, and Story 1 scope still states TLS + bearer token as baseline.
Impact: operators cannot infer a single deployment security contract from docs.

2. **Major** — WSL design text overstates implemented behavior.
References: `docs/architecture.md:72`, `docs/architecture.md:137`, `src/ai_cost_observer/detectors/wsl.py:54`.
Details: architecture claims WSL shell history reading via `\\wsl$` path; implementation currently scans `ps aux` only.
Impact: feature expectations and observability claims are inflated in design docs.

3. **Major** — README config path is macOS/Linux-centric, not Windows-accurate.
References: `README.md:59`, `src/ai_cost_observer/config.py:16`, `src/ai_cost_observer/config.py:18`.
Details: README instructs `~/.config/ai-cost-observer/config.yaml`; Windows implementation default is `%LOCALAPPDATA%\\ai-cost-observer\\config.yaml`.
Impact: Windows users may configure the wrong file and observe unexpected defaults.

4. **Major** — README troubleshooting command uses HTTPS for OTLP HTTP endpoint that is configured as plain HTTP.
References: `README.md:212`, `infra/otel-collector-config.yaml:13`.
Details: collector receives OTLP HTTP on `4318` with no TLS configuration in this stack.
Impact: troubleshooting guidance can fail even when deployment is healthy.

5. **Minor** — README test command references a non-existent test file.
References: `README.md:247`, `tests/test_story_3_review.py:1`.
Details: `tests/test_desktop.py` does not exist in current tree.
Impact: onboarding/dev workflow friction.

6. **Minor** — Story 2 file list is historically stale against current repository content.
References: `docs/stories.md:80`, `src/ai_cost_observer/detectors/desktop.py:1`, `src/ai_cost_observer/server/http_receiver.py:1`.
Details: Story 2 still mentions "empty `__init__.py`" subpackages, while subpackages now contain implemented modules.
Impact: low, but can confuse readers using `docs/stories.md` as current architecture index.

## Conclusion

Documentation quality is high overall, but several high-importance inconsistencies remain around transport security and platform behavior. These should be corrected before using docs as operational reference for new setups.

## Suggested doc patch order

1. Normalize TLS/insecure policy wording across `product-brief`, `architecture`, and `stories`.
2. Update WSL architecture section to match actual implementation scope.
3. Correct README Windows config path and OTLP troubleshooting command.
4. Refresh stale Story 2 historical notes and README test examples.
