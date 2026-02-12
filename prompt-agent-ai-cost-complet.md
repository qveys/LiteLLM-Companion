# PROMPT COMPLET : Agent Host Cross-Platform d'Observabilité des Coûts IA Personnels
## (Apps Desktop + Navigateurs Web + CLI)

## CONTEXTE & OBJECTIF

Tu dois construire un **agent host cross-platform (Windows & macOS)** pour suivre **précisément et objectivement** mes coûts mensuels liés à l'intelligence artificielle en usage personnel. L'agent doit :

1. **Détecter automatiquement** les applications IA desktop (ChatGPT Desktop, Claude Desktop, Cursor, etc.)
2. **Surveiller l'usage IA dans les navigateurs web** (Perplexity, Lovable, Bolt, ChatGPT web, Claude web, etc.)
3. **Mesurer leur usage réel** (durée active par domaine, fréquence, patterns)
4. **Collecter les métriques réseau** associées (volume données, timing, endpoints)
5. **Centraliser** toutes ces données dans OpenTelemetry
6. **Visualiser** les coûts et usages dans Grafana avec dashboards exploitables
7. **Aucun problème RGPD** : c'est **uniquement pour moi-même**, usage personnel strict

### Contraintes techniques absolues
- **Cross-platform** : fonctionner identiquement sur Windows 10/11 ET macOS (12+)
- **Léger** : consommation CPU/RAM minimale (< 5% CPU, < 200MB RAM en idle)
- **Non-invasif** : pas d'injection process, pas de modification binaires apps IA, pas d'inspection TLS
- **Respectueux TLS** : cert pinning ChatGPT Desktop bloque inspection, métriques réseau externes uniquement
- **Autonome** : lancement automatique au boot, récupération après crash app IA
- **Données locales** : toute la stack d'observabilité tourne en local (pas de cloud)
- **Privacy-first** : tracking usage sans contenu (pas de prompts, seulement durée/domaines)

---

## STACK TECHNIQUE VALIDÉE

### Langage & bibliothèques principales
- **Python 3.11+** (compatibilité Windows + macOS, écosystème riche)
- **psutil 6.1.1** : monitoring cross-platform processus & système[web:139][web:142]
  - CPU, mémoire, disque, réseau par processus
  - Détection process par nom/PID
  - Compatible Linux/Windows/macOS/FreeBSD
- **OpenTelemetry Python SDK 1.28+** : instrumentation custom metrics/traces[web:159][web:162]
  - Création métriques (Counter, UpDownCounter, Histogram)
  - Export OTLP vers Collector
  - Ressource attributes personnalisées

### Monitoring navigateur web (2 approches complémentaires)

#### Approche 1 : Extension navigateur (Chrome/Firefox/Edge)
- **Manifest V3** : API moderne Chrome Extensions[web:199][web:201]
  - `chrome.tabs` API : détection tab active, URL, titre[web:199][web:201]
  - `chrome.tabs.onActivated` : événement changement tab[web:201]
  - `chrome.tabs.onUpdated` : événement navigation nouvelle URL[web:201]
  - Storage local (`chrome.storage.local`) : persistance données[web:169][web:176]
- **WebExtensions API (Firefox)** : équivalent cross-browser[web:197]
  - `browser.tabs.query()` : requête tabs actifs
  - `browser.history` API : accès historique (permission "history" requise)[web:197]
- **Export métriques** : extension expose métriques via Native Messaging ou HTTP local[web:177]

#### Approche 2 : Analyse historique navigateur (SQLite)
- **Chrome/Edge** : `~/.config/google-chrome/Default/History` (Linux/macOS), `%LOCALAPPDATA%\Google\Chrome\User Data\Default\History` (Windows)[web:203][web:209][web:212]
  - Table `urls` : url, title, visit_count, last_visit_time
  - Table `visits` : visit_time, from_visit, transition
  - Query domaines IA : `SELECT url, visit_count FROM urls WHERE url LIKE '%perplexity.ai%'`[web:203][web:209]
- **Firefox** : `~/.mozilla/firefox/[profile]/places.sqlite`[web:206]
  - Table `moz_places` : url, title, rev_host (host inversé)
  - Table `moz_historyvisits` : visit_date, place_id (foreign key)
  - JOIN requis : `SELECT visit_date, url FROM moz_historyvisits LEFT JOIN moz_places ON moz_historyvisits.place_id = moz_places.id WHERE url LIKE '%claude.ai%'`[web:206]
- **Safari** : `~/Library/Safari/History.db`[web:203]
  - Table `history_items` : url, visit_count
  - Table `history_visits` : visit_time, history_item (foreign key)

#### Approche 3 : Monitoring réseau DNS (fallback)
- **DNS query logging** : capturer requêtes DNS vers domaines IA[web:175][web:178][web:181]
- **DNS filtering** : filtrer par catégorie domaines (AI tools)[web:181]
- Limitation : ne donne pas durée exacte sur page, seulement fréquence accès

### Stack observabilité locale
- **OpenTelemetry Collector Contrib 0.115+** : agrégation télémétrie[web:144][web:153]
  - Host metrics receiver (CPU, mémoire, disque, réseau, filesystem)[web:126][web:144][web:147]
  - OTLP receiver (pour agent Python custom)
  - Prometheus exporter (pour Grafana)
- **Prometheus 3.0+** : stockage time-series métriques[web:145][web:148]
  - Scraping Collector OpenTelemetry
  - Rétention 30 jours (configurable)
- **Grafana 11.4+** : visualisation dashboards[web:145][web:148]
  - Datasource Prometheus
  - Dashboards JSON pré-configurés[web:160][web:163][web:166]

### Déploiement
- **Docker Compose** : orchestration stack complète (Collector + Prometheus + Grafana)[web:145][web:148][web:151]
- **Agent Python** : script standalone, installé comme service système
  - Windows : Task Scheduler ou NSSM (Non-Sucking Service Manager)
  - macOS : launchd daemon[web:53][web:60]
- **Extension navigateur** : installable Chrome Web Store / Firefox Add-ons (ou unpacked pour dev)

---

## ARCHITECTURE DÉTAILLÉE

