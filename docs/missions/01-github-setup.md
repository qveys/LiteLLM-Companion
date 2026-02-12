# Mission: GitHub Setup — Publication V0

> **Reference obligatoire**: Lire [docs/context.md](../context.md) AVANT de commencer.

---

## Identite

- **Role**: Team Lead
- **Phase**: 0
- **Worktree**: `/Users/qveys/Git/opentelemetry` (main, directement)
- **Branche**: `main`

## Objectif

Publier le projet AI Cost Observer sur GitHub comme V0. Creer des commits structures par composant, les 21 issues de bugs identifies, et les labels.

## Contexte specifique

Le projet n'a aucun commit. Tous les fichiers sont untracked. Il faut commiter dans un ordre qui respecte les dependances entre composants (config avant telemetry, telemetry avant detectors, etc.).

Un audit complet a identifie 21 bugs repartis en 4 niveaux de severite. Chaque bug doit devenir une issue GitHub granulaire (1 bug = 1 issue, 1 seul objectif).

### Convention de commit
Emoji + Conventional Commits: `<emoji> <type>(scope): description`
Exemples: `feat:`, `fix:`, `docs:`, `test:`, `chore:`, `ci:`

### Ordre des commits (dependances respectees)

| # | Scope | Contenu | Message |
|---|-------|---------|---------|
| 1 | project | pyproject.toml, .python-version, .gitignore, uv.lock | `🎉 feat(project): initial project setup with dependencies` |
| 2 | docs | CLAUDE.md, README.md, docs/ | `📝 docs: add project documentation, architecture and stories` |
| 3 | config | __init__.py, config.py, data/ai_config.yaml | `✨ feat(config): add configuration system with AI tool definitions` |
| 4 | telemetry | telemetry.py | `✨ feat(telemetry): add OTel SDK setup with 16 metric instruments` |
| 5 | platform | platform/, detectors/active_window.py | `✨ feat(platform): add cross-platform active window detection` |
| 6 | detectors | detectors/ (desktop, cli, browser_history, shell_history, token_tracker, wsl) | `✨ feat(detectors): add 7 AI usage detectors` |
| 7 | server | server/http_receiver.py | `✨ feat(server): add HTTP receiver for Chrome extension` |
| 8 | storage | storage/prompt_db.py | `✨ feat(storage): add encrypted prompt storage` |
| 9 | main | main.py | `✨ feat(core): add main orchestrator with threading model` |
| 10 | infra | infra/ | `✨ feat(infra): add OTel Collector + Prometheus + Grafana stack` |
| 11 | extension | chrome-extension/ | `✨ feat(extension): add Chrome extension for real-time browser tracking` |
| 12 | service | service/ | `✨ feat(service): add daemon install scripts for macOS and Windows` |
| 13 | tests | tests/ | `✅ test: add 281 tests covering all detectors and endpoints` |
| 14 | misc | reviews/, prompt-agent-ai-cost-complet.md, images, .vibe/, .playwright-mcp/ | `📦 chore: add review notes and project assets` |

### Labels a creer

**Reproduire la structure du repo `qveys/myulis-frontend-vue3`** en l'adaptant a ce projet.
Utiliser `gh label list --repo qveys/myulis-frontend-vue3 --limit 50 --json name,color,description`
comme reference, puis adapter/completer avec les labels specifiques ci-dessous.

**Labels a reprendre tels quels (meme nom, couleur, description):**
- Toute la categorie `🤖 AC:` (Auto-Claude)
- Toute la categorie `🚦 Status:` (In Progress, Open, Ready, Review Needed, Blocked, Fixed, etc.)
- Toute la categorie `🔥 Priority:` (Critical, High, Medium, Low)
- Toute la categorie `⏱️ Effort:` (Small, Medium, Large, X-Large)
- Toute la categorie `🧷 Meta:` (Good First Issue, Help Wanted, Needs Discussion)
- Types generiques: `🐞 Type: Bug`, `✨ Type: Enhancement`, `🚀 Type: Feature`, `📚 Type: Documentation`, `🧪 Type: Test`, `🧼 Type: Refactor`, `🔒 Type: Security`, `⚡ Type: Performance`, `🧹 Type: Chore`, `🏗️ Type: Build`, `📦 Type: Dependency`

