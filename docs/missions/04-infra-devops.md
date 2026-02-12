# Mission: Infra & DevOps — CI/CD, Docker, Dashboards

> **Reference obligatoire**: Lire [docs/context.md](../context.md) AVANT de commencer.

---

## Identite

- **Role**: Team Lead
- **Phase**: 3 (bloquee par Phase 1, parallele avec Phase 2)
- **Worktree**: A creer dans `/Users/qveys/Git/opentelemetry-wt/phase3-infra-devops/`
- **Branche**: `phase3/infra-devops`

## Objectif

Mettre en place l'infrastructure de developpement (CI/CD, Docker local) et corriger les bugs medium/low restants lies a l'infra et aux dashboards.

## Contexte specifique

### Sous-taches

**A. GitHub Actions CI/CD**
Creer `.github/workflows/ci.yml` avec:
- Trigger: push + PR sur main
- Jobs:
  1. `lint`: `uv sync --extra dev && uv run ruff check src/`
  2. `test`: `uv sync --extra dev && uv run python -m pytest`
  3. `commit-check`: verifier la convention de commit (emoji + conventional)
- Matrix: Python 3.12 (macOS + Ubuntu)

**B. Docker Compose pour dev local**
- Bug #18: Les volume mounts utilisent `../files/` (convention Dokploy)
- Fix: Creer un `docker-compose.local.yml` override OU modifier les paths
- Tester que `cd infra && docker compose up -d` fonctionne

**C. Corriger les dashboards Grafana**
- Les panels CPU/Memory devraient fonctionner apres le fix C3 (Phase 1)
- Verifier que les PromQL queries sont correctes
- Verifier que tous les panels affichent des donnees

**D. Bugs medium/low restants**
| # | Bug | Fichier |
|---|-----|---------|
| 11 | Session duration +300s | browser_history.py:257-262 |
| 12 | JetBrains/VS Code faux positifs | ai_config.yaml:38-48 |
| 13 | Missing cli.category | shell_history.py:127-129 |
| 14 | Config shallow merge | config.py:111-115 |
| 15 | WSL "macos" keys | wsl.py:76 |
| 16 | HTTP receiver no auth/limits | http_receiver.py:24-167 |
| 17 | Weak encryption | prompt_db.py:103-104 |
| 19 | cpu_percent returns 0 | desktop.py:97 |
| 20 | _total suffix risk | telemetry.py:79-82 |

## Demarche

1. Creer le worktree: `git worktree add ../opentelemetry-wt/phase3-infra-devops -b phase3/infra-devops`
2. Paralleliser les sous-taches:
   - Agent A: GitHub Actions CI/CD
   - Agent B: Docker Compose local
   - Agent C: Bugs medium (11-16)
   - Agent D: Bugs low (17-20)
3. Verifier chaque fix avec pytest + ruff
4. Creer la PR vers main

## Resultats attendus

- [ ] `.github/workflows/ci.yml` fonctionnel
- [ ] Docker Compose local fonctionnel
- [ ] Dashboards Grafana verifies
- [ ] Bugs medium/low corriges
- [ ] PR creee vers main

## Definition of Done

- [ ] GitHub Actions CI passe (lint + test)
- [ ] `cd infra && docker compose up -d` fonctionne localement
- [ ] `uv run python -m pytest` passe
- [ ] `uv run ruff check src/` clean
- [ ] Issues GitHub fermees

## Capacites Team Lead

> Tu ES un team lead. Tu coordonnes, tu ne fais PAS tout seul.

### Outils a ta disposition:
- `TeamCreate`, `Task`, `TaskCreate`, `TaskUpdate`, `SendMessage`, `TeamDelete`

### Strategie recommandee:
- Agent A: CI/CD -> `general-purpose`
- Agent B: Docker -> `general-purpose`
- Agent C: Bugs medium -> `general-purpose`
- Agent D: Bugs low -> `general-purpose`

## Journal de bord

(A remplir pendant l'execution)

---

## ════════════════════════════════════════════════════════════
## ZONE DE RESULTATS — SYNTHESE FINALE
## ════════════════════════════════════════════════════════════

> Seul le contenu ci-dessous sera lu par le consolidateur.

### Statut: [REUSSI | ECHOUE | PARTIEL]

### Resultats cles:
- CI/CD: OK/NOK
- Docker local: OK/NOK
- Dashboards: OK/NOK
- Bugs corriges: /9
- PR: [lien]

### Problemes non resolus:
- ...

### Recommandations:
- ...