```
┌────────────────────────────────────────────────────────────────────────────┐
│                    HOST SYSTEM (Windows / macOS)                           │
│                                                                            │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │         Applications IA Desktop (détectées automatiquement)          │  │
│  │  • ChatGPT Desktop (ChatGPT.exe / ChatGPT.app)                       │  │
│  │  • Claude Desktop (Claude.exe / Claude.app)                          │  │
│  │  • Cursor, GitHub Copilot, Notion AI, etc.                           │  │
│  └─────────────────────┬────────────────────────────────────────────────┘  │
│                        │ Monitoring                                        │
│                        ▼                                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │         AGENT PYTHON (ai_cost_observer.py)                           │  │
│  │  • psutil : détection process, CPU, RAM, I/O réseau                  │  │
│  │  • OpenTelemetry SDK : custom metrics                                │  │
│  │  • Browser history parser : SQLite (Chrome/Firefox/Safari)           │  │
│  │  • Logic métier : corrélation usage → coûts estimés                  │  │
│  │  • Export OTLP → OTel Collector (localhost:4317)                     │  │
│  └─────────────────────┬────────────────────────────────────────────────┘  │
│                        │                                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │         NAVIGATEURS WEB (Chrome, Firefox, Edge, Safari, etc.)        │  │
│  │  • chrome.exe, firefox.exe, msedge.exe, Safari                       │  │
│  │  • Extension Browser Tracker (optionnel, Manifest V3)                │  │
│  │    - Détecte tab active, URL courante                                │  │
│  │    - Track temps par domaine (perplexity.ai, bolt.new, etc.)         │  │
│  │    - Export métriques via Native Messaging → Agent Python            │  │
│  │  • Historique SQLite (Chrome/Firefox/Safari)                         │  │
│  │    - Parsé par agent Python toutes les 60s                           │  │
│  │    - Filtre domaines IA, calcule durée depuis last_visit_time        │  │
│  └─────────────────────┬────────────────────────────────────────────────┘  │
│                        │ OTLP/gRPC                                         │
│                        ▼                                                   │
└────────────────────────┼───────────────────────────────────────────────────┘
                         │
┌────────────────────────┼───────────────────────────────────────────────────┐
│              STACK OBSERVABILITÉ (Docker Compose)                          │
│                        │                                                   │
│  ┌─────────────────────▼─────────────────────────────────────────────────┐ │
│  │     OpenTelemetry Collector (otel-collector-contrib)                  │ │
│  │  Receivers:                                                           │ │
│  │   • hostmetrics (CPU, RAM, disk, network host-level)                  │ │
│  │   • otlp (métriques agent Python + extension browser)                 │ │
│  │  Processors:                                                          │ │
│  │   • batch (groupement métriques)                                      │ │
│  │   • resource (ajout labels env)                                       │ │
│  │  Exporters:                                                           │ │
│  │   • prometheus (exposition :8889/metrics)                             │ │
│  └────────────────────┬──────────────────────────────────────────────────┘ │
│                       │ HTTP :8889/metrics                                 │
│                       ▼                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │               Prometheus (time-series DB)                           │   │
│  │  • Scrape interval: 15s                                             │   │
│  │  • Rétention: 30 jours                                              │   │
│  │  • Storage: volume Docker persistant                                │   │
│  └────────────────────┬────────────────────────────────────────────────┘   │
│                       │ PromQL queries                                     │
│                       ▼                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                 Grafana (visualisation)                             │   │
│  │  • Datasource: Prometheus                                           │   │
│  │  • Dashboards: AI Cost Overview, Browser AI Usage, App Details      │   │
│  │  • Alerts: budget dépassé, usage anormal                            │   │
│  │  • UI: http://localhost:3000                                        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## DÉTECTION DES APPLICATIONS IA

### 1. Applications desktop natives

| App | Process Windows | Process macOS | Endpoints réseau connus | Cost Estimate ($/h active) |
|-----|----------------|---------------|------------------------|----------------------------|
| **ChatGPT Desktop** | `ChatGPT.exe`, `ChatGPTHelper.exe` | `ChatGPT`, `ChatGPTHelper` | `chat.openai.com`, `api.openai.com` | 0.20 |
| **Claude Desktop** | `Claude.exe` | `Claude` | `api.anthropic.com`, `claude.ai` | 0.15 |
| **Cursor** | `Cursor.exe` | `Cursor` | `api.cursor.sh`, `api.openai.com` | 0.25 |
| **GitHub Copilot** | Intégré dans `Code.exe` (VS Code) | Intégré dans `Code` | `api.github.com/copilot` | 0.15 |
| **Notion AI** | Intégré dans `Notion.exe` | Intégré dans `Notion` | `api.notion.com` | 0.10 |
| **Microsoft Copilot** | `Copilot.exe`, intégré Edge/Teams | `Microsoft Copilot` | `copilot.microsoft.com` | 0.10 |

### 2. Applications web (via navigateur)

| Service IA Web | Domaines principaux | Catégorie | Cost Estimate ($/h active) |
|---------------|-------------------|-----------|----------------------------|
| **Perplexity** | `perplexity.ai`, `www.perplexity.ai` | Recherche IA | 0.10 |
| **ChatGPT Web** | `chat.openai.com`, `chatgpt.com` | Assistant conversationnel | 0.20 |
| **Claude Web** | `claude.ai`, `www.claude.ai` | Assistant conversationnel | 0.15 |
| **Lovable (Lovable.dev)** | `lovable.dev`, `lovable.app` | Génération code/sites | 0.30 |
| **Bolt.new** | `bolt.new` | Génération code web | 0.25 |
| **v0.dev (Vercel)** | `v0.dev` | Génération UI React | 0.20 |
| **GitHub Copilot Chat** | `github.com/copilot`, `copilot-proxy.githubusercontent.com` | Génération code | 0.15 |
| **Google Gemini** | `gemini.google.com`, `bard.google.com` | Assistant conversationnel | 0.10 |
| **Microsoft Copilot Web** | `copilot.microsoft.com`, `www.bing.com/chat` | Assistant conversationnel | 0.10 |
| **Anthropic Console** | `console.anthropic.com` | Playground Claude | 0.15 |
| **OpenAI Playground** | `platform.openai.com/playground` | Playground GPT | 0.20 |
| **Hugging Face Chat** | `huggingface.co/chat` | Chat models open-source | Gratuit (tracking usage) |
| **Poe.com** | `poe.com` | Agrégateur IA | 0.12 |
| **Character.AI** | `character.ai`, `beta.character.ai` | Chat IA personnages | 0.08 |
| **Jasper AI** | `jasper.ai`, `app.jasper.ai` | Génération contenu marketing | 0.25 |
| **Midjourney** | `www.midjourney.com`, `discord.com/channels/@me` (serveur MJ) | Génération images | 0.40 |
| **DALL-E** | `labs.openai.com` | Génération images | 0.30 |
| **Runway ML** | `runwayml.com`, `app.runwayml.com` | Génération vidéo IA | 0.50 |
| **ElevenLabs** | `elevenlabs.io`, `beta.elevenlabs.io` | Synthèse vocale IA | 0.20 |
| **Notion AI (web)** | `www.notion.so` (avec usage AI) | Assistant écriture | 0.10 |
| **Grammarly** | `app.grammarly.com`, `www.grammarly.com` | Correction IA | 0.05 |
| **Replit AI** | `replit.com` | Génération code IDE | 0.15 |
| **CodeSandbox AI** | `codesandbox.io` | Génération code IDE | 0.15 |
| **Framer AI** | `framer.com` | Design génératif | 0.20 |
| **Tome AI** | `tome.app` | Création présentations | 0.15 |
| **Beautiful.ai** | `beautiful.ai` | Création présentations | 0.12 |
| **Copy.ai** | `copy.ai`, `app.copy.ai` | Génération copywriting | 0.15 |
| **Writesonic** | `writesonic.com` | Génération contenu | 0.12 |

### 3. Navigateurs à surveiller

| Navigateur | Process Windows | Process macOS | Identification User-Agent |
|-----------|----------------|---------------|---------------------------|
| **Google Chrome** | `chrome.exe` | `Google Chrome` | User-agent: `Chrome/` sans `Edg/` |
| **Microsoft Edge** | `msedge.exe` | `Microsoft Edge` | User-agent: `Edg/` |
| **Mozilla Firefox** | `firefox.exe` | `firefox` | User-agent: `Firefox/` |
| **Safari** | N/A (Windows uniquement) | `Safari` | User-agent: `Safari/` sans `Chrome` |
| **Brave** | `brave.exe` | `Brave Browser` | User-agent: `Chrome/` + `Brave/` |
| **Opera** | `opera.exe` | `Opera` | User-agent: `OPR/` ou `Opera/` |
| **Arc** | N/A | `Arc` | User-agent: `Chrome/` (Chromium-based) |
| **Vivaldi** | `vivaldi.exe` | `Vivaldi` | User-agent: `Vivaldi/` |

### 4. Outils CLI IA (dans le terminal)

| CLI IA              | Binaire typique              | Commandes / alias fréquents           | Catégorie           | Cost Estimate ($/h active) |
|---------------------|------------------------------|---------------------------------------|---------------------|----------------------------|
| Claude Code CLI     | `claude-code`, `claude`      | `cc`, `claude-code`                   | code_assist         | 0.20                       |
| Gemini CLI          | `gemini`, `gemini-cli`       | `gemini`, `gcloud ai gemini`          | code_assist/agent   | 0.15                       |
| Mistral / Vibe CLI  | `mistral`, `mistral-vibe`    | `mistral`, `vibe`                     | code_assist/chat    | 0.10                       |
| Ollama              | `ollama`                     | `ollama run ...`                      | local_llm           | 0.05 (énergie, pas tokens) |
| LM Studio CLI       | `lmstudio`                   | `lmstudio-cli ...`                    | local_llm           | 0.05                       |
| Autres wrappers LLM | ex: `openai`, `anthropic`    | `openai api`, `anthropic messages`    | api_cli             | 0.15                       |

---

## MÉTHODES DE DÉTECTION

### Méthode 1 : Détection process browser + analyse historique SQLite

**Principe** : Parser périodiquement les fichiers SQLite d'historique navigateur, filtrer domaines IA, calculer durée usage

#### Code Python : Parser Chrome History

```python
import sqlite3
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict
import tempfile

