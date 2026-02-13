# Analyse LiteLLM — Codex
> Generee par Codex CLI (gpt-5.3-codex xhigh)
> Commit analysé: 3cbb12b9c890248bbe1350ad68f1b0082d2daeec (main, 2026-02-12)
---

## 1) CE QUE LITELLM FAIT DEJA

### 1. Proxy OpenAI-compatible + passthrough multi-provider

- Le proxy FastAPI expose des routes type OpenAI (`/v1/chat/completions`, `/v1/embeddings`, `/v1/models`) et de nombreuses routes de gestion.
- Il inclut aussi des routes passthrough vers fournisseurs natifs (Anthropic, Vertex, etc.).
- **Fichiers:** `litellm/proxy/proxy_server.py`, `litellm/proxy/pass_through_endpoints/pass_through_endpoints.py`, `litellm/proxy/pass_through_endpoints/llm_passthrough_endpoints.py`.

### 2. Abstraction modeles/fournisseurs

- Coeur SDK unifie pour completion, acompletion, embedding, aembedding.
- Large couche d'adaptateurs providers dans `litellm/llms/*`.
- Endpoints d'info modeles (`/model/info`, `/v1/model/info`, `/v2/model/info`).
- **Fichiers:** `litellm/main.py`, `litellm/router.py`, `litellm/proxy/proxy_server.py`, `litellm/proxy/management_endpoints/model_management_endpoints.py`, `model_prices_and_context_window.json`.

### 3. Cost tracking / spend tracking / budgets

- Calcul de cout centralise par modele/provider (tokens, images, video, custom pricing).
- Tracking spend cote proxy via callback DB (`_ProxyDBLogger`) et ecritures spend logs.
- Endpoints spend riches (`/spend/logs`, `/spend/logs/v2`, `/global/spend`, `/global/spend/logs`, `/provider/budgets`, `/cost/estimate`).
- **Fichiers:** `litellm/cost_calculator.py`, `litellm/proxy/hooks/proxy_track_cost_callback.py`, `litellm/proxy/spend_tracking/spend_tracking_utils.py`, `litellm/proxy/spend_tracking/spend_management_endpoints.py`, `litellm/proxy/management_endpoints/cost_tracking_settings.py`.

### 4. Logging extensible + payload standard

- Systeme callbacks global (`callbacks`, `success_callback`, `failure_callback`, async variants).
- API de callback typee via `CustomLogger` avec hooks pre/during/post et success/failure.
- Schema de log unifie `StandardLoggingPayload` (couts, tokens, status, trace_id, erreurs, cache).
- **Fichiers:** `litellm/__init__.py`, `litellm/integrations/custom_logger.py`, `litellm/litellm_core_utils/litellm_logging.py`, `litellm/types/utils.py`.

### 5. AuthN/AuthZ

- Auth API keys + controles de routes/permissions.
- JWT RBAC (roles/scopes), OAuth2, SSO/UI flows, SCIM.
- Endpoints d'inspection (`/key/info`, `/v2/key/info`, `/user/info`).
- **Fichiers:** `litellm/proxy/auth/user_api_key_auth.py`, `litellm/proxy/auth/route_checks.py`, `litellm/proxy/auth/handle_jwt.py`, `litellm/proxy/auth/oauth2_check.py`, `litellm/proxy/management_endpoints/key_management_endpoints.py`, `litellm/proxy/management_endpoints/internal_user_endpoints.py`.

### 6. Rate limiting et quotas multi-niveaux

- Limites RPM/TPM/max_parallel au niveau key/user/team/org/model, avec sliding windows.
- Dynamic rate limiting et max-budget limiter.
- Pre-call checks de limites modeles cote router.
- **Fichiers:** `litellm/proxy/hooks/parallel_request_limiter_v3.py`, `litellm/proxy/hooks/dynamic_rate_limiter.py`, `litellm/proxy/hooks/max_budget_limiter.py`, `litellm/router_utils/pre_call_checks/model_rate_limit_check.py`.

### 7. Caching

- Backends local/Redis/Redis semantic/Qdrant semantic/S3/GCS/Disk.
- Endpoints cache ping/delete/flush/settings.
- **Fichiers:** `litellm/caching/caching.py`, `litellm/caching/Readme.md`, `litellm/proxy/caching_routes.py`, `litellm/proxy/management_endpoints/cache_settings_endpoints.py`.

