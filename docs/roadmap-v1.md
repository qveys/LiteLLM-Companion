# Roadmap V0 → V1

## V0 (actuel) — Accompli

### Infrastructure
- [x] Repo GitHub structure (14 commits, 54 labels, 21 issues)
- [x] Tag v0.1.0
- [x] CI/CD GitHub Actions (lint + test)
- [x] Docker Compose local dev

### Bugs corriges (19/21)
- [x] 3 critiques (Codex double-counting, Claude offsets, Histogram→Gauge)
- [x] 7 high (ObservableGauge, free_port, metric_expiration, cache tokens, Chrome events, URL matching, cc pattern)
- [x] 6 medium (session duration, IDE plugin flag, cli.category, deep merge, WSL linux keys, HTTP limits)
- [x] 3 low (encryption key, cpu_percent priming, _total suffix)

### Validation
- [x] 7/9 endpoints valides
- [x] 336 tests (0 echecs)
- [x] Rapport de validation detaille

---

## V0.x (prochaines etapes immediates)

### P0 — Bugs restants
- [ ] **#44** WSL detector ObservableGauge `.add()` incompatibilite (High)
  - Effort: Small — aligner wsl.py sur le pattern snapshot de desktop.py/cli.py
- [ ] **#45** HTTP tokens fallback cost metric manquant (Medium)
  - Effort: Small — ajouter `estimate_cost()` dans le path fallback

### P1 — Validation Grafana
- [ ] Re-valider les 4 dashboards apres les changements de metriques
  - `ai.app.cpu.usage` et `ai.app.memory.usage` : Histogram → Gauge
  - `ai.tokens.*_total` → `ai.tokens.*` (Prometheus names inchanges)
  - `ai.app.running` et `ai.cli.running` : UpDownCounter → ObservableGauge
- [ ] Mettre a jour les panels si necessaire

### P2 — Tests d'integration
- [ ] Tests sans mocks pour les endpoints critiques (WSL, HTTP tokens)
- [ ] Pipeline end-to-end: detector → TelemetryManager → assertions sur les metrics

---

## V1 (MVP)

### Fonctionnalites
- [ ] Integration LiteLLM (details a definir avec l'utilisateur)
- [ ] Documentation utilisateur (README, guides d'installation)
- [ ] Support multi-utilisateurs (si pertinent avec LiteLLM)

### Qualite
- [ ] Couverture de tests > 90%
- [ ] `ruff format` global (fixer les 6 E501 restants)
- [ ] Tests d'integration avec OTel Collector en conteneur
- [ ] Monitoring des dashboards en CI (screenshot comparison?)

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