class BrowserHistoryParser:
    """Parse browser history SQLite databases to track AI domain usage"""
    
    # Configuration domaines IA à surveiller
    AI_DOMAINS = {
        "perplexity.ai": {"category": "search", "cost_per_hour": 0.10},
        "chat.openai.com": {"category": "conversational", "cost_per_hour": 0.20},
        "chatgpt.com": {"category": "conversational", "cost_per_hour": 0.20},
        "claude.ai": {"category": "conversational", "cost_per_hour": 0.15},
        "lovable.dev": {"category": "code_generation", "cost_per_hour": 0.30},
        "bolt.new": {"category": "code_generation", "cost_per_hour": 0.25},
        "v0.dev": {"category": "code_generation", "cost_per_hour": 0.20},
        "gemini.google.com": {"category": "conversational", "cost_per_hour": 0.10},
        "copilot.microsoft.com": {"category": "conversational", "cost_per_hour": 0.10},
        # ... ajouter tous les domaines du tableau ci-dessus
    }

    AI_CLI_CONFIG = {
        "Claude Code CLI": {
            "process_names": ["claude-code", "claude"],
            "command_prefixes": ["cc ", "cc:", "claude-code "],
            "cost_per_hour": 0.20,
            "log_files": [
                # Adapter aux chemins réels si présents
                "~/.claude-code/usage.jsonl"
            ]
        },
        "Gemini CLI": {
            "process_names": ["gemini", "gemini-cli"],
            "command_prefixes": ["gemini ", "gcloud ai gemini"],
            "cost_per_hour": 0.15,
            "log_files": []
        },
        "Mistral Vibe CLI": {
            "process_names": ["mistral", "mistral-vibe"],
            "command_prefixes": ["mistral ", "vibe "],
            "cost_per_hour": 0.10,
            "log_files": []
        },
        "Ollama": {
            "process_names": ["ollama"],
            "command_prefixes": ["ollama "],
            "cost_per_hour": 0.05,
            "log_files": []
        },
        "LM Studio CLI": {
            "process_names": ["lmstudio", "lmstudio-cli"],
            "command_prefixes": ["lmstudio "],
            "cost_per_hour": 0.05,
            "log_files": []
        },
    }


    @staticmethod
    def get_chrome_history_path():
        """Retourne chemin vers Chrome History selon OS"""
        import platform
        system = platform.system()
        
        if system == "Windows":
            return Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "User Data" / "Default" / "History"
        elif system == "Darwin":  # macOS
            return Path.home() / "Library" / "Application Support" / "Google" / "Chrome" / "Default" / "History"
        elif system == "Linux":
            return Path.home() / ".config" / "google-chrome" / "Default" / "History"
        
        return None
    
    @staticmethod
    def get_firefox_history_path():
        """Retourne chemin vers Firefox places.sqlite selon OS"""
        import platform
        system = platform.system()
        
        if system == "Windows":
            profile_dir = Path.home() / "AppData" / "Roaming" / "Mozilla" / "Firefox" / "Profiles"
        elif system == "Darwin":  # macOS
            profile_dir = Path.home() / "Library" / "Application Support" / "Firefox" / "Profiles"
        elif system == "Linux":
            profile_dir = Path.home() / ".mozilla" / "firefox"
        else:
            return None
        
        # Trouver premier profil .default-release
        if profile_dir.exists():
            for profile in profile_dir.iterdir():
                if profile.is_dir() and "default" in profile.name.lower():
                    places_db = profile / "places.sqlite"
                    if places_db.exists():
                        return places_db
        
        return None
    
    @staticmethod
    def get_safari_history_path():
        """Retourne chemin vers Safari History.db (macOS only)"""
        import platform
        if platform.system() == "Darwin":
            return Path.home() / "Library" / "Safari" / "History.db"
        return None
    
    def parse_chrome_history(self, since_hours: int = 1) -> List[Dict]:
        """
        Parse Chrome History database pour extraire visites domaines IA
        
        Args:
            since_hours: Ne garder que visites des N dernières heures
        
        Returns:
            Liste de dicts {domain, url, title, visit_time, visit_count}
        """
        history_path = self.get_chrome_history_path()
        if not history_path or not history_path.exists():
            return []
        
        # Copier DB dans temp (Chrome lock file sinon)
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        shutil.copy2(history_path, temp_db.name)
        
        try:
            conn = sqlite3.connect(temp_db.name)
            cursor = conn.cursor()
            
            # Chrome stocke last_visit_time en microseconds depuis 1601-01-01
            # Convertir en timestamp Unix
            chrome_epoch = datetime(1601, 1, 1)
            unix_epoch = datetime(1970, 1, 1)
            epoch_diff_seconds = (unix_epoch - chrome_epoch).total_seconds()
            
            # Timestamp depuis lequel filtrer (now - since_hours)
            cutoff_time = (datetime.now() - timedelta(hours=since_hours)).timestamp()
            chrome_cutoff = int((cutoff_time + epoch_diff_seconds) * 1e6)
            
            # Query : filtrer URLs contenant domaines IA
            ai_domain_conditions = " OR ".join([f"url LIKE '%{domain}%'" for domain in self.AI_DOMAINS.keys()])
            
            query = f"""
                SELECT url, title, visit_count, last_visit_time
                FROM urls
                WHERE ({ai_domain_conditions})
                  AND last_visit_time > ?
                ORDER BY last_visit_time DESC
            """
            
            cursor.execute(query, (chrome_cutoff,))
            rows = cursor.fetchall()
            
            results = []
            for row in rows:
                url, title, visit_count, last_visit_time_chrome = row
                
                # Convertir Chrome timestamp en datetime Python
                last_visit_seconds = (last_visit_time_chrome / 1e6) - epoch_diff_seconds
                visit_datetime = datetime.fromtimestamp(last_visit_seconds)
                
                # Extraire domaine
                from urllib.parse import urlparse
                domain = urlparse(url).netloc
                
                # Vérifier si domaine match (gérer www. etc)
                matched_domain = None
                for ai_domain in self.AI_DOMAINS.keys():
                    if ai_domain in domain:
                        matched_domain = ai_domain
                        break
                
                if matched_domain:
                    results.append({
                        "domain": matched_domain,
                        "url": url,
                        "title": title,
                        "visit_time": visit_datetime,
                        "visit_count": visit_count,
                        "browser": "chrome",
                        "cost_per_hour": self.AI_DOMAINS[matched_domain]["cost_per_hour"]
                    })
            
            conn.close()
            return results
        
        finally:
            # Cleanup temp file
            Path(temp_db.name).unlink(missing_ok=True)
    
    def parse_firefox_history(self, since_hours: int = 1) -> List[Dict]:
        """
        Parse Firefox places.sqlite pour extraire visites domaines IA
        
        Structure Firefox:
        - moz_places: id, url, title, visit_count, rev_host
        - moz_historyvisits: id, place_id, visit_date
        """
        history_path = self.get_firefox_history_path()
        if not history_path or not history_path.exists():
            return []
        
        # Copier DB dans temp
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".sqlite")
        shutil.copy2(history_path, temp_db.name)
        
        try:
            conn = sqlite3.connect(temp_db.name)
            cursor = conn.cursor()
            
            # Firefox stocke visit_date en microseconds depuis Unix epoch
            cutoff_time = (datetime.now() - timedelta(hours=since_hours)).timestamp()
            firefox_cutoff = int(cutoff_time * 1e6)
            
            ai_domain_conditions = " OR ".join([f"moz_places.url LIKE '%{domain}%'" for domain in self.AI_DOMAINS.keys()])
            
            query = f"""
                SELECT moz_places.url, moz_places.title, moz_historyvisits.visit_date
                FROM moz_historyvisits
                LEFT JOIN moz_places ON moz_historyvisits.place_id = moz_places.id
                WHERE ({ai_domain_conditions})
                  AND moz_historyvisits.visit_date > ?
                ORDER BY moz_historyvisits.visit_date DESC
            """
            
            cursor.execute(query, (firefox_cutoff,))
            rows = cursor.fetchall()
            
            results = []
            for row in rows:
                url, title, visit_date_micro = row
                
                visit_datetime = datetime.fromtimestamp(visit_date_micro / 1e6)
                
                from urllib.parse import urlparse
                domain = urlparse(url).netloc
                
                matched_domain = None
                for ai_domain in self.AI_DOMAINS.keys():
                    if ai_domain in domain:
                        matched_domain = ai_domain
                        break
                
                if matched_domain:
                    results.append({
                        "domain": matched_domain,
                        "url": url,
                        "title": title,
                        "visit_time": visit_datetime,
                        "visit_count": 1,  # Firefox visite = 1 entrée
                        "browser": "firefox",
                        "cost_per_hour": self.AI_DOMAINS[matched_domain]["cost_per_hour"]
                    })
            
            conn.close()
            return results
        
        finally:
            Path(temp_db.name).unlink(missing_ok=True)
    
    def parse_all_browsers(self, since_hours: int = 1) -> List[Dict]:
        """Parse tous navigateurs disponibles et agrège résultats"""
        all_visits = []
        
        # Chrome
        try:
            all_visits.extend(self.parse_chrome_history(since_hours))
        except Exception as e:
            print(f"Error parsing Chrome history: {e}")
        
        # Firefox
        try:
            all_visits.extend(self.parse_firefox_history(since_hours))
        except Exception as e:
            print(f"Error parsing Firefox history: {e}")
        
        # Safari (macOS uniquement)
        # TODO: implémenter parse_safari_history() similaire
        
        return all_visits
