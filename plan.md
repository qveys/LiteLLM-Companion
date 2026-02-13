# Plan V2: Fix Detection System

## Contexte

Detection rate actuelle: **3/8 (37.5%)** des apps AI en cours sur cette machine.
Objectif: **>=80% (7/8+)** de detection sur les apps reellement installees et en cours.

Sources: 4 rapports d'exploration (`docs/analysis/`) + 3 reviews externes (Gemini 53/100, Codex 44/100, Vibe 56/100).

---

## 1. Inventaire complet des bugs

### Desktop Apps

| # | App | Symptome | Cause racine | Fix exact | Fichier | Test |
|---|-----|----------|-------------|-----------|---------|------|
| D1 | ChatGPT | Non detecte | `proc.name()` = `ChatGPTHelper`, config attend `ChatGPT` | Ajouter `ChatGPTHelper` a `process_names.macos` | ai_config.yaml:8-10 | `test_chatgpt_helper_detected` |
| D2 | Claude Desktop | Non detecte | Seul `chrome-native-host` visible, config attend `Claude` | Ajouter `exe_path_patterns: ["Claude.app"]` | ai_config.yaml:14-16 + desktop.py | `test_claude_desktop_exe_path` |
| D3 | Comet (Perplexity) | Non detecte | Rebrand en "Comet", absent config | Remplacer `Perplexity` par `Comet` + `Comet Helper (Renderer)` dans process_names | ai_config.yaml:90-95 | `test_comet_detected` |
| D4 | Copilot JetBrains | Non detecte | `copilot-language-server` absent config | Ajouter `copilot-language-server` aux process_names de JetBrains AI | ai_config.yaml:49-58 | `test_copilot_language_server` |
| D5 | superwhisper | Non detecte | Absent config | Ajouter nouvelle entree `superwhisper` | ai_config.yaml (new) | `test_superwhisper_detected` |
| D6 | Codex Desktop | Non detecte | Absent config | Ajouter nouvelle entree `Codex` | ai_config.yaml (new) | `test_codex_desktop_detected` |
| D7 | Zed | Non detecte | Absent config | Ajouter nouvelle entree `zed` | ai_config.yaml (new) | `test_zed_detected` |

### CLI Tools

| # | Tool | Symptome | Cause racine | Fix exact | Fichier | Test |
|---|------|----------|-------------|-----------|---------|------|
| C1 | Claude Code | Non detecte | `proc.name()` = `2.1.39` (version!) | Ajouter `exe_path_patterns: ["/claude/versions/"]` + `cmdline_patterns: ["claude"]` | ai_config.yaml:238-245 + cli.py | `test_claude_code_version_name` |
| C2 | Codex CLI | Non detecte | `proc.name()` = `codex-aarch64-apple-darwin` | Ajouter `codex-aarch64-apple-darwin` a process_names + `exe_path_patterns` | ai_config.yaml:305-310 | `test_codex_cli_arch_name` |
| C3 | Gemini CLI | Non detecte | `proc.name()` = `node` | Deja gere par cmdline_patterns — verifier que ca fonctionne avec cmdline[:3] | ai_config.yaml:292-300 | `test_gemini_node_cmdline` |
| C4 | Vibe | Non detecte | `proc.name()` = `python` | Ajouter `exe_path_patterns: ["mistral-vibe"]` | ai_config.yaml:312-320 | `test_vibe_python_exe_path` |
| C5 | gh copilot | Faux positifs | `process_names: ["gh"]` matche TOUT usage de gh | Retirer `gh` des process_names, garder uniquement `cmdline_patterns: ["gh copilot"]` | ai_config.yaml:247-254 | `test_gh_alone_not_detected` + `test_gh_copilot_detected` |

---

## 2. Architecture de detection (3 tiers)

```
Tier 1: proc.name() exact match              (existant, rapide, ~0ms)
Tier 2: proc.exe() path substring match      (NOUVEAU, +2ms/scan)
Tier 3: cmdline[:3] substring match           (AMELIORE, limite faux positifs)
```

