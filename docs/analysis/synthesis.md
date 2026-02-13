# Synthese Croisee — Analyse LiteLLM pour Companion

> Sources: Gemini CLI, Codex CLI (gpt-5.3-codex), Vibe CLI
> Methode: Plus un point revient dans les 3 analyses, plus il est prioritaire (3/3 = P0, 2/3 = P1, 1/3 = P2)

---

## 1. Ce que LiteLLM fait deja (consensus 3/3)

| Domaine | Description | Fichiers cles |
|---------|-------------|---------------|
| **Proxy/Gateway** | API unifiee OpenAI-compatible (FastAPI), routes `/v1/chat/completions`, `/v1/embeddings`, passthrough multi-provider | `litellm/proxy/proxy_server.py`, `pass_through_endpoints/` |
| **100+ Modeles** | OpenAI, Azure, Anthropic, Bedrock, VertexAI, Groq, Cohere, Ollama, vLLM... | `litellm/llms/*.py`, `model_prices_and_context_window.json` |
| **Cost Tracking** | Cout par requete (tokens in/out), budgets, spend logs | `litellm/cost_calculator.py`, `proxy/spend_tracking/*`, `proxy/hooks/proxy_track_cost_callback.py` |
| **Logging/Callbacks** | Systeme extensible, `CustomLogger`, `StandardLoggingPayload`, integrations Langfuse/S3/Datadog/Slack | `litellm/integrations/custom_logger.py`, `litellm/litellm_core_utils/litellm_logging.py` |
| **Auth** | Virtual API Keys, JWT RBAC, OAuth2, SSO, SCIM | `proxy/auth/user_api_key_auth.py`, `proxy/auth/handle_jwt.py` |
| **Rate Limiting** | RPM/TPM par key/user/team/org/model, sliding windows, dynamic limiter | `proxy/hooks/parallel_request_limiter_v3.py`, `proxy/hooks/dynamic_rate_limiter.py` |
| **Caching** | Redis, in-memory, semantic (Qdrant), S3, GCS, disk | `litellm/caching/caching.py` |
| **Load Balancing** | simple-shuffle, least-busy, latency-based, cost-based, usage-based | `litellm/router.py`, `litellm/router_strategy/*` |
| **SDK Python** | `litellm.completion()`, `litellm.acompletion()`, client proxy admin | `litellm/main.py`, `litellm/proxy/client/*` |
| **UI Dashboard** | Next.js, ecrans usage/logs/keys/users/teams/guardrails | `ui/litellm-dashboard/` |
| **Governance base** | Teams/orgs/policies/guardrails/RBAC | `proxy/policy_engine/*`, `proxy/management_endpoints/` |

---

## 2. Ce que LiteLLM NE fait PAS — Gaps prioritises

### P0 — Absent (consensus 3/3)

Ces features sont **totalement absentes** de LiteLLM et identifiees par les 3 analystes:

| Gap | Detail | Pertinence Companion |
|-----|--------|---------------------|
| **Agent monitoring client-side** | Aucun agent local, LiteLLM = serveur pur. Zero visibilite sur ce qui se passe sur le poste de travail | **CRITIQUE** — c'est exactement ce que notre projet fait deja |
| **Detection apps AI desktop** | Impossible de savoir si ChatGPT, Cursor, Ollama tournent sur le poste | **CRITIQUE** — desktop.py existe deja |
| **Browser tracking** | Aucune extension navigateur, pas de suivi des interactions web avec les AI | **CRITIQUE** — chrome-extension/ existe deja |
| **Shell history tracking** | Aucune analyse des commandes shell pour identifier l'usage CLI d'outils AI | **CRITIQUE** — shell_history.py existe deja |
| **Token tracking CLI local** | Si un dev utilise claude/codex/gemini CLI sans passer par le proxy, c'est invisible | **CRITIQUE** — token_tracker.py existe deja |
| **Integration IDE native** | Pas de plugin VSCode/JetBrains pour monitoring en temps reel | **HAUTE** — notre detection desktop couvre partiellement |

### P1 — Partiel/Basique (consensus 3/3)

LiteLLM a des bases mais ne va pas assez loin:

| Gap | Etat actuel LiteLLM | Opportunite |
|-----|---------------------|-------------|
| **Analytics predictifs** | Endpoint `/global/predict/spend/logs` reference mais **non implemente** (Codex) | Prevision de couts, detection anomalies |
| **Alerting intelligent** | Alertes seuils statiques budget/soft-budget | Alertes ML, burn-rate, anomaly detection |
| **Governance avancee** | Policies/guardrails basiques, pas de compliance multi-regime | Policy-as-code, simulation d'impact, audit |
| **Cost optimization** | Routing cost-based existe, mais pas de recommandations proactives | "Ce prompt coute 80% moins cher avec model X" |
| **Dashboards Grafana** | `prometheus.py` + cookbook basique | Pack dashboards opiniones cle en main |

### P2 — Partiel (consensus 2/3)

| Gap | Detail |
|-----|--------|
| **Multi-tenant enterprise** | Team/org existent mais pas isolation data/control avancee, chargeback |
| **Usage perso vs enterprise** | Pas de mode dual personal/enterprise |

---

## 3. Opportunites Companion — Priorisees

### Tier 1: Notre ADN (deja code, consensus 3/3)

| Module | Nous l'avons deja | A interfacer avec LiteLLM |
|--------|-------------------|--------------------------|
| **Agent local multiplateforme** | `ai_cost_observer/` (Python, macOS/Windows) | Enrichir avec metadata LiteLLM via callbacks |
| **Desktop AI app detection** | `detectors/desktop.py` (psutil + active window) | Correler apps detectees avec spend proxy |
| **CLI process tracking** | `detectors/cli.py` (psutil + dedup) | Lier sessions CLI a des virtual keys |
| **Browser tracking** | `chrome-extension/` (Manifest V3) | Capturer aussi les requetes vers le proxy LiteLLM |
| **Shell history analysis** | `detectors/shell_history.py` | Enrichir avec patterns de commandes LiteLLM CLI |
| **Token tracking** | `detectors/token_tracker.py` (JSONL + SQLite) | Deduplication avec spend logs LiteLLM |
| **HTTP receiver** | `server/http_receiver.py` (Flask) | Recevoir aussi les callbacks de LiteLLM |
| **OTel/Prometheus pipeline** | `telemetry.py` (OTLP gRPC) | Unifier metriques client + server |
| **Grafana dashboards** | `infra/` (4 dashboards) | Ajouter panels spend LiteLLM |

### Tier 2: A construire (consensus 3/3, pas encore code)

| Module | Description | Effort estime |
|--------|-------------|---------------|
| **Ingestion & Correlation Engine** | Fusion flux LiteLLM (callbacks) + flux client-side, dedup via `trace_id` | Medium |
| **Predictive Cost Analytics** | Forecast spend par team/user/model, detection anomalies | Large |
| **Smart Alerting** | Alertes contextuelles, burn-rate, severity routing, suppression intelligente | Medium |
| **Governance Control Plane** | Policy templates PII/residency, simulation what-if, audit compliance | Large |
| **Cost Optimization Engine** | Recommandations model swap, cache policy, prompt optimization avec ROI | Large |

### Tier 3: Nice-to-have (consensus 1-2/3)

| Module | Description |
|--------|-------------|
| **IDE Extensions** | Plugin VSCode/JetBrains pour cout/token temps reel par fichier |
| **Multi-tenant FinOps** | Chargeback/showback multi-axes org/team/project |
| **CLI Wrapper** | Token/cost tracing par commande et repo |

---

## 4. Architecture d'integration recommandee

### Points d'extension LiteLLM (consensus 3/3)

