# Roadmap V0 → V1

## V0 — Accompli

### Infrastructure
- [x] Repo GitHub structure (14 commits, 54 labels, 21 issues)
- [x] Tag v0.1.0
- [x] CI/CD GitHub Actions (lint + test + coverage)
- [x] Docker Compose local dev

### Bugs corriges (21/21)
- [x] 3 critiques (Codex double-counting, Claude offsets, Histogram→Gauge)
- [x] 7 high (ObservableGauge, free_port, metric_expiration, cache tokens, Chrome events, URL matching, cc pattern)
- [x] 6 medium (session duration, IDE plugin flag, cli.category, deep merge, WSL linux keys, HTTP limits)
- [x] 3 low (encryption key, cpu_percent priming, _total suffix)
- [x] #44 WSL ObservableGauge `.add()` incompatibilite (PR #62)
- [x] #45 HTTP tokens fallback cost metric manquant (PR #61)

### Validation
- [x] 9/9 endpoints valides
- [x] 4 dashboards Grafana re-valides (16 metriques alignees)
- [x] 370 tests (0 echecs), coverage 80%
- [x] ruff lint 0 erreurs

### PRs mergees
| PR | Titre |
|----|-------|
| #43 | fix: 10 critical/high bugs |
| #46 | docs: 9 endpoint validation reports |
| #47 | feat: CI/CD + 9 medium/low fixes |
| #48 | fix(detection): exe path matching + 12 detection bugs |
| #61 | fix(http): fallback cost estimation for token events |
| #62 | fix(wsl): align WSL detector with ObservableGauge pattern |
| #64 | chore(lint): ruff auto-fix + coverage config |

---

## V1 (MVP)

### Fonctionnalites
- [ ] Integration LiteLLM (details a definir avec l'utilisateur)
- [ ] Documentation utilisateur (README, guides d'installation)
- [ ] Support multi-utilisateurs (si pertinent avec LiteLLM)

### Qualite
- [ ] Couverture de tests > 90%
- [ ] Tests d'integration avec OTel Collector en conteneur
- [ ] Pipeline end-to-end: detector → TelemetryManager → assertions sur les metrics

### Infra
- [ ] GitHub Release automatique sur tag
- [ ] PyPI publish (si open-source)
- [ ] Docker image pour l'agent Python
- [ ] Alerting Grafana (seuils de cout)

### Securite
- [ ] Audit des dependances (dependabot ou renovate)
- [ ] PROMPT_DB_KEY obligatoire en production
- [ ] Rate limiting configurable (pas hardcode)
- [ ] HTTPS pour le HTTP receiver (meme en localhost)

---

## Notes
- La Phase 5 (brainstorming multi-modeles) est reportee — sera plus pertinente quand les besoins d'integration LiteLLM seront clairs
- Le projet va se greffer sur BerriAI/litellm (Python SDK/AI Gateway, 35k+ stars) — les details d'integration viendront de l'utilisateur