```

#### Calcul durée usage par domaine

**Logique** : Entre deux visites successives d'un même domaine, estimer durée de session

```python
from collections import defaultdict

def estimate_domain_usage_duration(visits: List[Dict], max_session_minutes: int = 30) -> Dict[str, float]:
    """
    Estime durée d'usage par domaine basé sur historique visites
    
    Args:
        visits: Liste visites triées par visit_time DESC
        max_session_minutes: Durée max session (au-delà = nouvelle session)
    
    Returns:
        Dict {domain: duration_hours}
    """
    # Trier par domain puis par temps (ASC)
    visits_sorted = sorted(visits, key=lambda x: (x["domain"], x["visit_time"]))
    
    domain_durations = defaultdict(float)  # en heures
    
    for i in range(len(visits_sorted) - 1):
        current = visits_sorted[i]
        next_visit = visits_sorted[i + 1]
        
        # Si même domaine
        if current["domain"] == next_visit["domain"]:
            time_diff = (next_visit["visit_time"] - current["visit_time"]).total_seconds()
            time_diff_minutes = time_diff / 60
            
            # Si < max_session_minutes, considérer comme même session
            if time_diff_minutes <= max_session_minutes:
                domain_durations[current["domain"]] += time_diff / 3600  # convert to hours
            else:
                # Session close, estimer 5 min par défaut
                domain_durations[current["domain"]] += 5 / 60
        else:
            # Changement domaine, estimer 5 min
            domain_durations[current["domain"]] += 5 / 60
    
    # Dernière visite : estimer 5 min
    if visits_sorted:
        last = visits_sorted[-1]
        domain_durations[last["domain"]] += 5 / 60
    
    return dict(domain_durations)
```

**Limitations** : Estimation imprécise (heuristique), ne capture pas temps réel exact. **Solution hybride** : combiner avec extension browser pour précision.

---

### Méthode 2 : Extension navigateur (précision maximale)

**Avantage** : Track temps réel exact sur chaque domaine, tab actif détecté précisément

#### Structure extension Chrome (Manifest V3)

**Fichier `manifest.json`** :
```json
{
  "manifest_version": 3,
  "name": "AI Cost Tracker",
  "version": "1.0.0",
  "description": "Track time spent on AI websites for personal cost monitoring",
  "permissions": [
    "tabs",
    "storage",
    "activeTab"
  ],
  "host_permissions": [
    "*://perplexity.ai/*",
    "*://chat.openai.com/*",
    "*://claude.ai/*",
    "*://bolt.new/*",
    "*://lovable.dev/*"
    // ... ajouter tous domaines IA
  ],
  "background": {
    "service_worker": "background.js",
    "type": "module"
  },
  "action": {
    "default_popup": "popup.html",
    "default_icon": {
      "16": "icons/icon16.png",
      "48": "icons/icon48.png",
      "128": "icons/icon128.png"
    }
  },
  "icons": {
    "16": "icons/icon16.png",
    "48": "icons/icon48.png",
    "128": "icons/icon128.png"
  }
}
```

**Fichier `background.js`** (service worker) :
```javascript
// Configuration domaines IA
const AI_DOMAINS = {
  "perplexity.ai": { category: "search", costPerHour: 0.10 },
  "chat.openai.com": { category: "conversational", costPerHour: 0.20 },
  "chatgpt.com": { category: "conversational", costPerHour: 0.20 },
  "claude.ai": { category: "conversational", costPerHour: 0.15 },
  "lovable.dev": { category: "code_generation", costPerHour: 0.30 },
  "bolt.new": { category: "code_generation", costPerHour: 0.25 },
  // ... ajouter tous
};

// État tracking
let currentActiveTab = null;
let currentDomain = null;
let sessionStartTime = null;
let domainStats = {}; // {domain: {totalSeconds, lastUpdate, sessions}}

// Charger stats depuis storage au démarrage
chrome.storage.local.get(['domainStats'], (result) => {
  if (result.domainStats) {
    domainStats = result.domainStats;
  }
});

// Détecte si URL correspond à domaine IA
function getAIDomain(url) {
  if (!url) return null;
  
  try {
    const urlObj = new URL(url);
    const hostname = urlObj.hostname;
    
    for (const domain in AI_DOMAINS) {
      if (hostname === domain || hostname.endsWith('.' + domain)) {
        return domain;
      }
    }
  } catch (e) {
    return null;
  }
  
  return null;
}

// Sauvegarder session en cours
function saveCurrentSession() {
  if (currentDomain && sessionStartTime) {
    const now = Date.now();
    const durationSeconds = (now - sessionStartTime) / 1000;
    
    if (!domainStats[currentDomain]) {
      domainStats[currentDomain] = {
        totalSeconds: 0,
        lastUpdate: now,
        sessions: 0,
        costPerHour: AI_DOMAINS[currentDomain].costPerHour
      };
    }
    
    domainStats[currentDomain].totalSeconds += durationSeconds;
    domainStats[currentDomain].lastUpdate = now;
    domainStats[currentDomain].sessions += 1;
    
    // Persister dans storage
    chrome.storage.local.set({ domainStats });
    
    console.log(`Saved session: ${currentDomain}, duration: ${durationSeconds.toFixed(1)}s`);
  }
}

// Démarrer nouvelle session
function startNewSession(tabId, url) {
  // Sauvegarder session précédente si existe
  saveCurrentSession();
  
  const domain = getAIDomain(url);
  
  if (domain) {
    currentActiveTab = tabId;
    currentDomain = domain;
    sessionStartTime = Date.now();
    
    console.log(`Started tracking: ${domain}`);
  } else {
    // Tab non-IA, reset
    currentActiveTab = null;
    currentDomain = null;
    sessionStartTime = null;
  }
}

// Événement : tab actif change
chrome.tabs.onActivated.addListener(async (activeInfo) => {
  const tab = await chrome.tabs.get(activeInfo.tabId);
  startNewSession(tab.id, tab.url);
});

// Événement : tab mise à jour (nouvelle URL)
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.url && tab.active) {
    startNewSession(tabId, changeInfo.url);
  }
});

// Événement : fenêtre change de focus
chrome.windows.onFocusChanged.addListener(async (windowId) => {
  if (windowId === chrome.windows.WINDOW_ID_NONE) {
    // Browser perdu focus, sauvegarder session
    saveCurrentSession();
    currentActiveTab = null;
    currentDomain = null;
    sessionStartTime = null;
  } else {
    // Browser regagne focus, démarrer tracking si tab IA
    const [tab] = await chrome.tabs.query({ active: true, windowId: windowId });
    if (tab) {
      startNewSession(tab.id, tab.url);
    }
  }
});

// Sauvegarder périodiquement (toutes les 30s)
setInterval(() => {
  if (currentDomain && sessionStartTime) {
    saveCurrentSession();
    // Redémarrer session pour continuer tracking
    sessionStartTime = Date.now();
  }
}, 30000);

// Export métriques vers agent Python (via Native Messaging ou HTTP local)
// TODO: implémenter Native Messaging host ou simple HTTP POST vers localhost:8080
function exportMetricsToAgent() {
  // Exemple : HTTP POST
  fetch('http://localhost:8080/metrics/browser', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      browser: 'chrome',
      timestamp: Date.now(),
      domains: domainStats
    })
  }).catch(err => console.log('Agent unavailable:', err));
}

// Exporter toutes les 60s
setInterval(exportMetricsToAgent, 60000);
```

**Fichier `popup.html`** (UI stats) :
```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>AI Cost Tracker</title>
  <style>
    body {
      width: 400px;
      padding: 16px;
      font-family: system-ui, -apple-system, sans-serif;
    }
    h2 {
      margin-top: 0;
      font-size: 18px;
    }
    .domain-row {
      display: flex;
      justify-content: space-between;
      padding: 8px 0;
      border-bottom: 1px solid #eee;
    }
    .domain-name {
      font-weight: 500;
    }
    .domain-time {
      color: #666;
    }
    .domain-cost {
      color: #0066cc;
      font-weight: 600;
    }
    .total {
      margin-top: 16px;
      padding-top: 16px;
      border-top: 2px solid #333;
      display: flex;
      justify-content: space-between;
      font-size: 16px;
      font-weight: 600;
    }
  </style>
</head>
<body>
  <h2>AI Usage Today</h2>
  <div id="domains"></div>
  <div class="total">
    <span>Total Cost:</span>
    <span id="totalCost">$0.00</span>
  </div>
  
  <script src="popup.js"></script>
