# Review du Plan: Hierarchie Documentaire + Brainstorming Multi-Modeles

> Review produite par l'agent vibe-reviewer (Mistral CLI indisponible en mode non-interactif — review realisee par analyse directe)

---

## FORCES

1. **Architecture pyramidale bien pensee.** La hierarchie 2 niveaux (Dispatcher → Team Leads → sous-agents) avec consolidation pyramidale via zones balisees est un pattern eprouve. Ca evite le chaos d'une coordination plate avec 15+ agents.

2. **Separation claire des responsabilites.** Les 5 team leads couvrent des domaines orthogonaux: GitHub Setup, Data Integrity, Endpoint Validation, Infra/DevOps, Consolidation. Pas de chevauchement evident.

3. **Template uniforme (00-TEMPLATE.md).** Imposer une structure commune a toutes les missions reduit l'ambiguite et permet au consolidateur (TL5) de parser mecaniquement les outputs.

4. **Capacites team lead explicites.** Le plan documente precisement les outils disponibles (TeamCreate, TaskCreate, SendMessage, etc.) et le protocole d'execution. Ca reduit le risque d'agents "perdus" qui ne savent pas quoi faire.

5. **Parallelisation maitrisee.** La limite de 3-4 sous-agents simultanes avec spawning par vagues est pragmatique — ca evite la saturation de contexte et les couts explosifs.

6. **Brainstorming multi-modeles.** Confronter Gemini, Codex et Vibe sur les memes sujets est une bonne strategie pour eviter les biais d'un seul modele. La phase de cross-review ajoute de la valeur.

7. **docs/context.md comme "bible".** Un document de reference unique pour tous les agents est essentiel pour la coherence. Bien place en etape 1.

---

## RISQUES

### R1 — Explosion des couts API (CRITIQUE)
- 5 team leads + ~15-20 sous-agents + 12 executions brainstorming = potentiellement 30+ sessions LLM concurrentes
- Aucun budget global defini, pas de circuit breaker
- Un team lead qui spawne trop de sous-agents peut bruler le budget avant que les autres commencent

### R2 — Fenetre de contexte des sous-agents
- Les sous-agents spawnes via `Task` ont un contexte frais — ils ne voient PAS le contexte du team lead
- Si le fichier mission est trop long ou mal structure, le sous-agent peut ignorer des instructions critiques
- Risque de "drift" ou les sous-agents interpretent differemment la meme mission

### R3 — Race conditions sur les fichiers
- Plusieurs agents ecrivent dans `docs/missions/` et `docs/brainstorming/` en parallele
- Pas de mecanisme de lock ou de coordination git (qui commit quoi, quand)
- Le consolidateur (TL5) peut lire des zones balisees incompletes si les team leads n'ont pas fini

### R4 — Dependance fragile au Workstream B
- Les 12 executions brainstorming dependent de 3 CLIs externes (Gemini, Codex, Vibe)
- Vibe ne fonctionne pas en mode non-interactif pipe (confirme par cette session)
- Si 1/3 des outils echoue, le brainstorming est desequilibre

### R5 — Consolidation TL5 prematuree
- L'ordre d'execution ne definit pas quand TL5 peut commencer
- Si TL5 demarre avant que TL1-TL4 aient fini, les rapports seront incomplets
- Pas de signal explicite "j'ai fini" entre team leads

### R6 — Complexite operationnelle
- Le plan genere potentiellement 30+ fichiers dans docs/
- Le dispatcher doit gerer 5 equipes + 12 executions brainstorming + la synthese
- Risque de surcharge cognitive pour le dispatcher humain

---

## LACUNES

### L1 — Pas de criteres de succes mesurables
- Quand est-ce qu'une mission est "terminee"?
- Pas de definition de "done" pour chaque team lead
- Pas de metriques: nombre de bugs fixes, endpoints valides, coverage, etc.

### L2 — Pas de gestion d'erreurs
- Que se passe-t-il si un team lead echoue completement?
- Pas de rollback: si TL2 (Data Integrity) casse des tests, comment revenir en arriere?
- Pas de strategie de retry ou de fallback

### L3 — Pas de timeouts
- Aucune limite de temps par team lead ou par sous-agent
- Un agent bloque peut bloquer toute la chaine (surtout TL5 qui attend les 4 autres)
- Pas de deadline globale

