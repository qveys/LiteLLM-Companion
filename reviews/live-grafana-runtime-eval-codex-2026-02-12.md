# Validation Runtime Grafana/Prometheus (Codex, 2026-02-12)

## Objectif
Valider en live que les panels corrigés reflètent des valeurs cohérentes avec un jeu de données injecté, en particulier:
- cohérence du cumul coût (`Cost Accumulation Over Time`),
- application réelle des filtres globaux (`browser`, `category`, `source`) sur les panels Browser.

## Environnement de test
- Mini-stack locale isolée démarrée via Docker dans `/tmp/otel-live-eval`:
  - OTel Collector (`14317 -> 4317`)
  - Prometheus (`19090 -> 9090`, scrape 1s)
- Injection métriques via `create_app()` (receiver HTTP interne) + `TelemetryManager` pointant sur `127.0.0.1:14317`.

## Dataset injecté
- Host: `grafana-eval-live-1770882278`
- Deux cycles d’export extension, à l’identique:
  - `chatgpt.com`: 1800s, 3 visites
  - `claude.ai`: 600s, 2 visites
- Coût attendu total browser après 2 cycles:
  - chatgpt: `0.5 * (3600/3600) = 0.5`
  - claude: `0.6 * (1200/3600) = 0.2`
  - total: `0.7`

## Résultats live
- `sum(ai_browser_domain_estimated_cost_USD_total{host_name=~"..."} ) = 0.7` ✅
- Expression du panel `Cost Accumulation Over Time` (version corrigée, somme directe des compteurs) = `0.7` ✅

Filtres globaux (panels Browser):
- `usage_source=history_parser` -> `0.0` ✅
- `usage_source=extension` -> non-zéro ✅
- `browser_name=firefox` -> `0.0` ✅
- `browser_name=chrome` -> non-zéro ✅
- `ai_category=code` -> `0.0` ✅
- `ai_category=chat` -> non-zéro ✅

Répartition domaines (query de type `Domain Details`):
- `chatgpt.com ≈ 1819.18`
- `claude.ai ≈ 606.39`
- ratio `chatgpt/claude = 3.0` ✅ (ratio attendu 3:1)

## Note d’interprétation (important)
Les panels Browser actuels utilisent `increase(...[1d])`.  
Avec des séries très courtes en test synthétique, Prometheus applique son extrapolation de bord sur `increase`, ce qui peut produire une valeur absolue légèrement différente du delta brut injecté.  
En revanche:
- la cohérence des filtres,
- la cohérence des ratios entre séries,
- et la cohérence du panel de cumul coût (corrigé sans `increase`)  
ont été validées.