**Labels a adapter (remplacer Area: Frontend/Backend par nos composants):**
- `🧩 Area: Detector` (couleur: 1d76db) — Changes in src/ai_cost_observer/detectors/
- `🧩 Area: Telemetry` (couleur: 1d76db) — OTel SDK, metric instruments
- `🧩 Area: Infra` (couleur: 1d76db) — OTel Collector, Prometheus, Grafana, Docker
- `🧩 Area: Extension` (couleur: 1d76db) — Chrome extension
- `🧩 Area: Server` (couleur: 1d76db) — HTTP receiver (Flask)
- `🧩 Area: Config` (couleur: 1d76db) — Configuration system
- `🧩 Area: Core` (couleur: 1d76db) — main.py, orchestration
- `🧩 Area: CI` (couleur: ededed) — (garder tel quel)

**Labels specifiques a ajouter:**
- `🎯 Detector: Desktop` (couleur: 26a69a) — desktop.py specific
- `🎯 Detector: CLI` (couleur: 26a69a) — cli.py specific
- `🎯 Detector: Browser History` (couleur: 26a69a) — browser_history.py specific
- `🎯 Detector: Shell History` (couleur: 26a69a) — shell_history.py specific
- `🎯 Detector: Token Tracker` (couleur: 26a69a) — token_tracker.py specific
- `🎯 Detector: WSL` (couleur: 26a69a) — wsl.py specific
- `🗺️ Roadmap: Phase 1` (couleur: d1c4e9) — (garder tel quel)
- `🗺️ Roadmap: Phase 2` (couleur: 9575cd) — (garder tel quel)

**Labels a NE PAS reprendre (non pertinents):**
- `🌐 Browser:` (Chrome, Firefox, Cross-Browser) — pas pertinent ici
- `🧱 Type: Breaking Change` — pas encore en production publique
- `🧭 Type: Migration` — pas applicable
- `❓ Type: Question` — pas necessaire

### Les 21 issues a creer

**Critical (3):**
1. Codex token scanner re-processes ALL sessions every 5-min cycle — `token_tracker.py:245-263` — Labels: `🐞 Type: Bug`, `🔥 Priority: Critical`, `🎯 Detector: Token Tracker`
2. Claude Code token tracker offsets not persisted — full re-count on restart — `token_tracker.py:85-86` — Labels: `🐞 Type: Bug`, `🔥 Priority: Critical`, `🎯 Detector: Token Tracker`
3. CPU/Memory Histogram metrics queried as Gauge — panels show NO DATA — `telemetry.py:69-70`, Overview panels 13-14 — Labels: `🐞 Type: Bug`, `🔥 Priority: Critical`, `🧩 Area: Telemetry`, `🧩 Area: Infra`

**High (7):**
4. UpDownCounter for running state drifts on crash/restart — `desktop.py:128-133`, `cli.py:140-145` — Labels: `🐞 Type: Bug`, `🔥 Priority: High`, `🧩 Area: Telemetry`, `🎯 Detector: Desktop`, `🎯 Detector: CLI`
5. `_free_port()` sends SIGKILL to arbitrary processes on port 8080 — `main.py:56-73` — Labels: `🐞 Type: Bug`, `🔥 Priority: High`, `🧩 Area: Core`
6. metric_expiration 5m < shell_history interval 3600s — causes counter resets — `otel-collector-config.yaml:33` — Labels: `🐞 Type: Bug`, `🔥 Priority: High`, `🧩 Area: Infra`
7. Token cost ignores cache tokens (cache_creation + cache_read) — `token_tracker.py:163-170` — Labels: `🐞 Type: Bug`, `🔥 Priority: High`, `🎯 Detector: Token Tracker`
8. Chrome extension loses token events when service worker suspends — `background.js:134` — Labels: `🐞 Type: Bug`, `🔥 Priority: High`, `🧩 Area: Extension`
9. Browser history domain matching uses substring — false positives — `browser_history.py:189-194` — Labels: `🐞 Type: Bug`, `🔥 Priority: High`, `🎯 Detector: Browser History`
10. Shell history pattern "cc" matches C compiler — `ai_config.yaml:232` — Labels: `🐞 Type: Bug`, `🔥 Priority: High`, `🎯 Detector: Shell History`, `🧩 Area: Config`