### Pourquoi cmdline[:3] et pas cmdline complet ?
```
# Faux positif observe:
cmdline = ["claude", "--resume", "49958b5c", "--dangerously-skip-permissions"]
# "claude" dans cmdline[:3] = OK (arg 0)

# Mais avec cmdline complet, un process random pourrait matcher:
cmdline = ["some-tool", "--config", "/path/to/claude/config.json"]
# "claude" dans join(cmdline) = FAUX POSITIF
```

---

## 3. Modifications exactes par fichier

### 3.1. ai_config.yaml — Snippets exacts

#### D1: ChatGPT — ajouter ChatGPTHelper
```yaml
# AVANT (ligne 8-10)
- name: ChatGPT
  process_names:
    macos: ["ChatGPT"]
    windows: ["ChatGPT.exe"]

# APRES
- name: ChatGPT
  process_names:
    macos: ["ChatGPT", "ChatGPTHelper"]
    windows: ["ChatGPT.exe"]
```

#### D2: Claude Desktop — ajouter exe_path_patterns
```yaml
# AVANT (ligne 14-16)
- name: Claude
  process_names:
    macos: ["Claude"]
    windows: ["Claude.exe"]

# APRES
- name: Claude
  process_names:
    macos: ["Claude", "chrome-native-host"]
    windows: ["Claude.exe"]
  exe_path_patterns: ["Claude.app"]
```

#### D3: Perplexity/Comet — corriger process_names
```yaml
# AVANT (ligne 90-95)
- name: Perplexity
  process_names:
    macos: ["Perplexity"]
    windows: ["Perplexity.exe"]

# APRES
- name: Perplexity
  process_names:
    macos: ["Perplexity", "Comet", "Comet Helper (Renderer)"]
    windows: ["Perplexity.exe"]
  exe_path_patterns: ["Comet.app"]
```

#### D4: Copilot JetBrains — ajouter copilot-language-server
```yaml
# AVANT (ligne 49-58) — JetBrains AI entry
- name: JetBrains AI
  process_names:
    macos: ["idea", "pycharm", "webstorm", "goland", "clion", "rider"]

# APRES — ajouter copilot-language-server
- name: JetBrains AI
  process_names:
    macos: ["idea", "pycharm", "webstorm", "goland", "clion", "rider", "copilot-language-server"]
```

#### D5-D7: Nouvelles apps (apres Pieces, avant ai_domains)
```yaml
  - name: superwhisper
    process_names:
      macos: ["superwhisper"]
    category: audio
    cost_per_hour: 0.20

  - name: Codex Desktop
    process_names:
      macos: ["Codex"]
      windows: ["Codex.exe"]
    exe_path_patterns: ["Codex.app"]
    category: code
    cost_per_hour: 1.00

  - name: Zed
    process_names:
      macos: ["zed"]
      windows: ["zed.exe"]
    category: code
    cost_per_hour: 0.30
    note: "Editor with built-in AI assistant"
```

#### C1: Claude Code CLI — ajouter exe_path_patterns
```yaml
# AVANT (ligne 238-245)
- name: claude-code
  process_names:
    macos: ["claude"]
    linux: ["claude"]
    windows: ["claude.exe"]
  command_patterns: ["claude"]
  category: code

# APRES
- name: claude-code
  process_names:
    macos: ["claude"]
    linux: ["claude"]
    windows: ["claude.exe"]
  command_patterns: ["claude"]
  exe_path_patterns: ["/claude/versions/"]
  cmdline_patterns: ["claude"]
  category: code
```

#### C2: Codex CLI — ajouter nom avec arch
```yaml
# AVANT (ligne 305-310)
- name: codex-cli
  process_names:
    macos: ["codex"]

# APRES
- name: codex-cli
  process_names:
    macos: ["codex", "codex-aarch64-apple-darwin"]
    linux: ["codex", "codex-x86_64-unknown-linux-gnu"]
    windows: ["codex.exe"]
  exe_path_patterns: ["/codex"]
```

#### C5: gh copilot — retirer gh des process_names
```yaml
# AVANT (ligne 247-254)
- name: github-copilot-cli
  process_names:
    macos: ["gh"]
    linux: ["gh"]
    windows: ["gh.exe"]
  command_patterns: ["gh copilot"]

# APRES
- name: github-copilot-cli
  process_names:
    macos: []
    linux: []
    windows: []
  command_patterns: ["gh copilot"]
  cmdline_patterns: ["gh copilot"]
```