```
┌──────────────────────────────────────────────────────────────────┐
│                        LiteLLM Proxy                             │
│                                                                  │
│  ┌─────────────┐   ┌──────────────┐   ┌───────────────────────┐ │
│  │ Pre-call     │──▸│ LLM Provider │──▸│ Post-call             │ │
│  │ hooks        │   │ (100+ models)│   │ success/failure hooks │ │
│  └──────┬──────┘   └──────────────┘   └──────────┬────────────┘ │
│         │                                         │              │
│         ▼                                         ▼              │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │              CustomLogger Callbacks                         │ │
│  │  async_pre_call_hook()                                      │ │
│  │  async_post_call_success_hook()  → StandardLoggingPayload   │ │
│  │  async_post_call_failure_hook()                             │ │
│  └──────────────────────┬──────────────────────────────────────┘ │
│                         │                                        │
│  APIs: /spend/logs, /key/info, /user/info, /model/info          │
└─────────────────────────┼────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│                   LiteLLM Companion                              │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │ CompanionLog │  │ Client-side  │  │ Correlation Engine     │ │
│  │ (CustomLogger│  │ Agent        │  │ (dedup trace_id,       │ │
│  │  callback)   │  │ (desktop,cli,│  │  enrich with client    │ │
│  │              │  │  browser,    │  │  context)              │ │
│  │              │  │  shell,token)│  │                        │ │
│  └──────┬───────┘  └──────┬──────┘  └───────────┬────────────┘ │
│         │                 │                      │              │
│         ▼                 ▼                      ▼              │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │              OTel Pipeline → Prometheus → Grafana           │ │
│  │              (metriques unifiees client + server)           │ │
│  └─────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

### Callback Companion (squelette — consensus 3/3)

```python
from litellm.integrations.custom_logger import CustomLogger
from litellm.types.utils import StandardLoggingPayload

class CompanionLogger(CustomLogger):
    """Bridge LiteLLM → Companion ingestion."""

    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        # Injecter metadata Companion (session_id, host_id, workspace)
        data.setdefault("metadata", {})
        data["metadata"]["companion_host"] = self._get_host_id()
        return data

    async def async_post_call_success_hook(self, data, user_api_key_dict, response):
        # Extraire StandardLoggingPayload
        # Enrichir avec dimensions client-side
        # Push vers Companion ingestion (OTel ou API)
        payload = self._extract_payload(data, response)
        await self._ingest(payload)
        return response

    async def async_post_call_failure_hook(self, request_data, original_exception,
                                            user_api_key_dict, traceback_str=None):
        # Classifier erreur + alerting
        await self._alert(request_data, original_exception)
        return None
```

### Champs StandardLoggingPayload critiques

| Champ | Usage Companion |
|-------|-----------------|
| `id`, `trace_id` | Deduplication avec tracking local |
| `model`, `model_group`, `custom_llm_provider` | Correlation cout/provider |
| `prompt_tokens`, `completion_tokens`, `total_tokens` | Reconciliation avec token_tracker.py |
| `response_cost`, `cost_breakdown` | Agregation avec estimations client-side |
| `status`, `error_information` | Alerting intelligent |
| `cache_hit` | Optimisation recommendations |
| `metadata` | Injection context client (host, app, workspace) |

### APIs pour polling/backfill

| Endpoint | Usage |
|----------|-------|
| `GET /spend/logs` | Reconciliation periodique |
| `GET /key/info` | Mapping virtual keys → users |
| `GET /user/info` | Budgets et limites |
| `GET /v1/model/info` | Catalogue modeles + prix |
| `POST /cost/estimate` | Prevision avant appel |

---

## 5. Strategie recommandee

### Phase immediate: Callback + Bridge

1. Creer `CompanionLogger(CustomLogger)` qui pousse les events LiteLLM vers notre pipeline OTel
2. Ajouter un endpoint d'ingestion dans notre `http_receiver.py` pour recevoir les StandardLoggingPayload
3. Unifier les metriques: spend LiteLLM + detections client-side dans les memes dashboards Grafana

### Phase suivante: Correlation

4. Matcher les sessions CLI (claude, codex) avec les spend logs LiteLLM via `trace_id`
5. Dedup: eviter le double-comptage entre notre token_tracker et le cost tracking LiteLLM
6. Vue unifiee: "dark usage" (hors proxy) + "tracked usage" (via proxy)

### Phase finale: Intelligence

7. Predictive cost analytics (forecast, anomaly detection)
8. Smart alerting (burn-rate, deviation, blast radius)
9. Cost optimization recommendations (model swap suggestions)

---

## Conclusion

**Notre projet est exactement le complement manquant de LiteLLM.** LiteLLM couvre le cote serveur (proxy, routing, cost tracking API). Nous couvrons le cote client (desktop, browser, CLI, shell). L'integration via `CustomLogger` callbacks + `StandardLoggingPayload` est la voie naturelle — sans fork necessaire, juste un plugin.

La priorite absolue est le **bridge callback** qui connecte les deux mondes, puis la **correlation** pour eliminer les doublons et offrir une vue 360° de l'usage AI.
