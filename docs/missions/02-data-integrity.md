# Mission: Data Integrity — Corriger les bugs critiques et high

> **Reference obligatoire**: Lire [docs/context.md](../context.md) AVANT de commencer.

---

## Identite

- **Role**: Team Lead
- **Phase**: 1 (bloquee par Phase 0)
- **Worktree**: A creer dans `/Users/qveys/Git/opentelemetry-wt/phase1-data-integrity/`
- **Branche**: `phase1/data-integrity`

## Objectif

Corriger les 10 bugs (3 critiques + 7 high) qui corrompent activement les donnees ou affectent la fiabilite du pipeline. Chaque fix doit etre couvert par un test.

## Contexte specifique

Ces bugs ont ete identifies par un audit de 5 agents independants (2 analystes + 2 reviewers + 1 comparateur). Les references fichier:ligne sont precises.

### Bugs a corriger (ordre de priorite)

**CRITICAL — Corrompent activement les donnees:**

| # | Bug | Fichier | Fix attendu |
|---|-----|---------|-------------|
| C1 | Codex scanner re-traite TOUTES les sessions a chaque cycle 5min | `token_tracker.py:245-263` | Tracker le dernier `rowid` traite, ajouter `WHERE rowid > ?` |
| C2 | Claude Code offsets en memoire seulement, re-comptage au restart | `token_tracker.py:85-86` | Persister `_file_offsets` sur disque (comme `shell_history.py:133-151`) |
| C3 | CPU/Memory definis comme Histogram, requetes comme Gauge | `telemetry.py:69-70`, `desktop.py:155,157` | Changer Histogram -> Gauge, `.record()` -> `.set()` |

**HIGH — Fiabilite et precision:**

| # | Bug | Fichier | Fix attendu |
|---|-----|---------|-------------|
| H1 | UpDownCounter drift au crash/restart | `desktop.py:128-133`, `cli.py:140-145` | Remplacer par ObservableGauge avec callback |
| H2 | `_free_port()` SIGKILL aveugle sur port 8080 | `main.py:56-73` | SIGTERM d'abord + PID file, ou SO_REUSEADDR |
| H3 | metric_expiration 5m < shell_history 3600s | `otel-collector-config.yaml:33` | Augmenter a 90m ou supprimer |
| H4 | Cache tokens ignores dans le cout | `token_tracker.py:163-170` | Integrer cache_creation (x1.25) et cache_read (x0.1) |
| H5 | Chrome ext perd token events au suspend | `background.js:134` | Persister `pendingTokenEvents` dans `chrome.storage.local` |
| H6 | Browser history substring matching | `browser_history.py:189-194` | Utiliser `urlparse` + suffix matching sur hostname |
| H7 | Pattern "cc" matche le compilateur C | `ai_config.yaml:232` | Retirer "cc" ou le rendre plus specifique |

## Demarche

1. Creer le worktree: `git worktree add ../opentelemetry-wt/phase1-data-integrity -b phase1/data-integrity`
2. Pour chaque bug (par ordre de priorite C1 -> C3 -> H1 -> H7):
   a. Lire et comprendre le code concerne
   b. Ecrire le test qui reproduit le bug (test_echoue AVANT le fix)
   c. Appliquer le fix
   d. Verifier que le test passe
   e. `uv run python -m pytest` — pas de regression
   f. `uv run ruff check src/` — lint clean
   g. Commit: `🐛 fix(scope): description`
3. Fermer les issues GitHub correspondantes (si elles existent)
4. Creer la PR vers main

## Resultats attendus

- [ ] 10 bugs corriges
- [ ] 10+ nouveaux tests couvrant les fixes
- [ ] Pas de regression sur les 281 tests existants
- [ ] PR creee vers main, prete a merger

## Definition of Done

- [ ] Chaque bug fixe est couvert par au moins 1 test specifique
- [ ] `uv run python -m pytest` passe (281 + nouveaux tests)
- [ ] `uv run ruff check src/` clean
- [ ] Aucune regression fonctionnelle
- [ ] Issues GitHub fermees avec reference au commit

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
Les bugs peuvent etre groupes par fichier/composant pour paralleliser:
- Agent A: token_tracker.py (C1, C2, H4) — 3 bugs lies au meme fichier
- Agent B: telemetry.py + desktop.py (C3, H1) — metriques/instruments
- Agent C: main.py + otel-collector (H2, H3) — infra/lifecycle
- Agent D: browser_history.py + ai_config.yaml + background.js (H5, H6, H7) — sources de donnees

**ATTENTION**: Tous les agents travaillent dans le MEME worktree.
Assigner des fichiers DIFFERENTS a chaque agent pour eviter les conflits.

### Types de sous-agents:
- Fix de bugs -> `general-purpose` (besoin d'editer + tester)

## Journal de bord

(A remplir pendant l'execution)

---

## ════════════════════════════════════════════════════════════
## ZONE DE RESULTATS — SYNTHESE FINALE
## ════════════════════════════════════════════════════════════

> Seul le contenu ci-dessous sera lu par le consolidateur.

### Statut: REUSSI

### Resultats cles:
- Bugs corriges: 10/10 (3 critical + 7 high)
- Nouveaux tests: 33
- Tests totaux: 314/314 passent
- Issues fermees: 0/10 (a fermer au merge)
- PR: https://github.com/qveys/LiteLLM-Companion/pull/43

### Detail des fixes:
- C1: Codex rowid tracking (`token_tracker.py`) — commit `d05703f`
- C2: File offsets persistes sur disque (`token_tracker.py`) — commit `3e13fe3`
- C3: Histogram → Gauge pour CPU/Memory (`telemetry.py`, `desktop.py`) — commit `96e5fd0`
- H1: UpDownCounter → ObservableGauge (`telemetry.py`, `desktop.py`, `cli.py`) — commit `7b76c88`
- H2: `_free_port()` supprime, SO_REUSEADDR suffit (`main.py`) — commit dans `96e5fd0`
- H3: metric_expiration 5m → 90m (`otel-collector-config.yaml`) — commit `b0cc62f`
- H4: Cache tokens integres dans le cout (`token_tracker.py`) — commit `fa514b8`
- H5: pendingTokenEvents persistes dans chrome.storage.local (`background.js`) — commit `43596b4`
- H6: urlparse + suffix matching (`browser_history.py`) — commit `fadea50`
- H7: Pattern "cc" supprime (`ai_config.yaml`) — commit `1038613`

### Problemes non resolus:
- 8 warnings E501 (line too long) pre-existants dans du code non modifie
- Les issues GitHub n'ont pas encore ete fermees (a faire au merge)

### Recommandations:
- Merger la PR #43 pour debloquer Phases 2 et 3
- Fermer les issues #1-#14 avec reference aux commits
- Verifier manuellement les dashboards Grafana apres merge (panels CPU/Memory)