### 3.2. desktop.py — Ajouter Tier 2 (exe path matching)

```python
# DANS __init__, apres self._cmdline_patterns (ligne ~52):
# Ajouter:
self._exe_patterns: dict[str, dict] = {}
for app in config.ai_apps:
    for pattern in app.get("exe_path_patterns", []):
        self._exe_patterns[pattern.lower()] = app

# DANS scan(), modifier process_iter (ligne 69):
# AVANT:
for proc in psutil.process_iter(["pid", "name", "cmdline"]):
# APRES:
for proc in psutil.process_iter(["pid", "name", "exe", "cmdline"]):

# DANS scan(), apres le Tier 1 name match (ligne ~80), AVANT le cmdline fallback:
# Ajouter Tier 2:
if app_cfg is None and self._exe_patterns:
    exe_path = proc.info.get("exe") or ""
    if exe_path and not exe_path.startswith("/System/Library/"):
        exe_lower = exe_path.lower()
        for pattern, candidate in self._exe_patterns.items():
            if pattern in exe_lower:
                app_cfg = candidate
                break
```

**Protection `/System/Library/`**: evite les faux positifs macOS (ex: `CursorUIViewService` dans `/System/Library/` qui contient "Cursor").

### 3.3. cli.py — Ajouter Tier 2 + limiter cmdline

```python
# DANS __init__, apres self._cmdline_patterns (ligne ~57):
# Ajouter:
self._exe_patterns: dict[str, dict] = {}
for tool in config.ai_cli_tools:
    for pattern in tool.get("exe_path_patterns", []):
        self._exe_patterns[pattern.lower()] = tool

# DANS scan(), modifier process_iter (ligne 81):
# AVANT:
for proc in psutil.process_iter(["pid", "name", "cmdline"]):
# APRES:
for proc in psutil.process_iter(["pid", "name", "exe", "cmdline"]):

# DANS scan(), apres le Tier 1 name match (ligne ~103), AVANT le cmdline fallback:
# Ajouter Tier 2:
if tool_cfg is None and self._exe_patterns:
    exe_path = proc.info.get("exe") or ""
    if exe_path:
        exe_lower = exe_path.lower()
        for pattern, candidate in self._exe_patterns.items():
            if pattern in exe_lower:
                tool_cfg = candidate
                break

# DANS scan(), modifier le cmdline matching (ligne ~109):
# AVANT:
cmdline_str = " ".join(cmdline).lower()
# APRES (limiter a cmdline[:3]):
cmdline_str = " ".join(cmdline[:3]).lower()
```

---

## 4. Matrice de tests

### 4.1. Tests positifs (detection attendue)

| Test | proc.name | proc.exe | cmdline | Tool attendu | Tier |
|------|-----------|----------|---------|-------------|------|
| `test_chatgpt_helper_detected` | `ChatGPTHelper` | `/Applications/ChatGPT.app/.../ChatGPTHelper` | — | ChatGPT | 1 |
| `test_claude_desktop_exe_path` | `chrome-native-host` | `/Applications/Claude.app/.../chrome-native-host` | — | Claude | 1+2 |
| `test_comet_detected` | `Comet` | `/Applications/Comet.app/.../Comet` | — | Perplexity | 1 |
| `test_copilot_language_server` | `copilot-language-server` | `.../copilot-agent/.../copilot-language-server` | — | JetBrains AI | 1 |
| `test_superwhisper_detected` | `superwhisper` | `/Applications/superwhisper.app/.../superwhisper` | — | superwhisper | 1 |
| `test_claude_code_version_name` | `2.1.39` | `~/.local/share/claude/versions/2.1.39` | `["claude", "--resume", "xxx"]` | claude-code | 2 |
| `test_codex_cli_arch_name` | `codex-aarch64-apple-darwin` | `~/.codex/codex-aarch64-apple-darwin` | — | codex-cli | 1 |
| `test_gemini_node_cmdline` | `node` | `/usr/local/bin/node` | `["node", "/path/gemini-cli/index.js"]` | gemini-cli | 3 |
| `test_vibe_python_exe_path` | `python` | `~/.local/share/uv/tools/mistral-vibe/.../python` | `["python3", "-m", "vibe"]` | vibe | 2 |
| `test_gh_copilot_detected` | `gh` | `/usr/local/bin/gh` | `["gh", "copilot", "suggest"]` | github-copilot-cli | 3 |