### L4 — Pas de gestion git
- Qui cree les branches? Un branch par team lead? Un seul branch?
- Comment gerer les merge conflicts entre agents qui modifient le meme code?
- Le plan ne mentionne pas de strategie de commit (un commit par sous-tache? par team lead?)

### L5 — Pas de validation intermediaire
- Le dispatcher ne revoit pas le travail des team leads avant la consolidation
- Pas de quality gate entre les etapes
- Risque d'accumulation d'erreurs qui ne sont detectees qu'a la fin

### L6 — Brainstorming sans criteres de synthese
- Les 12 outputs vont etre heterogenes en format et en profondeur
- Pas de grille d'evaluation pour la phase de confrontation
- Comment decider quelles recommandations garder vs. rejeter?

### L7 — Pas de communication inter-team-leads
- Les team leads ne communiquent qu'avec le dispatcher, pas entre eux
- TL2 (Data Integrity) et TL3 (Endpoint Validation) pourraient avoir des dependances croisees
- Pas de protocole de coordination laterale

---

## RECOMMANDATIONS

### P0 — Critique

**P0.1 — Definir un budget global et des limites par team lead.**
Ajouter dans chaque mission: `max_cost: $X`, `max_agents: N`, `max_turns: N`. Le dispatcher doit avoir un budget total et couper les agents qui depassent.

**P0.2 — Ajouter des dependances explicites entre TL1-TL4 et TL5.**
TL5 ne doit PAS demarrer tant que TL1-TL4 n'ont pas marque leurs taches comme `completed`. Utiliser `addBlockedBy` dans les tasks.

**P0.3 — Definir une strategie git AVANT de lancer les agents.**
Recommandation: 1 branche par team lead (`tl1/github-setup`, `tl2/data-integrity`, etc.), merge sequentiel vers `main` apres validation. Chaque team lead est responsable de ses commits.

**P0.4 — Valider que les 3 CLIs brainstorming fonctionnent AVANT de lancer les 12 executions.**
Tester `gemini`, `codex`, `vibe` avec un prompt trivial. Avoir un fallback (ex: remplacer Vibe par un prompt Claude direct si Vibe echoue).

### P1 — Important

**P1.1 — Ajouter des quality gates.**
Le dispatcher doit revoir les outputs de chaque team lead avant de lancer TL5. Minimum: verifier que les zones balisees existent et contiennent du contenu substantiel.

**P1.2 — Definir des criteres de "done" par mission.**
Exemples: TL1 = issues creees + labels appliques, TL2 = 0 bugs critiques + tests passants, TL3 = 9 endpoints valides avec reponse 200, TL4 = CI/CD pipeline vert.

**P1.3 — Ajouter des timeouts.**
Suggestion: 30 min par team lead, 10 min par sous-agent, 5 min par execution brainstorming. Le dispatcher monitore et coupe les agents depasses.

**P1.4 — Permettre la communication laterale entre TL2 et TL3.**
Ces deux missions touchent au meme code (endpoints + data integrity). Ajouter un canal de coordination ou merger ces missions.

### P2 — Nice-to-have

**P2.1 — Ajouter un dry-run.**
Lancer d'abord 1 seul team lead (le plus simple, ex: TL1 GitHub Setup) pour valider le workflow avant de tout paralleliser.

**P2.2 — Grille d'evaluation pour le brainstorming.**
Creer une grille avec des criteres (pertinence, faisabilite, originalite, cout) pour noter les 12 outputs et faciliter la synthese.

**P2.3 — Dashboard de progression.**
Un fichier `docs/progress.md` mis a jour par chaque team lead avec: statut, taches terminees, blocages. Facilite le monitoring par le dispatcher.

**P2.4 — Reduire le scope du brainstorming.**
12 executions paralleles est ambitieux. Commencer par 4 (1 outil x 4 sujets) puis etendre si les resultats sont bons.

---

## VERDICT GLOBAL

Le plan est **solide dans sa structure** mais **fragile dans son execution**. L'architecture pyramidale et la separation des responsabilites sont bien pensees. Les risques principaux sont: l'absence de budget/timeouts (peut exploser en couts), l'absence de strategie git (peut creer des conflits), et la dependance aux CLIs externes pour le brainstorming (Vibe confirme non-fonctionnel en pipe).

**Recommandation principale:** Implementer les 4 items P0 avant de lancer quoi que ce soit. Ensuite, faire un dry-run avec TL1 seul avant de paralleliser.