</body>
</html>
```

**Fichier `popup.js`** :
```javascript
// Charger et afficher stats
chrome.storage.local.get(['domainStats'], (result) => {
  const domainStats = result.domainStats || {};
  const domainsDiv = document.getElementById('domains');
  const totalCostSpan = document.getElementById('totalCost');
  
  let totalCost = 0;
  
  // Filtrer seulement aujourd'hui (lastUpdate < 24h)
  const now = Date.now();
  const oneDayAgo = now - (24 * 60 * 60 * 1000);
  
  for (const [domain, stats] of Object.entries(domainStats)) {
    if (stats.lastUpdate > oneDayAgo) {
      const hours = stats.totalSeconds / 3600;
      const cost = hours * stats.costPerHour;
      totalCost += cost;
      
      const row = document.createElement('div');
      row.className = 'domain-row';
      row.innerHTML = `
        <span class="domain-name">${domain}</span>
        <span class="domain-time">${(hours * 60).toFixed(0)} min</span>
        <span class="domain-cost">$${cost.toFixed(2)}</span>
      `;
      domainsDiv.appendChild(row);
    }
  }
  
  totalCostSpan.textContent = `$${totalCost.toFixed(2)}`;
});
```

#### Native Messaging (extension → agent Python)

**Avantage** : Communication bidirectionnelle extension ↔ agent Python natif

**Manifest ajout** :
```json
{
  "permissions": [
    "nativeMessaging"
  ]
}
```

**Host manifest (JSON installé système)** `com.ai_cost_observer.native_host.json` :

*macOS/Linux* : `/Library/Application Support/Google/Chrome/NativeMessagingHosts/` (macOS) ou `~/.config/google-chrome/NativeMessagingHosts/` (Linux)

*Windows* : Registry key `HKEY_CURRENT_USER\Software\Google\Chrome\NativeMessagingHosts\com.ai_cost_observer.native_host`

```json
{
  "name": "com.ai_cost_observer.native_host",
  "description": "AI Cost Observer Native Messaging Host",
  "path": "/path/to/native_messaging_host.py",
  "type": "stdio",
  "allowed_origins": [
    "chrome-extension://YOUR_EXTENSION_ID/"
  ]
}
```

**Script Python `native_messaging_host.py`** :
```python
#!/usr/bin/env python3
"""
Native Messaging Host pour recevoir métriques depuis extension browser
"""
import sys
import json
import struct

def send_message(message_dict):
    """Envoie message JSON vers extension"""
    message_json = json.dumps(message_dict)
    message_bytes = message_json.encode('utf-8')
    sys.stdout.buffer.write(struct.pack('I', len(message_bytes)))
    sys.stdout.buffer.write(message_bytes)
    sys.stdout.buffer.flush()

def read_message():
    """Lit message JSON depuis extension"""
    # Lire 4 bytes (length)
    text_length_bytes = sys.stdin.buffer.read(4)
    if not text_length_bytes:
        return None
    
    text_length = struct.unpack('i', text_length_bytes)[0]
    text = sys.stdin.buffer.read(text_length).decode('utf-8')
    return json.loads(text)

def main():
    # Intégrer ici logique agent Python (ou importer module)
    # Pour démo, juste logger message
    while True:
        message = read_message()
        if message is None:
            break
        
        # Traiter message (domainStats depuis extension)
        # TODO: exporter vers OpenTelemetry
        
        # Répondre à extension
        send_message({"status": "ok", "received": True})

if __name__ == "__main__":
    main()
```

---

### Méthode 3 : Monitoring process browser + détection fenêtre active

**Principe** : Surveiller process browser, déterminer si actif (fenêtre foreground), estimer usage si combiné avec patterns réseau

**Code Python** :
```python
import psutil

def detect_active_browser_process():
    """Détecte quel browser process est actif (foreground)"""
    browser_processes = ["chrome.exe", "firefox.exe", "msedge.exe", "Safari", "Google Chrome", "firefox"]
    
    # Récupérer fenêtre active (OS-specific, voir section précédente)
    active_proc_name = get_active_window_process()  # implémenté précédemment
    
    if active_proc_name in browser_processes:
        # Browser actif, mais quel domaine ?
        # → Nécessite parsing historique ou extension
        return active_proc_name
    
    return None
```

**Limitation** : Ne donne pas domaine actif, seulement "browser running". **Combiner avec** parsing historique SQLite pour enrichir.

---

### Méthode 4 : Détection en temps réel des CLI (psutil)

À côté du monitor desktop, ajoute un monitor CLI :

```python
@dataclass
class CLICallSnapshot:
    cli_name: str
    pid: int
    process_name: str
    cmdline: str
    cpu_percent: float
    memory_mb: float
    timestamp: float = field(default_factory=time.time)


class AICLIMonitor:
    def __init__(self):
        self.tracked_pids: Dict[int, Dict] = {}  # pid -> {cli_name, start_time, last_snapshot, cumulative_active_seconds, cumulative_cost}

    def scan_cli_processes(self) -> List[CLICallSnapshot]:
        snapshots: List[CLICallSnapshot] = []

        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cpu_percent', 'memory_info']):
            try:
                name = proc.info['name']
                cmdline_list = proc.info.get('cmdline') or []
                cmdline = " ".join(cmdline_list)

                for cli_name, cfg in AI_CLI_CONFIG.items():
                    if name in cfg["process_names"] or any(
                        cmdline.startswith(p) or f" {p}" in cmdline
                        for p in cfg["command_prefixes"]
                    ):
                        snapshots.append(
                            CLICallSnapshot(
                                cli_name=cli_name,
                                pid=proc.info['pid'],
                                process_name=name,
                                cmdline=cmdline,
                                cpu_percent=proc.info['cpu_percent'] or 0.0,
                                memory_mb=proc.info['memory_info'].rss / (1024 * 1024),
                            )
                        )
                        break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return snapshots

    def update_cli_metrics(self, snapshots: List[CLICallSnapshot], interval_seconds: float):
        # PIDs en cours
        current_pids = {s.pid: s for s in snapshots}

        # PIDs stoppés
        stopped_pids = set(self.tracked_pids.keys()) - set(current_pids.keys())
        for pid in stopped_pids:
            info = self.tracked_pids[pid]
            labels = {
                "cli.name": info["cli_name"],
                "cli.pid": str(pid),
            }
            ai_cli_running.add(-1, labels)
            del self.tracked_pids[pid]

        # PIDs actifs
        for snap in snapshots:
            labels = {
                "cli.name": snap.cli_name,
                "cli.pid": str(snap.pid),
            }

            if snap.pid not in self.tracked_pids:
                self.tracked_pids[snap.pid] = {
                    "cli_name": snap.cli_name,
                    "start_time": snap.timestamp,
                    "last_snapshot": snap,
                    "cumulative_active_seconds": 0.0,
                    "cumulative_cost": 0.0,
                }
                ai_cli_running.add(1, labels)

            info = self.tracked_pids[snap.pid]

            # On considère qu’un process CLI actif = usage actif pendant tout l’intervalle
            info["cumulative_active_seconds"] += interval_seconds
            ai_cli_active_duration.add(interval_seconds, labels)

            # Coût
            cfg = AI_CLI_CONFIG[snap.cli_name]
            cost_inc = (interval_seconds / 3600.0) * cfg["cost_per_hour"]
            info["cumulative_cost"] += cost_inc
            ai_cli_estimated_cost.add(cost_inc, labels)

            # CPU / mémoire instantanés
            ai_cli_cpu_usage.record(snap.cpu_percent, labels)
            ai_cli_memory_usage.record(snap.memory_mb, labels)

            info["last_snapshot"] = snap
```

Dans ta boucle principale, ajoute :

```python
cli_monitor = AICLIMonitor()

# Dans la loop principale:
cli_snapshots = cli_monitor.scan_cli_processes()
cli_monitor.update_cli_metrics(cli_snapshots, interval_seconds=scan_interval)
```

### Historique shell (zsh/bash) pour compter les commandes IA

Ajoute une tâche secondaire dans l’agent :

```python
def parse_shell_history(paths=None) -> Dict[str, int]:
"""
Parcourt les historiques shell et compte les commandes CLI IA.
paths: liste de fichiers history à inspecter
"""
if paths is None:
paths = [
"~/.zsh_history",
"~/.bash_history",
# Ajouter d’autres shells si besoin
]

    counts = {name: 0 for name in AI_CLI_CONFIG.keys()}

    for raw_path in paths:
        path = os.path.expanduser(raw_path)
        if not os.path.exists(path):
            continue

        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    # zsh peut avoir format ": timestamp:flags;command"
                    if ";" in line:
                        _, cmd = line.split(";", 1)
                    else:
                        cmd = line
                    cmd = cmd.strip()

                    for cli_name, cfg in AI_CLI_CONFIG.items():
                        if any(cmd.startswith(p) for p in cfg["command_prefixes"]):
                            counts[cli_name] += 1
        except Exception as e:
            logger.warning(f"Error parsing history {path}: {e}")

    return counts