### 4.2. Tests negatifs (PAS de detection)

| Test | proc.name | proc.exe | cmdline | Attendu |
|------|-----------|----------|---------|---------|
| `test_gh_alone_not_detected` | `gh` | `/usr/local/bin/gh` | `["gh", "pr", "list"]` | **Rien** |
| `test_node_random_not_detected` | `node` | `/usr/local/bin/node` | `["node", "webpack", "serve"]` | **Rien** |
| `test_python_random_not_detected` | `python` | `/usr/bin/python3` | `["python3", "manage.py", "runserver"]` | **Rien** |
| `test_system_cursor_not_detected` | `CursorUIViewService` | `/System/Library/.../CursorUIViewService` | — | **Rien** (filtre /System/Library/) |
| `test_chrome_native_not_claude` | `chrome-native-host` | `/Applications/Arc.app/.../chrome-native-host` | — | **Rien** (exe path ne contient pas Claude.app) |

### 4.3. Tests edge cases

| Test | Scenario | Attendu |
|------|----------|---------|
| `test_exe_none_no_crash` | `proc.info["exe"]` = `None` (AccessDenied) | Continue sans crash |
| `test_cmdline_empty_no_crash` | `proc.info["cmdline"]` = `[]` ou `None` | Continue sans crash |
| `test_exe_access_denied` | `proc.exe()` leve `psutil.AccessDenied` | Continue sans crash |
| `test_existing_ollama_still_works` | `proc.name()` = `Ollama` | Toujours detecte (non-regression) |
| `test_existing_idea_still_works` | `proc.name()` = `idea` | Toujours detecte (non-regression) |

### 4.4. Objectif quantitatif

**Detection rate cible: >= 80% (8/10 apps testables)**
- Avant: 3/8 (37.5%)
- Apres: au minimum 7/8 apps actuellement en cours doivent etre detectees

---

## 5. Gestion des risques

| Risque | Probabilite | Impact | Mitigation |
|--------|:-----------:|:------:|-----------|
| `proc.exe()` retourne `None` (AccessDenied) | Haute | Crash scan | `exe_path = proc.info.get("exe") or ""` — deja gere par psutil quand on passe `"exe"` a `process_iter` (retourne None au lieu de lever) |
| `proc.cmdline()` leve `AccessDenied` | Moyenne | Skip detection | Deja gere par le try/except existant (ligne 115/121 dans les detecteurs) |
| Faux positifs `chrome-native-host` (Arc, Chrome, etc.) | Haute | Mauvaise attribution | Combiner Tier 1 + Tier 2: `chrome-native-host` dans process_names ET `Claude.app` dans exe_path obligatoire |
| Faux positifs `node`/`python` | Haute | Mauvaise attribution | Tier 3 limite a `cmdline[:3]` — seuls les 3 premiers args sont scannes |
| Faux positif `/System/Library/CursorUIViewService` | Moyenne | Fausse detection Cursor | Filtre explicite: `if exe_path.startswith("/System/Library/"): skip` |
| Regression apps existantes (Ollama, JetBrains) | Faible | Perte detection | Tests de non-regression dans la matrice (section 4.3) |
| Performance degradee (+2ms/scan) | Faible | Scan trop lent | Budget: scan complet < 100ms. Monitorer via log timing. |
| Rollback necessaire | Faible | Retour arriere | `git revert <merge-sha>` sur la PR. Config YAML seul = zero risque code. |

---

## 6. Execution — Equipe de 3 agents

### Agent 1: `fix-config`

**Fichier cible:** `src/ai_cost_observer/data/ai_config.yaml`

