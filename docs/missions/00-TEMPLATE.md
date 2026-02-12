# Mission: [TITRE DE LA MISSION]

> **Reference obligatoire**: Lire [docs/context.md](../context.md) AVANT de commencer.

---

## Identite

- **Role**: [Team Lead | Sous-agent]
- **Phase**: [0-5]
- **Worktree**: [chemin du worktree assigne]
- **Branche**: [nom de la branche]

## Objectif

[Description claire et sans ambiguite de ce qui doit etre accompli.
Un seul objectif principal. Pas de sous-objectifs implicites.]

## Contexte specifique

[Informations supplementaires au context.md, specifiques a cette mission.
References aux fichiers concernes, bugs a corriger, endpoints a valider, etc.]

## Demarche

[Etapes numerotees, dans l'ordre d'execution.
Chaque etape doit etre actionnable et verifiable.]

1. ...
2. ...
3. ...

## Resultats attendus

[Liste precise de ce qui doit etre produit/modifie/cree.
Fichiers, issues GitHub, rapports, etc.]

- [ ] ...
- [ ] ...

## Definition of Done

[Criteres mesurables et verifiables. La mission n'est reussie
QUE si TOUS ces criteres sont remplis.]

- [ ] ...
- [ ] ...
- [ ] `uv run python -m pytest` passe
- [ ] `uv run ruff check src/` clean

## Capacites Team Lead

> **Section reservee aux team leads.** Supprimer si sous-agent.

Tu ES un team lead. Tu coordonnes, tu ne fais PAS tout seul.

### Outils a ta disposition:
- `TeamCreate` — creer ta propre equipe
- `Task` avec `team_name` + `name` — spawner des sous-agents
- `TaskCreate` / `TaskUpdate` — gerer les taches
- `SendMessage` — communiquer avec tes agents
- `SendMessage(type=shutdown_request)` — arreter tes agents quand c'est fini
- `TeamDelete` — nettoyer l'equipe a la fin

### Strategie de parallelisation:
- Max 3-4 sous-agents simultanes
- Spawner par vagues si > 4 sous-taches
- Types de sous-agents:
  - Lecture/analyse -> `feature-dev:code-explorer`
  - Code review -> `feature-dev:code-reviewer`
  - Ecriture de code -> `general-purpose`
  - Recherche -> `Explore`

### Protocole d'execution:
1. Creer la team (`TeamCreate`)
2. Creer toutes les tasks (`TaskCreate`)
3. Definir les dependances (`addBlockedBy`)
4. Spawner les agents par vagues
5. Collecter les rapports (via messages)
6. Consolider dans ta zone de resultats
7. Shutdown tous les agents (`SendMessage(type=shutdown_request)`)
8. `TeamDelete`

### Sous-missions:
Cree un fichier mission par sous-agent dans `docs/missions/XX-sub/`
(XX = numero de ta mission) en utilisant ce meme template.

## Journal de bord

[Consigne ici TOUTES les etapes de travail au fur et a mesure.
Chaque action, decision, resultat intermediaire, probleme rencontre.]

### [Date/Heure] — [Action]
- ...

---

## ════════════════════════════════════════════════════════════
## ZONE DE RESULTATS — SYNTHESE FINALE
## ════════════════════════════════════════════════════════════

> **ATTENTION**: Seul le contenu de cette zone sera pris en compte
> par l'agent consolidateur. Tout ce qui est au-dessus sert de
> journal de bord mais ne sera PAS lu lors de la consolidation.
>
> Cette zone doit contenir UNIQUEMENT l'essentiel:
> - Statut: REUSSI / ECHOUE / PARTIEL
> - Resultats cles (chiffres, fichiers modifies, issues creees)
> - Problemes non resolus
> - Recommandations pour la suite

### Statut: [REUSSI | ECHOUE | PARTIEL]

### Resultats cles:
- ...

### Problemes non resolus:
- ...

### Recommandations:
- ...