def export_cli_command_counts():
counts = parse_shell_history()
for cli_name, n in counts.items():
if n > 0:
ai_cli_command_count.add(
n,
{
"cli.name": cli_name,
"source": "shell_history",
},
)
```

Lance ça dans un thread:

```python
def cli_history_loop():
while True:
export_cli_command_counts()
time.sleep(3600)  # 1 fois par heure

threading.Thread(target=cli_history_loop, daemon=True).start()
```

## MÉTRIQUES OPENTELEMETRY CUSTOM

### Structure des métriques (semantic conventions adaptées)

```python
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.resources import Resource

# Configuration OpenTelemetry
resource = Resource.create({
    "service.name": "ai-cost-observer",
    "service.version": "2.0.0",  # v2 avec support browser
    "deployment.environment": "personal",
    "host.name": socket.gethostname(),
    "os.type": platform.system().lower()
})

exporter = OTLPMetricExporter(
    endpoint="http://localhost:4317",
    insecure=True
)

reader = PeriodicExportingMetricReader(
    exporter,
    export_interval_millis=15000  # Export toutes les 15s
)

provider = MeterProvider(resource=resource, metric_readers=[reader])
metrics.set_meter_provider(provider)

meter = metrics.get_meter("ai-cost-observer")

# Métriques DESKTOP APPS (existantes)
ai_app_running = meter.create_up_down_counter(
    name="ai.app.running",
    description="Whether AI desktop app is currently running (1) or not (0)",
    unit="1"
)

ai_app_active_duration = meter.create_counter(
    name="ai.app.active.duration",
    description="Total time AI app was actively used (foreground)",
    unit="s"
)

# ... autres métriques desktop (voir prompt précédent)

# Métriques BROWSER AI USAGE (nouvelles)
ai_browser_domain_active_duration = meter.create_counter(
    name="ai.browser.domain.active.duration",
    description="Total time spent actively on AI domain in browser",
    unit="s"
)

ai_browser_domain_visit_count = meter.create_counter(
    name="ai.browser.domain.visit.count",
    description="Number of visits to AI domain",
    unit="1"
)

ai_browser_domain_estimated_cost = meter.create_counter(
    name="ai.browser.domain.estimated.cost",
    description="Estimated cost in USD for browser AI usage",
    unit="USD"
)

ai_browser_active = meter.create_up_down_counter(
    name="ai.browser.active",
    description="Whether browser with AI domain is currently active (1=yes, 0=no)",
    unit="1"
)

# Métriques CLI IA

ai_cli_running = meter.create_up_down_counter(
    name="ai.cli.running",
    description="Whether AI CLI process is currently running (1) or not (0)",
    unit="1",
)

ai_cli_active_duration = meter.create_counter(
    name="ai.cli.active.duration",
    description="Total time AI CLI was running (approx active usage)",
    unit="s",
)

ai_cli_cpu_usage = meter.create_histogram(
    name="ai.cli.cpu.usage",
    description="CPU usage percentage of AI CLI",
    unit="%",
)

ai_cli_memory_usage = meter.create_histogram(
    name="ai.cli.memory.usage",
    description="Memory usage of AI CLI process",
    unit="MB",
)

ai_cli_estimated_cost = meter.create_counter(
    name="ai.cli.estimated.cost",
    description="Estimated cost in USD for AI CLI usage",
    unit="USD",
)

ai_cli_command_count = meter.create_counter(
    name="ai.cli.command.count",
    description="Number of AI CLI commands executed (from shell history)",
    unit="1",
)


# Labels communs browser metrics:
# - browser.name : "chrome", "firefox", "safari", "edge", etc.
# - ai.domain : "perplexity.ai", "chat.openai.com", etc.
# - ai.category : "search", "conversational", "code_generation", etc.
# - usage.type : "active" (tab focused) ou "background" (tab open but not focused)
```

### Logique d'export métriques browser

**Depuis extension (via Native Messaging ou HTTP)** :
```python
# Dans agent Python

from flask import Flask, request
import threading

app = Flask(__name__)

@app.route('/metrics/browser', methods=['POST'])
def receive_browser_metrics():
    """Endpoint pour recevoir métriques depuis extension browser"""
    data = request.json
    
    browser = data.get('browser', 'unknown')
    timestamp = data.get('timestamp')
    domains = data.get('domains', {})
    
    for domain, stats in domains.items():
        total_seconds = stats['totalSeconds']
        cost_per_hour = stats['costPerHour']
        
        # Labels
        labels = {
            "browser.name": browser,
            "ai.domain": domain,
            "ai.category": AI_DOMAINS.get(domain, {}).get("category", "unknown")
        }
        
        # Exporter métriques OTel
        ai_browser_domain_active_duration.add(total_seconds, labels)
        
        # Calculer coût
        hours = total_seconds / 3600
        cost = hours * cost_per_hour
        ai_browser_domain_estimated_cost.add(cost, labels)
        
        ai_browser_domain_visit_count.add(stats.get('sessions', 1), labels)
    
    return {"status": "ok"}, 200

# Lancer serveur Flask dans thread
def start_metrics_server():
    app.run(host='127.0.0.1', port=8080, debug=False)

metrics_thread = threading.Thread(target=start_metrics_server, daemon=True)
metrics_thread.start()
```

**Depuis parsing historique SQLite** :
```python
# Dans boucle monitoring agent

def monitor_browser_history():
    """Parse historique navigateurs périodiquement et exporte métriques"""
    parser = BrowserHistoryParser()
    
    while True:
        # Parser historique dernière heure
        visits = parser.parse_all_browsers(since_hours=1)
        
        # Estimer durées par domaine
        durations = estimate_domain_usage_duration(visits, max_session_minutes=30)
        
        # Exporter métriques
        for domain, hours in durations.items():
            config = parser.AI_DOMAINS.get(domain, {})
            cost_per_hour = config.get("cost_per_hour", 0)
            category = config.get("category", "unknown")
            
            # Détecter browser depuis visits
            browser_visits = [v for v in visits if v["domain"] == domain]
            browser = browser_visits[0]["browser"] if browser_visits else "unknown"
            
            labels = {
                "browser.name": browser,
                "ai.domain": domain,
                "ai.category": category,
                "usage.type": "estimated"  # car parsing historique, pas temps réel
            }
            
            seconds = hours * 3600
            ai_browser_domain_active_duration.add(seconds, labels)
            
            cost = hours * cost_per_hour
            ai_browser_domain_estimated_cost.add(cost, labels)
        
        # Attendre 60s avant prochain scan
        time.sleep(60)