**Instructions exactes:**
1. Lire le fichier `ai_config.yaml`
2. Appliquer EXACTEMENT les modifications YAML de la section 3.1 (D1 a D7, C1 a C5)
3. Verifier la syntaxe YAML (`python -c "import yaml; yaml.safe_load(open('...'))"`)
4. NE PAS modifier d'autre fichier

**Definition of Done:**
- [ ] Tous les snippets de la section 3.1 appliques
- [ ] YAML valide (pas d'erreur de parsing)
- [ ] 7 bugs desktop + 5 bugs CLI adresses

**Quand tu as termine, sauvegarde, envoie un message au team lead, puis FERME TA SESSION.**

### Agent 2: `fix-detectors`

**Fichiers cibles:** `src/ai_cost_observer/detectors/desktop.py` + `src/ai_cost_observer/detectors/cli.py`

**Instructions exactes:**
1. Lire `desktop.py` et `cli.py`
2. Appliquer les modifications de la section 3.2 (desktop.py):
   - Ajouter `self._exe_patterns` dans `__init__`
   - Ajouter `"exe"` a `process_iter`
   - Ajouter Tier 2 entre Tier 1 et Tier 3 dans `scan()`
   - Ajouter filtre `/System/Library/`
3. Appliquer les modifications de la section 3.3 (cli.py):
   - Ajouter `self._exe_patterns` dans `__init__`
   - Ajouter `"exe"` a `process_iter`
   - Ajouter Tier 2 dans `scan()`
   - Limiter cmdline a `[:3]`
4. Lancer `uv run python -m pytest tests/detectors/ tests/test_cli_cmdline.py -x` pour verifier que les tests existants passent toujours
5. NE PAS modifier d'autre fichier

**Definition of Done:**
- [ ] Tier 2 (exe path) ajoute dans les deux detecteurs
- [ ] cmdline limite a [:3] dans cli.py
- [ ] Filtre /System/Library/ ajoute dans desktop.py
- [ ] Tests existants passent toujours

**Quand tu as termine, sauvegarde, envoie un message au team lead, puis FERME TA SESSION.**

### Agent 3: `fix-tests` (BLOQUE par agents 1 + 2)

**Fichiers cibles:** `tests/test_detection_tiers.py` (NOUVEAU)

**Instructions exactes:**
1. Attendre que les agents 1 et 2 aient termine (le team lead t'enverra un message)
2. Lire les fichiers modifies (`ai_config.yaml`, `desktop.py`, `cli.py`)
3. Creer `tests/test_detection_tiers.py` avec TOUS les tests de la section 4 (positifs, negatifs, edge cases, non-regression)
4. Les mocks doivent inclure `exe` dans `proc.info`: `proc.info = {"pid": X, "name": "...", "exe": "...", "cmdline": [...]}`
5. Lancer `uv run python -m pytest -x` (TOUS les tests, pas juste les nouveaux)
6. Si des tests echouent, diagnostiquer et fixer (dans les tests OU dans le code source si bug evident)

**Definition of Done:**
- [ ] >= 20 nouveaux tests (10 positifs + 5 negatifs + 5 edge cases)
- [ ] `uv run python -m pytest` = 0 failures
- [ ] `uv run ruff check src/` = clean

**Quand tu as termine, sauvegarde, envoie un message au team lead, puis FERME TA SESSION.**

### Orchestration

```
[Team Lead]
    ├── spawn Agent 1 (fix-config) ── en parallele
    ├── spawn Agent 2 (fix-detectors) ── en parallele
    │
    ├── Attendre completion Agent 1 + Agent 2
    │
    ├── spawn Agent 3 (fix-tests) ── sequentiel
    │
    └── Quand Agent 3 termine: passer a Phase 2
```

**Si un agent echoue:** Le team lead lit le message d'erreur, corrige le probleme lui-meme ou relance un agent avec des instructions ajustees.

---

## 7. Phase 2: PR + Labels + Issues

### Branch et commit
- Creer branche `fix/detection-system` depuis `main`
- Commits atomiques Conventional Commits:
  - `🐛 fix(config): add missing process names for ChatGPT, Claude, Comet`
  - `🐛 fix(config): add exe_path_patterns for CLI tools`
  - `🐛 fix(config): remove gh false positive, add new apps`
  - `✨ feat(detector): add Tier 2 exe path matching`
  - `🐛 fix(detector): limit cmdline matching to first 3 args`
  - `✅ test(detector): add detection tier test matrix`
- Push vers origin

### PR
```
Title: fix(detection): add exe path matching + fix 12 detection bugs
Body:
## Summary
- Add Tier 2 exe path matching to desktop + CLI detectors
- Fix 7 desktop app detection bugs (ChatGPT, Claude, Comet, etc.)
- Fix 5 CLI tool detection bugs (Claude Code, Codex, gh copilot, etc.)
- Add 4 new apps (superwhisper, Codex Desktop, Zed, copilot-language-server)
- Detection rate: 37.5% → target 80%+

## Test plan
- [ ] 20+ new tests in test_detection_tiers.py
- [ ] All existing tests pass (336+)
- [ ] Manual validation on this machine
Labels: bug, detection, priority: high, enhancement
```

### Issues GitHub
- 1 issue par bug (D1-D7, C1-C5 = 12 issues)
- Labels: `bug`, `detection`, composant (`desktop`/`cli`/`config`)
- Liees a la PR via `Fixes #XX`

### Auto-labelling GitHub Action
```yaml
# .github/workflows/auto-label.yml
name: Auto Label
on:
  pull_request:
    types: [opened, synchronize]
jobs:
  label:
    runs-on: ubuntu-latest
    permissions:
      pull-requests: write
    steps:
      - uses: actions/labeler@v5
        with:
          repo-token: "${{ secrets.GITHUB_TOKEN }}"
# .github/labeler.yml
detection:
  - changed-files:
    - any-glob-to-any-file: 'src/**/detectors/**'
config:
  - changed-files:
    - any-glob-to-any-file: 'src/**/data/**'
tests:
  - changed-files:
    - any-glob-to-any-file: 'tests/**'
ci/cd:
  - changed-files:
    - any-glob-to-any-file: ['.github/**', '*.yml']
```

---

## 8. Phase 3: Review cycle

Quand les reviews externes arrivent (CodeRabbit, reviewers configures):

### Triage des commentaires
| Categorie | Action | SLA |
|-----------|--------|-----|
| `blocking` | Fix obligatoire avant merge | Immediat |
| `important` | Fix recommande | Meme session |
| `nit` | Fix optionnel | Best effort |
| `question` | Repondre au commentaire | Repondre |

### Equipe de traitement (2 agents)
- **Agent review-code**: Lire chaque commentaire, corriger le code, commit + push
- **Agent review-respond**: Repondre aux commentaires GitHub, expliquer les choix

**Definition of Done pour chaque commentaire:**
- [ ] Commit SHA reference dans la reponse
- [ ] Test relance apres correction
- [ ] Thread resolu

---

## 9. Validation terrain

### Protocole de validation manuelle

| Etape | Action | Verification |
|-------|--------|-------------|
| 1 | Lancer l'agent avec `python -m ai_cost_observer` | Demarre sans erreur |
| 2 | Ouvrir ChatGPT.app | Log: `Detected AI app: ChatGPT` |
| 3 | Verifier Claude Desktop tourne | Log: `Detected AI app: Claude` |
| 4 | Verifier Comet tourne | Log: `Detected AI app: Perplexity` |
| 5 | Verifier Claude Code tourne (ce terminal) | Log: `Detected AI CLI tool: claude-code` |
| 6 | Lancer `gh pr list` (pas copilot) | PAS de log `github-copilot-cli` |
| 7 | Verifier Ollama tourne | Log: `Detected AI app: Ollama (GUI)` (non-regression) |
| 8 | Verifier IntelliJ tourne | Log: `Detected AI app: JetBrains AI` (non-regression) |

**Critere de succes:** >= 7/8 apps detectees correctement, 0 faux positifs.

---

## 10. Hors scope

- Bundle ID detection (NSRunningApplication) — amelioration future macOS-only
- Hook-based detection (WakaTime style) — amelioration future
- Apps non installees (Windsurf, LM Studio, etc.) — pas testable
- Auto-Claude — pas installe, pas testable
