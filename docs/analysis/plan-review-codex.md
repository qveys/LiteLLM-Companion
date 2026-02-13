# Review du Plan — Codex
> Score: 44/100

## Modele utilise
- Codex CLI v0.99.0, model gpt-5.3-codex, reasoning effort xhigh

## Evaluation critere par critere

| # | Critere | Note | Justification |
|---|---|---:|---|
| 1 | Couverture des bugs | **9/15** | Le plan mappe plusieurs bugs vers des fixes, mais la couverture n'est pas exhaustive (apps manquantes deja identifiees) et certains fixes restent trop generiques. |
| 2 | Clarte des instructions agents | **6/15** | Les roles sont nommes, mais sans livrables precis, sans criteres d'acceptation detailles, sans snippets ni etapes exactes d'execution. |
| 3 | Gestion equipe (shutdown, dependances, parallelisme, panes) | **3/10** | Une dependance est mentionnee (agent 3 bloque), mais pas d'orchestration concrete (ordre, handoff, arret/reprise, gestion des conflits). |
| 4 | Tests (nouveaux + non-regression + execution) | **6/15** | L'intention est bonne, mais pas de matrice de tests complete, pas de seuils quantitatifs, pas de strategie claire anti-faux positifs/faux negatifs. |
| 5 | Workflow Git | **7/10** | Branch/PR/labels/issues sont presents. En revanche, conventions de commit, strategie de decoupage, checklist PR, criteres de merge insuffisamment definis. |
| 6 | Cycle de review | **4/10** | Le cycle est cite, mais manque de procedure operationnelle (triage des commentaires, SLA, regles de resolution de threads, re-test cible). |
| 7 | Risques et edge cases | **2/10** | Faible: risques techniques critiques quasi absents (proc.exe() None, AccessDenied, collisions `node`/`python`, rollback, instrumentation perf). |
| 8 | Validation terrain | **5/10** | "Validation manuelle debug" existe, mais sans protocole mesurable (jeu de scenarios reel, baseline avant/apres, metriques de precision/rappel). |
| 9 | Auto-suffisance | **2/5** | Le plan donne la direction mais pas le niveau d'execution "cle en main" (commandes exactes, DoD precis, artefacts attendus). |

**Total: 44/100**

## Comparaison avec l'auto-evaluation (60/100)

Codex est **plus severe**: **44/100 vs 60/100**.
Raison: le plan est strategique mais pas assez operable; la grille valorise l'execution detaillee, les risques, et la validation quantitative, qui sont les zones les plus faibles.

## Ameliorations concretes (pour chaque critere < 80%)

### 1. Couverture bugs (9/15)
- Ajouter une matrice exhaustive `App/Tool -> symptome -> cause racine -> fix exact -> fichier -> test`.
- Integrer explicitement les 4 apps manquantes (superwhisper, Codex Desktop, Zed, Auto-Claude).
- Definir pour chaque bug un resultat attendu mesurable (ex: "detecte en <2 scans, 0 faux positif sur 5 apps proches").

### 2. Clarte agents (6/15)
- Donner a chaque agent: fichiers cibles, commandes exactes, output attendu, Definition of Done.
- Ajouter des snippets precis (ex: structure YAML attendue, pseudo-code de fallback `name -> exe -> cmdline`).
- Definir les criteres de validation par agent avant handoff.

### 3. Gestion equipe (3/10)
- Poser un DAG d'execution: `A1 config` et `A2 engine` en parallele partiel, `A3 tests` apres merge local.
- Definir un protocole de handoff (artefacts, checklists, "ready for next agent").
- Preciser strategie de resolution de conflits git + regle d'arret/reprise (shutdown propre).

### 4. Tests (6/15)
- Creer une matrice de tests positive/negative par tier (name/exe/cmdline).
- Ajouter tests edge cases: `AccessDenied`, `exe=None`, cmdline vide/tronquee, processus generiques (`node`, `python`, `gh`).
- Ajouter un test de non-regression perf (budget scan, ex: +<5ms median) et un test quantitatif de precision.

### 5. Workflow Git (7/10)
- Imposer commits atomiques Conventional Commits par domaine (`fix(config)`, `fix(detector)`, `test(detector)`).
- Definir template PR avec checklist obligatoire (tests, risques, rollback, validation terrain).
- Lier chaque fix a une issue (`Fixes #...`) et definir labels exacts.

### 6. Cycle review (4/10)
- Definir triage standard: `blocking`, `important`, `nit`, `outdated`.
- Exiger pour chaque correction: commit SHA + reponse de thread + test relance.
- Fixer regle de sortie: tous les commentaires bloquants resolus + suite ciblee verte.

### 7. Risques/edge cases (2/10)
- Ajouter registre de risques avec mitigation et owner.
- Implementer `safe_get_exe()` et garde-fous `try/except` autour de `psutil`.
- Prevoir rollback explicite: feature flag de la detection tier2/3 + procedure revert rapide.

### 8. Validation terrain (5/10)
- Definir protocole reel avant/apres sur la machine: N scans, fenetre temporelle fixe, memes apps ouvertes.
- Mesurer precision, rappel, faux positifs, faux negatifs avec tableau de verite manuel.
- Inclure un script de validation reproductible et rapport chiffre dans PR.

### 9. Auto-suffisance (2/5)
- Transformer le plan en runbook executable (commandes shell exactes, ordre, sorties attendues).
- Ajouter les chemins de fichiers a modifier et les assertions de test minimales.
- Ajouter criteres "go/no-go" finaux.