# Lancer monitoring browser history dans thread
browser_thread = threading.Thread(target=monitor_browser_history, daemon=True)
browser_thread.start()
```

---

## DASHBOARDS GRAFANA (ENRICHIS AVEC BROWSER USAGE)

### Dashboard 1 : AI Cost Overview (mise à jour)

**Panels ajoutés** :

7. **Browser AI Usage Breakdown (Today)** - Pie chart
   - Query : `sum by (ai_domain) (increase(ai_cost_ai_browser_domain_active_duration_total{usage_type="active"}[1d])) / 3600`
   - Affiche heures par domaine IA web (perplexity, claude.ai, bolt.new, etc.)

8. **Browser vs Desktop Cost Comparison (30 days)** - Bar gauge
   - Query desktop : `sum(increase(ai_cost_ai_app_estimated_cost_total[30d]))`
   - Query browser : `sum(increase(ai_cost_ai_browser_domain_estimated_cost_total[30d]))`
   - Compare coûts desktop apps vs browser usage

9. **Top 5 AI Domains (Browser)** - Table
   - Query : `topk(5, sum by (ai_domain) (increase(ai_cost_ai_browser_domain_active_duration_total[7d])))`
   - Affiche domaines les plus utilisés derniers 7 jours

### Dashboard 2 : Browser AI Usage Details (nouveau)

**Variables** :
- `$browser` : dropdown (chrome, firefox, edge, safari)
- `$ai_category` : dropdown (search, conversational, code_generation, image_generation)
- `$time_range` : interval picker

**Panels** :

1. **Active Browser Sessions Timeline** - State timeline
   - Query : `ai_cost_ai_browser_active{browser_name="$browser"}`
   - Affiche périodes où browser avec domaine IA était actif

2. **Usage by AI Category** - Stacked time series
   - Query per category : `sum by (ai_category) (rate(ai_cost_ai_browser_domain_active_duration_total{browser_name="$browser"}[5m]))`
   - Affiche tendances usage par catégorie (search vs conversational vs code gen)

3. **Cost Rate by Domain** - Table
   - Columns : Domain | Time (hours) | Visits | Cost (USD)
   - Query time : `sum by (ai_domain) (increase(ai_cost_ai_browser_domain_active_duration_total{browser_name="$browser"}[$time_range])) / 3600`
   - Query visits : `sum by (ai_domain) (increase(ai_cost_ai_browser_domain_visit_count_total{browser_name="$browser"}[$time_range]))`
   - Query cost : `sum by (ai_domain) (increase(ai_cost_ai_browser_domain_estimated_cost_total{browser_name="$browser"}[$time_range]))`

4. **Hourly Usage Pattern** - Heatmap
   - Query : `sum by (hour) (increase(ai_cost_ai_browser_domain_active_duration_total{browser_name="$browser"}[1h]))`
   - Affiche patterns horaires (quand j'utilise le plus l'IA web)

5. **Domain Deep Dive** - Time series multi-axis
   - Y-axis left : durée active (minutes)
   - Y-axis right : coût cumulé (USD)
   - Query duration : `increase(ai_cost_ai_browser_domain_active_duration_total{ai_domain=~"$ai_domain"}[1h]) / 60`
   - Query cost : `increase(ai_cost_ai_browser_domain_estimated_cost_total{ai_domain=~"$ai_domain"}[1h])`

### Dashboard 3 : Unified AI Cost (desktop + browser)

**Panel principal : Total Monthly Cost Breakdown** - Pie chart avec drill-down

Query :
```promql
# Desktop apps cost
sum(increase(ai_cost_ai_app_estimated_cost_total[30d])) by (app_name)

# Browser domains cost
sum(increase(ai_cost_ai_browser_domain_estimated_cost_total[30d])) by (ai_domain)

#CLI IA Cost Breakdown (30 days) - Bar chart
sum(increase(ai_cost_ai_cli_estimated_cost_total[30d])) by (cli_name)

#CLI Usage (commands / day) – Time series
sum by (cli_name) (increase(ai_cost_ai_cli_command_count_total[1d]))

#Desktop vs Browser vs CLI Cost – Pie chart
Desktop : sum(increase(ai_cost_ai_app_estimated_cost_total[30d]))
Browser : sum(increase(ai_cost_ai_browser_domain_estimated_cost_total[30d]))
CLI : sum(increase(ai_cost_ai_cli_estimated_cost_total[30d]))
```

Combine les trois sources dans même visualisation avec labels distincts.
Tu peux ajouter un label category (desktop/browser/cli) côté agent pour simplifier.

---

## PLAN D'IMPLÉMENTATION GRANULAIRE (MIS À JOUR)

### Étape 1 : Setup infrastructure observabilité locale
*(Inchangé, voir prompt précédent)*

### Étape 2 : Agent Python - Détection process desktop IA basique
*(Inchangé, voir prompt précédent)*

### Étape 3 : Intégration OpenTelemetry SDK - Export métriques basiques desktop
*(Inchangé, voir prompt précédent)*

### Étape 4 : Détection fenêtre active OS-specific desktop
*(Inchangé, voir prompt précédent)*

### Étape 5 : Parser historique browser (SQLite) - Première version (Vérifiable : domaines IA détectés dans logs)

**Objectif** : Agent Python parse Chrome/Firefox History.db, détecte visites domaines IA

**Actions** :
1. Implémenter `BrowserHistoryParser` classe avec méthodes pour Chrome, Firefox, Safari
2. Ajouter config `AI_DOMAINS` avec tous domaines du tableau (Perplexity, Lovable, Bolt, etc.)
3. Dans boucle monitoring, appeler `parse_all_browsers(since_hours=1)` toutes les 60s
4. Logger domaines IA détectés avec timestamps

**Critères validation** :
- [ ] Agent log affiche : "Parsed Chrome history: 5 AI visits found"
- [ ] Domaines détectés corrects (perplexity.ai, claude.ai, etc.)
- [ ] Timestamps visites cohérents (dernières heures)
- [ ] Fonctionne sur Windows ET macOS (tester chemins paths)

### Étape 6 : Estimer durées usage par domaine browser (Vérifiable : durées calculées cohérentes)

**Objectif** : Calculer durée estimée session par domaine IA web

**Actions** :
1. Implémenter fonction `estimate_domain_usage_duration(visits, max_session_minutes=30)`
2. Logique : delta entre visites successives même domaine < 30min = même session
3. Logger durées estimées par domaine

**Critères validation** :
- [ ] Durées calculées raisonnables (ex: 0.5h pour 30min usage Perplexity)
- [ ] Sessions multiples même domaine agrégées correctement
- [ ] Max session cap respecté (pas de sessions > 30min entre visites espacées)

### Étape 7 : Export métriques browser vers OpenTelemetry (Vérifiable : métriques browser dans Prometheus)

**Objectif** : Métriques usage browser AI visibles dans Prometheus

**Actions** :
1. Créer instruments OTel : `ai.browser.domain.active.duration`, `ai.browser.domain.estimated.cost`, etc.
2. Dans boucle monitoring browser history, exporter métriques avec labels (browser, domain, category)
3. Vérifier export OTLP fonctionne

**Critères validation** :
- [ ] Prometheus affiche métriques : `{__name__=~"ai_cost_ai_browser.*"}`
- [ ] Labels `browser_name`, `ai_domain`, `ai_category` présents
- [ ] Valeurs cohérentes avec durées calculées Étape 6
- [ ] Métriques s'accumulent au fil du temps (counter increment)

### Étape 8 : Extension browser Chrome - Tracking temps réel (Vérifiable : extension installée, stats visibles)

**Objectif** : Extension Chrome track temps réel sur domaines IA, affiche stats dans popup

**Actions** :
1. Créer structure extension : manifest.json, background.js, popup.html, popup.js
2. Implémenter tracking tab actif, détection domaines IA, calcul durée
3. Persister stats dans `chrome.storage.local`
4. Tester : installer unpacked extension, naviguer perplexity.ai 5min, vérifier popup affiche durée

**Critères validation** :
- [ ] Extension installée sans erreur dans chrome://extensions
- [ ] Popup affiche domaines IA visités aujourd'hui avec temps + coût estimé
- [ ] Durées augmentent en temps réel quand tab IA actif
- [ ] Stats persistent après redémarrage Chrome (storage.local fonctionne)

### Étape 9 : Extension browser - Export vers agent Python (Vérifiable : agent reçoit métriques extension)

**Objectif** : Extension envoie métriques vers agent Python (HTTP ou Native Messaging)

**Actions** :
1. Implémenter endpoint Flask `/metrics/browser` dans agent Python
2. Dans background.js extension, ajouter `exportMetricsToAgent()` POST HTTP localhost:8080
3. Exporter toutes les 60s
4. Dans agent, recevoir données et exporter vers OTel

**Critères validation** :
- [ ] Agent log affiche : "Received browser metrics from chrome: 3 domains"
- [ ] Métriques browser apparaissent dans Prometheus avec source "chrome"
- [ ] Durées extension > durées parsing historique (preuve que temps réel > estimation)
- [ ] Pas d'erreur réseau si agent down (extension handle gracefully)

### Étape 10 : Dashboard Grafana - Browser AI Usage (Vérifiable : dashboard fonctionnel)

**Objectif** : Dashboard "Browser AI Usage Details" affiche métriques browser

**Actions** :
1. Créer JSON dashboard `browser-ai-usage-details.json` avec 5 panels
2. Variables `$browser`, `$ai_category`
3. Provisionner dans Grafana
4. Tester avec données réelles (naviguer plusieurs domaines IA, vérifier dashboard update)

**Critères validation** :
- [ ] Dashboard visible Grafana, dropdown `$browser` liste browsers détectés
- [ ] Panel "Usage by AI Category" affiche courbes par catégorie
- [ ] Panel "Cost Rate by Domain" table affiche domaines + coûts
- [ ] Données temps-réel (auto-refresh 30s)
- [ ] Drill-down domaine spécifique fonctionne

### Étape 11 : Dashboard Unified AI Cost (desktop + browser) (Vérifiable : comparaison desktop vs browser)

**Objectif** : Dashboard unifié compare coûts desktop apps vs browser AI

**Actions** :
1. Créer dashboard JSON avec panel "Total Cost Breakdown" (pie chart)
2. Query combine `ai_app_estimated_cost` + `ai_browser_domain_estimated_cost`
3. Labels distinctes pour desktop vs browser

**Critères validation** :
- [ ] Pie chart affiche % coût desktop vs browser
- [ ] Si utilisation intensive browser (ex: Perplexity 2h/jour), coût browser visible significatif
- [ ] Total cost match somme coûts individuels desktop + browser

### Étape 12 : Tests end-to-end complets (Vérifiable : scénarios validés)

**Objectif** : Validation pipeline complète desktop + browser

**Scénarios** :
1. **Desktop app uniquement** : Utiliser ChatGPT Desktop 15min, vérifier coût $0.05 dans Grafana
2. **Browser uniquement** : Naviguer Perplexity 30min + Bolt.new 20min, vérifier coûts séparés
3. **Mixte** : Alterner ChatGPT Desktop 10min, puis Claude web 10min, vérifier les 2 sources distinctes
4. **Multi-browser** : Utiliser Chrome 20min claude.ai, puis Firefox 15min perplexity.ai, vérifier stats séparées par browser
5. **Extension crash recovery** : Désactiver extension, réactiver, vérifier stats persistent

**Critères validation** :
- [ ] Tous scénarios donnent métriques attendues ±10%
- [ ] Aucune duplication comptage (desktop + browser même service ne comptent pas 2x)
- [ ] Grafana dashboards exploitables pour décisions (identifier service le + coûteux)

### Étape 13 : Documentation utilisateur complète (Vérifiable : README exploitable)

**Actions** :
1. Rédiger README.md : prérequis, installation agent + extension, configuration, troubleshooting
2. Screenshots Grafana dashboards
3. FAQ : "Pourquoi coût estimé ≠ facture réelle ?", "Comment ajouter nouveau domaine IA ?", etc.

**Critères validation** :
- [ ] Utilisateur non-technique peut suivre README pour installer stack complète
- [ ] Troubleshooting couvre cas fréquents (agent ne démarre pas, extension ne track pas, etc.)

### Étape 14 : (CLI-1) Détection process CLI IA (Vérifiable : CLI détectées dans logs)

Objectif : L’agent voit quand Claude Code, Gemini CLI, etc. tournent.

Actions :
- Ajouter `AI_CLI_CONFIG`
- Implémenter `AICLIMonitor.scan_cli_processes()` et `update_cli_metrics()`
- Loguer les CLI vues à chaque scan

Critères validation :
- [ ] Lancer `cc` ou `claude-code` dans un terminal → logs affichent `Claude Code CLI running (PID X)`
- [ ] Les métriques `ai_cost_ai_cli_running` apparaissent dans Prometheus

---

### Étape 15 : (CLI-2) Historique shell → command.count (Vérifiable : nb de commandes IA par jour)

Objectif : Compter combien de commandes IA tu tapes (cc, gemini, mistral, …).

Actions :
- Implémenter `parse_shell_history()` et `export_cli_command_counts()`
- Lancer boucle `cli_history_loop` toutes les heures

Critères validation :
- [ ] `ai_cost_ai_cli_command_count_total` montre des valeurs >0
- [ ] En ajoutant manuellement des commandes `cc ...` dans .zsh_history, le compteur augmente

---

### Étape 16 : (CLI-3) (Optionnel) Ingestion usage natif Claude Code (ccusage / JSONL)

Objectif : Avoir une mesure très fine de l’usage Claude Code (durées, projets).

Actions :
- Installer `ccusage` ou `claude-code-usage` si disponible
- Ajouter une fonction `ingest_claude_code_usage()` qui :
    - appelle `ccusage --json`
    - agrège `duration_sec` par jour/projet
    - exporte vers `ai.cli.active.duration` + `ai.cli.estimated.cost` avec labels `project`

Critères validation :
- [ ] Les durées/ coûts Claude Code issues de `ccusage` matchent (±10%) ce que montre ton pipeline OTel
- [ ] Les labels `project` apparaissent dans Grafana (filtre par projet Claude Code)


---

## VALIDATION OPENTELEMETRY COMME OUTIL

*(Inchangé, voir prompt précédent - toujours valide pour desktop + browser)*

**Conclusion** : OpenTelemetry reste le bon choix, car :
- Support custom metrics Python SDK mature
- Peut ingérer métriques depuis multiples sources (agent Python + extension browser)
- OTel Collector agrège tout uniformément
- Export Prometheus + Grafana pour visualisation riche

---

## SOURCES & RÉFÉRENCES COMPLÉMENTAIRES (BROWSER)

- **Chrome Extensions Manifest V3** : chrome.tabs API, activeTab permission[web:199][web:201][web:208]
- **Browser History SQLite** : Chrome/Firefox/Safari schemas, query patterns[web:203][web:206][web:209][web:212]
- **Browser Time Tracking Extensions** : Web Activity Time Tracker, Webtime Tracker, TimeSpy (exemples open-source)[web:169][web:170][web:173][web:176]
- **Native Messaging** : Communication extension ↔ native app[web:177]
- **DNS Monitoring** : DNS filtering, domain resolution pour tracking réseau[web:175][web:178][web:181]

---

## TROUBLESHOOTING & FAQ (MIS À JOUR)

### Problème : Agent ne détecte pas visites browser AI

**Causes** :
1. Chemin historique browser incorrect (OS/version différente)
2. Browser non supporté (ex: Opera, Arc)
3. Historique vide (mode incognito, historique désactivé)

**Debug** :
```python
# Vérifier chemins
parser = BrowserHistoryParser()
print(f"Chrome path: {parser.get_chrome_history_path()}")
print(f"Firefox path: {parser.get_firefox_history_path()}")
print(f"Exists: {parser.get_chrome_history_path().exists()}")