**Medium (6):**
11. Browser session duration adds 300s unconditionally — inflates single visits — `browser_history.py:257-262` — Labels: `🐞 Type: Bug`, `🔥 Priority: Medium`, `🎯 Detector: Browser History`
12. JetBrains/VS Code detected as AI tools without plugin check — `ai_config.yaml:38-48` — Labels: `🐞 Type: Bug`, `🔥 Priority: Medium`, `🧩 Area: Config`
13. Missing `cli.category` on `ai.cli.command.count` metric — `shell_history.py:127-129` — Labels: `🐞 Type: Bug`, `🔥 Priority: Medium`, `🎯 Detector: Shell History`, `🧩 Area: Telemetry`
14. Config shallow merge loses nested user overrides — `config.py:111-115` — Labels: `🐞 Type: Bug`, `🔥 Priority: Medium`, `🧩 Area: Config`
15. WSL detector uses "macos" process name keys for Linux — `wsl.py:76` — Labels: `🐞 Type: Bug`, `🔥 Priority: Medium`, `🎯 Detector: WSL`
16. HTTP receiver: no auth, rate limit, or payload size limit — `http_receiver.py:24-167` — Labels: `✨ Type: Enhancement`, `🔥 Priority: Medium`, `🧩 Area: Server`, `🔒 Type: Security`

**Low (4):**
17. Encryption key from guessable hostname:username — `prompt_db.py:103-104` — Labels: `✨ Type: Enhancement`, `🔥 Priority: Low`, `🔒 Type: Security`
18. Docker Compose ../files/ paths break local dev — `docker-compose.yml:7,24,38-39` — Labels: `🐞 Type: Bug`, `🔥 Priority: Low`, `🧩 Area: Infra`
19. cpu_percent(interval=0) returns 0 on first call — `desktop.py:97` — Labels: `🐞 Type: Bug`, `🔥 Priority: Low`, `🎯 Detector: Desktop`
20. Token metric _total suffix duplication risk — `telemetry.py:79-82` — Labels: `✨ Type: Enhancement`, `🔥 Priority: Low`, `🧩 Area: Telemetry`

**DevOps (1):**
21. Set up CI/CD: lint, test, conventional commit check — Labels: `✨ Type: Enhancement`, `🧩 Area: CI`, `🏗️ Type: Build`

## Demarche

1. Verifier que le repo GitHub est cree et configure (prive)
2. Ajouter le remote origin si pas fait
3. Creer les labels GitHub via `gh label create`
4. Executer les 14 commits dans l'ordre (verifier que chaque commit ne reference que des fichiers deja commites)
5. Pousser vers GitHub
6. Creer le tag v0.1.0
7. Creer les 21 issues via `gh issue create`
8. Verifier le resultat

## Resultats attendus

- [ ] 14 commits structures sur main
- [ ] 21 issues creees avec labels
- [ ] Tag v0.1.0
- [ ] Labels crees sur le repo

## Definition of Done

- [ ] `git log --oneline` montre 14 commits dans l'ordre
- [ ] `gh issue list --limit 30` montre 21 issues
- [ ] `gh label list` montre tous les labels
- [ ] `git tag` montre v0.1.0
- [ ] `uv run python -m pytest` passe (281 tests)
- [ ] Aucun fichier untracked restant (`git status` clean)

## Capacites Team Lead

> Tu ES un team lead. Tu coordonnes, tu ne fais PAS tout seul.

### Outils a ta disposition:
- `TeamCreate` — creer ta propre equipe
- `Task` avec `team_name` + `name` — spawner des sous-agents
- `TaskCreate` / `TaskUpdate` — gerer les taches
- `SendMessage` — communiquer avec tes agents
- `SendMessage(type=shutdown_request)` — arreter tes agents quand c'est fini
- `TeamDelete` — nettoyer l'equipe a la fin

### Strategie recommandee:
- Agent 1: Commits (git add + commit, sequentiel obligatoire)
- Agent 2: Labels (gh label create, parallelisable)
- Agent 3: Issues (gh issue create, parallelisable apres labels)
- Toi: Verification finale + tag

### Types de sous-agents:
- Commits/Labels/Issues -> `general-purpose` (besoin de bash)

## Journal de bord

(A remplir pendant l'execution)

---

## ════════════════════════════════════════════════════════════
## ZONE DE RESULTATS — SYNTHESE FINALE
## ════════════════════════════════════════════════════════════

> Seul le contenu ci-dessous sera lu par le consolidateur.

### Statut: REUSSI

### Resultats cles:
- Nombre de commits: 14/14
- Nombre d'issues: 21/21
- Nombre de labels: 54
- Tag v0.1.0: OUI
- Tests: 284/281 passent (3 tests supplementaires detectes)
- Git status: clean (aucun fichier untracked)
- Push: origin/main a jour

### Problemes non resolus:
- Aucun

### Recommandations:
- Le nombre de tests (284) est legerement superieur aux 281 documentes — mettre a jour docs/stories.md
- Certaines issues ont des numeros non sequentiels (#1-#37) en raison de doublons crees puis fermes pendant l'execution
