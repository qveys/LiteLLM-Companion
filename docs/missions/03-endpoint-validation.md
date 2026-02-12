# Mission: Endpoint Validation — Valider les 9 sources de donnees

> **Reference obligatoire**: Lire [docs/context.md](../context.md) AVANT de commencer.

---

## Identite

- **Role**: Team Lead
- **Phase**: 2 (bloquee par Phase 1)
- **Worktree**: A creer dans `/Users/qveys/Git/opentelemetry-wt/phase2-endpoint-validation/`
- **Branche**: `phase2/endpoint-validation`

## Objectif

Valider individuellement chaque source de donnees (detecteur/endpoint) du pipeline. Pour chaque endpoint: verifier que le code est correct, que les donnees emises sont de qualite, et que les tests couvrent les cas importants. Verdict: VALIDE ou INVALIDE.

## Contexte specifique

Apres la Phase 1 (Data Integrity), les bugs critiques et high sont corriges. Cette phase valide que chaque endpoint fonctionne correctement de bout en bout.

### Les 9 endpoints a valider

| # | Endpoint | Fichier principal | Metriques emises | Tests existants |
|---|----------|-------------------|------------------|-----------------|
| 1 | Desktop apps | `detectors/desktop.py` | ai.app.running, .active.duration, .cpu.usage, .memory.usage, .estimated.cost | test_desktop.py, test_desktop_extended.py |
| 2 | CLI processes | `detectors/cli.py` | ai.cli.running, .active.duration, .estimated.cost | test_cli.py, test_cli_extended.py |
| 3 | Browser history | `detectors/browser_history.py` | ai.browser.domain.active.duration, .visit.count, .estimated.cost | test_browser_history.py, test_story_4_review.py |
| 4 | Shell history | `detectors/shell_history.py` | ai.cli.command.count | test_shell_history.py, test_shell_history_extended.py |
| 5 | Token tracker (Claude Code) | `detectors/token_tracker.py` (JSONL) | ai.tokens.input_total, .output_total, .cost_usd_total, ai.prompt.count_total | test_token_tracker.py |
| 6 | Token tracker (Codex) | `detectors/token_tracker.py` (SQLite) | memes que #5 | test_token_tracker.py |
| 7 | HTTP receiver (browser) | `server/http_receiver.py` `/metrics/browser` | ai.browser.domain.* | test_http_receiver_values.py |
| 8 | HTTP receiver (tokens) | `server/http_receiver.py` `/api/tokens` | ai.tokens.* | test_http_tokens.py |
| 9 | WSL detector | `detectors/wsl.py` | ai.cli.running | test_wsl_detector.py, test_wsl_extended.py |

### Protocole de validation par endpoint

Pour CHAQUE endpoint, l'agent dedie doit:

1. **Lire le code source** du detecteur/endpoint
2. **Lire les tests existants** qui le couvrent
3. **Executer les tests**: `uv run python -m pytest tests/test_<fichier>.py -v`
4. **Verifier la qualite des donnees emises:**
   - Noms de metriques corrects (namespace `ai.*`)
   - Types d'instruments corrects (Counter, Gauge, Histogram)
   - Attributs/labels complets et consistants
   - Unites correctes
   - Pas de double-comptage
   - Incremental (pas de re-traitement de donnees deja comptees)
5. **Identifier les gaps de test** — cas non couverts, edge cases
6. **Produire un verdict:**
   - **VALIDE** — le code est correct, les donnees sont fiables, tests suffisants
   - **INVALIDE** — probleme identifie, detailler et ouvrir une issue GitHub

### Format du rapport par endpoint

```markdown
## Endpoint: [nom]
### Fichiers analyses: [liste]
### Tests executes: X/X passent
### Qualite des donnees:
- Noms: OK/NOK (detail)
- Types: OK/NOK (detail)
- Attributs: OK/NOK (detail)
- Incremental: OK/NOK (detail)
### Gaps de test identifies: [liste]
### Verdict: VALIDE / INVALIDE
### Si INVALIDE — Issue: [titre + description]
```

## Demarche

1. Creer le worktree: `git worktree add ../opentelemetry-wt/phase2-endpoint-validation -b phase2/endpoint-validation`
2. Spawner 1 agent par endpoint (ou grouper par 3)
3. Chaque agent suit le protocole de validation ci-dessus
4. Collecter les 9 rapports
5. Creer les issues GitHub pour les endpoints INVALIDE
6. Sauvegarder les rapports dans `docs/validation/`

## Resultats attendus

- [ ] 9 rapports de validation (1 par endpoint)
- [ ] Rapports sauvegardes dans `docs/validation/`
- [ ] Issues GitHub creees pour les endpoints INVALIDE
- [ ] Aucune regression de tests

## Definition of Done

- [ ] 9 endpoints ont un verdict (VALIDE ou INVALIDE)
- [ ] Chaque endpoint INVALIDE a une issue GitHub associee
- [ ] `uv run python -m pytest` passe
- [ ] Rapports dans `docs/validation/`

## Capacites Team Lead

> Tu ES un team lead. Tu coordonnes, tu ne fais PAS tout seul.

### Outils a ta disposition:
- `TeamCreate`, `Task`, `TaskCreate`, `TaskUpdate`, `SendMessage`, `TeamDelete`

### Strategie recommandee:
- Vague 1 (3 agents): Desktop (#1), CLI (#2), Browser History (#3)
- Vague 2 (3 agents): Shell History (#4), Token Tracker Claude (#5), Token Tracker Codex (#6)
- Vague 3 (3 agents): HTTP Browser (#7), HTTP Tokens (#8), WSL (#9)

### Types de sous-agents:
- Validation (lecture + tests) -> `general-purpose` (besoin d'executer pytest)

## Journal de bord

(A remplir pendant l'execution)

---

## ════════════════════════════════════════════════════════════
## ZONE DE RESULTATS — SYNTHESE FINALE
## ════════════════════════════════════════════════════════════

> Seul le contenu ci-dessous sera lu par le consolidateur.

### Statut: REUSSI

### Resultats cles:
- Endpoints VALIDES: 7/9 (Desktop, CLI, Browser History, Shell History, Token Claude, Token Codex, HTTP Browser)
- Endpoints INVALIDES: 2/9 (HTTP Tokens #45, WSL #44)
- Tests executes: 314/314 passent
- Gaps identifies: 2 bugs masques par les mocks
- PR: https://github.com/qveys/LiteLLM-Companion/pull/46

### Problemes non resolus:
- #44: WSL detector appelle `.add()` sur ObservableGauge (API incompatible apres fix H1)
- #45: HTTP /api/tokens fallback ne record pas `tokens_cost_usd_total` quand token_tracker est None

### Recommandations:
- Les 2 bugs invalides sont masques par les mocks dans les tests — un test d'integration avec le vrai TelemetryManager les aurait detectes
- Ajouter des tests d'integration pour les endpoints critiques
