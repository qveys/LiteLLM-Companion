# Validation Grafana vs Valeurs Réelles (Codex, 2026-02-12)

## Constat initial
- `Duration by Category` et `Domain Details` n'appliquaient pas tous les filtres globaux (`$browser`, `$category`, `$source`).
- `Cost Accumulation Over Time` utilisait `increase(...[$__rate_interval])`, ce qui produit un delta glissant et non un cumul réel.
- L'extension et le backend n'étaient pas totalement alignés sur les domaines/rates de `ai_config.yaml`.
- Le flux d'export extension pouvait compter des totaux avant l'ACK agent et perdait l'état en mémoire au redémarrage du service worker.

## Correctifs appliqués
- Dashboards:
  - Ajout des filtres globaux manquants dans `browser-ai-usage.json`.
  - Passage du panel "Cost Accumulation Over Time" en somme directe des compteurs `_total` dans `unified-cost.json`.
  - Uniformisation de tous les `uid` datasource Prometheus sur `prometheus-vps`.
- Extension:
  - Alignement des domaines trackés sur `src/ai_cost_observer/data/ai_config.yaml`.
  - Alignement des `COST_RATES` popup sur `cost_per_hour`.
  - Export rendu idempotent: ACK HTTP obligatoire (`response.ok`), `dailyTotals` mis à jour seulement après succès.
  - Persistance de `pendingDeltas` via `chrome.storage.local` + verrou séquentiel.
- Agent:
  - `WSLDetector`: transitions d'état (+1/-1) au lieu d'incréments répétitifs.
  - `BrowserHistoryParser`: checkpoint avancé uniquement après scan réussi (pas d'avance en cas d'erreur).

## Tests d'évaluation ajoutés
- `tests/test_grafana_value_integrity.py`
  - Vérifie filtres globaux des panels.
  - Vérifie logique "running total" (pas de `increase` glissant sur le panel concerné).
  - Vérifie UID datasource Prometheus unifié.
- `tests/test_extension_data_consistency.py`
  - Vérifie synchronisation `AI_DOMAINS` et `COST_RATES` avec `ai_config.yaml`.
  - Vérifie la sémantique d'ACK avant vidage des deltas.
- `tests/test_http_receiver_values.py`
  - Vérifie que durée/visites/coût envoyés par extension correspondent aux valeurs calculées côté agent.
- `tests/test_wsl_detector.py`
  - Vérifie les transitions de comptage WSL (+1 puis -1, sans double incrément).
- `tests/test_browser_history_checkpoint.py`
  - Vérifie l'absence d'avance de checkpoint après échec de scan.

## Résultats d'exécution
- Suite ciblée d'évaluation:
  - `PYTHONPATH=src .venv/bin/pytest -q tests/test_grafana_value_integrity.py tests/test_extension_data_consistency.py tests/test_http_receiver_values.py tests/test_wsl_detector.py tests/test_browser_history_checkpoint.py`
  - Résultat: `10 passed`.
- Suite globale:
  - Bloquée par un test e2e hors périmètre (`tests/test_e2e_agent.py`) qui attend `run_main_loop` non présent dans `src/ai_cost_observer/main.py`.

## Limite actuelle
- Vérification runtime live Grafana/Prometheus non exécutable ici: endpoints locaux `127.0.0.1:3000` et `127.0.0.1:9090` indisponibles au moment du contrôle.