### 8. Load balancing / retries / fallbacks

- Router avec strategies simple-shuffle, least-busy, latency-based-routing, cost-based-routing, usage-based-routing, usage-based-routing-v2.
- Systeme de fallbacks context/content policy + retry policy global/model-group.
- **Fichiers:** `litellm/router.py`, `litellm/router_strategy/least_busy.py`, `litellm/router_strategy/lowest_latency.py`, `litellm/router_strategy/lowest_cost.py`, `litellm/router_strategy/lowest_tpm_rpm_v2.py`.

### 9. SDKs

- SDK Python complet (runtime calls + router).
- Client Python dedie au proxy (keys/users/models/teams + CLI).
- JS present mais moins riche cote proxy client.
- **Fichiers:** `litellm/main.py`, `litellm/router.py`, `litellm/proxy/client/README.md`, `litellm/proxy/client/keys.py`, `litellm/proxy/client/users.py`, `litellm/proxy/client/models.py`, `litellm/proxy/client/cli/main.py`, `litellm-js/proxy/src/index.ts`.

### 10. UI Dashboard

- Dashboard Next.js avec ecrans usage/logs/keys/users/teams/guardrails/policies.
- Couche API front centralisee qui appelle les endpoints spend/key/user/policy/cache/budget.
- **Fichiers:** `ui/litellm-dashboard/src/app/page.tsx`, `ui/litellm-dashboard/src/app/(dashboard)/*`, `ui/litellm-dashboard/src/components/networking.tsx`.

### 11. Gouvernance et multi-tenant (base solide)

- Teams/organizations/memberships/object permissions/policies/attachments en base.
- Policy engine avec resolution de guardrails et endpoints de validation/test/resolve.
- **Fichiers:** `litellm/proxy/schema.prisma`, `litellm/proxy/management_endpoints/team_endpoints.py`, `litellm/proxy/management_endpoints/organization_endpoints.py`, `litellm/proxy/management_endpoints/internal_user_endpoints.py`, `litellm/proxy/management_endpoints/policy_endpoints.py`, `litellm/proxy/policy_engine/policy_endpoints.py`, `litellm/proxy/policy_engine/policy_resolve_endpoints.py`.

---

## 2) CE QUE LITELLM NE FAIT PAS (ou fait partiellement) vs besoin "Companion"

### 1. Monitoring client-side (desktop/host local)

- **Etat: Absent** dans LiteLLM coeur.
- LiteLLM observe les requetes qui passent par son proxy, pas les evenements OS/app locaux en amont.
- Indices: architecture centree proxy dans `litellm/proxy/*`; pas de collecteur desktop dedie.

### 2. Analytics predictif de cout

- **Etat: Partiel / non abouti** cote OSS.
- Endpoint `/global/predict/spend/logs` reference en types/UI mais pas implemente en route serveur dans `litellm/proxy/**/*.py`.
- Preuves: `litellm/proxy/_types.py`, `ui/litellm-dashboard/src/components/networking.tsx`, `tests/test_spend_logs.py` (test skip).

### 3. Alerting intelligent (anomalies, forecasting, causal)

- **Etat: Partiel.**
- Alertes budget/soft-budget/failures existent, mais pas moteur avance d'anomaly detection/prediction.
- **Fichiers:** `litellm/proxy/utils.py`, `litellm/proxy/auth/auth_checks.py`, `litellm/proxy/hooks/proxy_track_cost_callback.py`.

### 4. Governance avancee (compliance enterprise approfondie)

- **Etat: Partiel.**
- Il existe policies/guardrails/RBAC, mais pas un framework complet "policy-as-code" oriente conformite multi-regime avec simulation d'impact transverse avancee.
- **Fichiers:** `litellm/proxy/policy_engine/*`, `litellm/proxy/management_endpoints/policy_endpoints.py`.

### 5. Multi-tenant avance "enterprise-grade isole"

