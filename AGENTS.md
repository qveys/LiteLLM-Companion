# Repository Guidelines

## Project Structure & Module Organization
Core application code lives in `src/ai_cost_observer/`:
- `detectors/` for desktop, browser, CLI, WSL, and token detection logic
- `server/` for the local HTTP receiver
- `storage/` for persistence (for example prompt DB)
- `data/ai_config.yaml` as the canonical AI domains/tools catalog

Operational assets are split by concern:
- `tests/` (unit/regression suites, including `tests/detectors/`)
- `chrome-extension/` (Manifest V3 extension: `background.js`, `popup.js`, `options.js`)
- `infra/` (Prometheus, OTel Collector, Grafana provisioning and dashboards)
- `service/` (macOS launchd and Windows Task Scheduler installers)

## Build, Test, and Development Commands
- `uv sync` — install project and dev dependencies from lockfile.
- `uv run python -m ai_cost_observer --debug` — run agent with verbose logs.
- `PYTHONPATH=src .venv/bin/pytest -q` — run all Python tests.
- `PYTHONPATH=src .venv/bin/pytest -q tests/test_grafana_value_integrity.py` — run a focused test file.
- `PYTHONPATH=src .venv/bin/ruff check src tests` — lint Python code.
- `cd infra && docker compose up -d` — start observability stack locally/VPS.

## Coding Style & Naming Conventions
Python style is enforced by Ruff (`line-length = 100`, rules `E,F,I,N,W` in `pyproject.toml`).
- Use 4-space indentation.
- Use `snake_case` for functions/modules, `PascalCase` for classes, and explicit type hints on new/changed code.
- Keep constants uppercase (for example `AGENT_URL`, `EXPORT_INTERVAL_SECONDS`).
JavaScript in `chrome-extension/` should use `camelCase` for functions and `UPPER_SNAKE_CASE` for constants.

## Testing Guidelines
Use `pytest` + `pytest-mock`. Name files `test_*.py` and keep detector-specific tests under `tests/detectors/`.
When changing metrics, dashboards, or extension export logic, add regression tests that validate value integrity (not only JSON syntax).
Prefer small deterministic tests with explicit expected metric values.

## Commit & Pull Request Guidelines
`main` currently has no commit history; adopt Conventional Commits:
- `feat(scope): ...`
- `fix(scope): ...`
- `test(scope): ...`
- `docs(scope): ...`

PRs should include:
- a clear problem statement and impacted paths
- test evidence (exact commands run)
- screenshots for Grafana/dashboard UI changes
- config/security notes when touching tokens, endpoints, or auth flow.

## Security & Configuration Tips
Never commit secrets (`OTEL_BEARER_TOKEN`, Grafana admin passwords). Use environment variables or local config files under `~/.config/ai-cost-observer/`.
Keep the local receiver bound to `127.0.0.1` unless explicitly hardening network exposure.