# Tester query direct
import sqlite3
conn = sqlite3.connect(parser.get_chrome_history_path())
cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) FROM urls")
print(f"Total URLs in history: {cursor.fetchone()[0]}")
```

### Problème : Extension browser ne track pas temps

**Causes** :
1. Permissions manquantes (tabs, storage, activeTab)
2. Domaine IA pas dans `AI_DOMAINS` config
3. Service worker background.js crashé

**Debug** :
1. Aller chrome://extensions, vérifier "Errors" extension
2. Inspecter service worker : click "Inspect views: service worker"
3. Console logs : vérifier messages "Started tracking: [domain]"
4. Storage : chrome.storage.local, vérifier clé `domainStats` existe

### Problème : Durées estimées incohérentes (trop hautes)

**Causes** :
- Max session duration trop élevé (30min par défaut)
- Historique contient anciennes visites (since_hours trop grand)

**Solutions** :
1. Réduire `max_session_minutes` à 15 ou 20
2. Filtrer `since_hours=0.5` (dernières 30min) pour tests
3. Vérifier timestamps visites dans logs

### Problème : Métriques browser dupliquées (extension + historique)

**Causes** :
- Extension ET parser historique exportent même usage

**Solutions** :
1. Désactiver parsing historique si extension active : flag dans config agent
2. Utiliser labels `usage_source` : "extension" vs "history_parser"
3. Dashboard Grafana filter par `usage_source="extension"` (plus précis)

---

## CONCLUSION

Tu disposes maintenant du **prompt complet et exhaustif** pour construire l'agent d'observabilité IA incluant **apps desktop ET usage browser web**.

**Capacités finales** :
✅ Tracking apps desktop (ChatGPT Desktop, Claude, Cursor, etc.)  
✅ Tracking usage browser AI (Perplexity, Lovable, Bolt, ChatGPT web, etc.)  
✅ Support multi-browser (Chrome, Firefox, Edge, Safari)  
✅ Extension browser Chrome (Manifest V3) pour tracking temps réel  
✅ Parsing historique SQLite (Chrome/Firefox/Safari) en fallback  
✅ Métriques OpenTelemetry unifiées (desktop + browser)  
✅ Dashboards Grafana complets (cost overview, browser details, unified view)  
✅ Cross-platform (Windows + macOS)  
✅ Privacy-first (données locales uniquement, pas de contenu prompts)

**Architecture recommandée finale** :
1. **Agent Python** : monitoring continu desktop apps + parsing historique browser (60s interval)
2. **Extension Chrome** (optionnel mais recommandé) : tracking temps réel précis browser
3. **Stack Docker Compose** : OTel Collector + Prometheus + Grafana
4. **3 Dashboards Grafana** : AI Cost Overview, Browser AI Usage Details, Unified AI Cost

**Prochaines étapes** : Commence par Étape 1-4 (desktop apps), puis Étape 5-7 (browser history parsing), puis Étape 8-9 (extension) si besoin précision maximale.

Bonne implémentation ! 🚀