- **Etat: Partiel.**
- Team/org/permissions existent, mais pas une couche complete d'isolation de plans (data/control), delegation admin hierarchique poussee, chargeback multi-tenant analytique avance.
- **Fichiers:** `litellm/proxy/schema.prisma`, `litellm/proxy/management_endpoints/team_endpoints.py`, `litellm/proxy/management_endpoints/organization_endpoints.py`.

### 6. Integration IDE native

- **Etat: Absent** (pas de plugin VSCode/JetBrains first-class dans le repo).

### 7. Browser tracking riche

- **Etat: Absent/limite.**
- Il y a analytics "user-agent/tag" serveur, mais pas extension/browser instrumentation cote client final.
- **Fichiers:** `litellm/proxy/management_endpoints/user_agent_analytics_endpoints.py`.

### 8. Usage perso vs enterprise (produit dual mode)

- **Etat: Partiel.**
- Le code distingue certaines features premium, mais pas un modele produit "personal observability" complet separe du mode enterprise.

### 9. Grafana custom pret-a-l'emploi "compagnon"

- **Etat: Partiel.**
- Existence de metriques Prometheus + dashboards cookbook, mais pas une offre custom data-model compagnon cle en main.
- **Fichiers:** `litellm/integrations/prometheus.py` (via imports), `cookbook/litellm_proxy_server/grafana_dashboard/*`.

### 10. Cost optimization proactive (recommandations automatiques)

- **Etat: Partiel.**
- Routing cost-based existe, mais pas moteur de recommandations/action plans "optimiser prompts/models/policies" avec ROI estime.
- **Fichiers:** `litellm/router_strategy/lowest_cost.py`, `litellm/router.py`.

### 11. Detection apps IA desktop

- **Etat: Absent.**

### 12. Shell history analytics

- **Etat: Absent.**

### 13. Token tracking CLI local (hors proxy)

- **Etat: Absent.**
- Le CLI proxy gere l'admin, pas la telemetrie detaillee des usages CLI locaux multi-outils.

---

## 3) OPPORTUNITES COMPANION (modules manquants et positionnement)

### 1. Companion Local Agent (desktop/browser/CLI)

- Capture locale: process list IA, shell commands IA, sessions CLI, extensions navigateur, IDE events.
- Correlation avec appels proxy via trace/session ids.
- **Valeur:** couvrir le "dark usage" hors proxy.

### 2. Companion Ingestion + Correlation Engine

- Ingestion bi-source: flux LiteLLM (callbacks + APIs) + flux client-side.
- Unification en "conversation/session/cost graph".
- Deduplication retries/fallbacks via `trace_id`/`id` de `StandardLoggingPayload`.

### 3. Predictive Cost & Capacity

- Prevision spend par team/user/model/provider.
- Detection d'anomalies (ruptures de tendance, cout/token hors distribution, misuse de cles).
- Generation de recommandations auto (model swap, cache policy, rate policy).

### 4. Governance Control Plane

- Policy templates (PII, data residency, prompt risk) au-dessus des policies LiteLLM.
- Simulation "what-if" avant deploiement de guardrails/policies.
- Audit de conformite oriente equipes/orgs.

### 5. Smart Alerting

- Alertes contextuelles (severity, blast radius, owner routing, suppression intelligente).
- Alertes "preventives" (burn-rate vers depassement budget, saturation RPM imminente).

### 6. Advanced Multi-tenant FinOps

- Chargeback/showback multi-axes (org/team/user/project/application/device).
- Quotas dynamiques par profil de risque et criticite.

### 7. IDE + Browser + CLI UX

- Extension IDE: cout/token en temps reel par fichier/session.
- Extension browser: trace de prompts vers vendor UIs.
- CLI wrapper: token/cost tracing par commande et repo.

### 8. Grafana Pack Companion

- Dashboards opinionnes (efficacite cout, anomalies, guardrails impact, latence/cout correlees).
- Datasource normalisee depuis Companion DB.

---

## 4) ARCHITECTURE INTEGRATION (callbacks, hooks, middleware, APIs, SDK)

### 1. Points d'extension LiteLLM a utiliser en priorite

- Callbacks globaux et success/failure: `litellm/__init__.py`.
- Interface callback: `litellm/integrations/custom_logger.py` avec `async_pre_call_hook`, `async_post_call_success_hook`, `async_post_call_failure_hook`, `async_logging_hook`, `async_pre_routing_hook`.
- Pipeline proxy hooks: `litellm/proxy/utils.py` (`pre_call_hook`, `during_call_hook`, `post_call_success_hook`, `post_call_failure_hook`), appeles depuis `litellm/proxy/common_request_processing.py` et `litellm/proxy/pass_through_endpoints/pass_through_endpoints.py`.
- Callback mgmt endpoints: `litellm/proxy/management_endpoints/callback_management_endpoints.py`.

### 2. Mecanisme Companion recommande

- Deployer un callback custom `CustomLogger` dedie Companion qui pousse evenements vers un backend Companion.
- Utiliser `StandardLoggingPayload` comme contrat d'ingestion principal pour eviter un schema proprietaire fragile.
- Completer par polling/backfill via APIs proxy.
- **API cles:** `/spend/logs`, `/spend/logs/v2`, `/global/spend`, `/global/spend/logs`, `/key/info`, `/v2/key/info`, `/user/info`, `/v1/model/info`, `/v2/model/info`.

### 3. Contrat de donnees de base

- Source standard: `StandardLoggingPayload` dans `litellm/types/utils.py`.
- **Champs critiques:** `id`, `trace_id`, `model`, `model_group`, `custom_llm_provider`, `prompt_tokens`, `completion_tokens`, `total_tokens`, `response_cost`, `cost_breakdown`, `status`, `status_fields`, `cache_hit`, `metadata`, `user_agent`, `error_information`.
- Regle Companion: enrichir avec dimensions client-side (`host_id`, `app_name`, `shell_command_hash`, `ide_workspace`, `browser_tab_origin`, `usage_mode_personal_enterprise`).

### 4. Callbacks success/failure concrets

- **Success path:** `async_post_call_success_hook` pour enrichir cout final, latence, cache-hit, policy-hit.
- **Failure path:** `async_post_call_failure_hook` pour classifier erreurs provider/proxy/auth/rate-limit et generer alertes intelligentes.
- **Pre-appel:** `async_pre_call_hook` pour injecter metadata Companion (`session_id`, `workload_id`, `client_context`) dans les requetes.

### 5. Middleware proxy et hooks

- LiteLLM a un middleware explicite (`PrometheusAuthMiddleware`) et CORS dans `litellm/proxy/proxy_server.py`.
- Pour Companion, privilegier callbacks/hooks (moins intrusif) avant d'ajouter du middleware FastAPI custom.
- Si middleware necessaire: fork controle de `proxy_server.py` + `app.add_middleware(...)`.

### 6. Integration SDK Python

- Apps clientes peuvent continuer a appeler LiteLLM via `litellm.completion`/`litellm.acompletion` (fichiers `litellm/main.py`, `litellm/router.py`).
- Le Companion peut utiliser le client proxy Python pour introspection admin (`litellm/proxy/client/*`).
- **Strategie:** runtime calls via SDK LiteLLM, control/analytics via Proxy Client + callbacks Companion.

### 7. Squelette minimal callback Companion

```python
from litellm.integrations.custom_logger import CustomLogger

class CompanionLogger(CustomLogger):
    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        data.setdefault("metadata", {})
        data["metadata"]["companion_session_id"] = data.get("metadata", {}).get("companion_session_id")
        return data

    async def async_post_call_success_hook(self, data, user_api_key_dict, response):
        # extraire StandardLoggingPayload via kwargs/resultat selon pipeline
        # push vers Companion Ingestion API
        return response

    async def async_post_call_failure_hook(self, request_data, original_exception, user_api_key_dict, traceback_str=None):
        # classifier l'erreur + push evenement failure
        return None
```

---

## Conclusion technique

- LiteLLM est deja tres solide comme proxy LLM unifie + gouvernance de base + FinOps operationnel cote serveur.
- Le projet Companion doit se positionner sur ce qui manque: **telemetrie client-side, intelligence predictive, gouvernance avancee, optimisation proactive et experience IDE/browser/CLI**.
- La voie d'integration la plus robuste est: **callbacks CustomLogger + hooks proxy + APIs de spend/key/user + contrat StandardLoggingPayload**, sans casser le coeur LiteLLM.
