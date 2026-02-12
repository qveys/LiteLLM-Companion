"""Audit: trace every OTel metric through the Prometheus naming pipeline and
verify that every Grafana dashboard PromQL query references a valid
Prometheus metric name.

OTel-to-Prometheus name conversion rules (OTel Collector prometheusexporter,
NO namespace configured):

  1. Dots (.) in the metric name become underscores (_).
  2. A unit suffix is appended based on the unit parameter:
       "s"   -> "_seconds"
       "USD" -> "_USD"
       "%"   -> "_percent"
       "MB"  -> "_MB"
       "1"   -> (nothing)
  3. Counter (monotonic Sum) appends "_total" **unless the name already ends
     with _total** (deduplication per OTel spec).
  4. Gauge / ObservableGauge / UpDownCounter does NOT append "_total".
  5. Histogram generates base name + "_bucket" / "_sum" / "_count".
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# 1. Define all 16 OTel metrics from telemetry.py and compute expected
#    Prometheus names.
# ---------------------------------------------------------------------------

# Each entry: (otel_name, unit, otel_type, expected_prometheus_base_name)
# otel_type is one of: "counter", "up_down_counter", "histogram"
OTEL_METRICS = [
    ("ai.app.running",                        "1",   "observable_gauge"),
    ("ai.app.active.duration",                "s",   "counter"),
    ("ai.app.cpu.usage",                      "%",   "gauge"),
    ("ai.app.memory.usage",                   "MB",  "gauge"),
    ("ai.app.estimated.cost",                 "USD", "counter"),
    ("ai.browser.domain.active.duration",     "s",   "counter"),
    ("ai.browser.domain.visit.count",         "1",   "counter"),
    ("ai.browser.domain.estimated.cost",      "USD", "counter"),
    ("ai.cli.running",                        "1",   "observable_gauge"),
    ("ai.cli.active.duration",                "s",   "counter"),
    ("ai.cli.estimated.cost",                 "USD", "counter"),
    ("ai.cli.command.count",                  "1",   "counter"),
    ("ai.tokens.input_total",                 "1",   "counter"),
    ("ai.tokens.output_total",                "1",   "counter"),
    ("ai.tokens.cost_usd_total",              "1",   "counter"),
    ("ai.prompt.count_total",                 "1",   "counter"),
]

UNIT_SUFFIX_MAP = {
    "1":   "",
    "s":   "_seconds",
    "%":   "_percent",
    "MB":  "_MB",
    "USD": "_USD",
}


def otel_to_prometheus(name: str, unit: str, otel_type: str) -> str:
    """Convert an OTel metric name + unit + type to the Prometheus name.

    Follows the OTel Collector prometheusexporter logic (no namespace).
    """
    # Step 1: dots -> underscores
    prom = name.replace(".", "_")

    # Step 2: append unit suffix
    prom += UNIT_SUFFIX_MAP[unit]

    # Step 3: counter -> append _total (deduplicated)
    if otel_type == "counter":
        if not prom.endswith("_total"):
            prom += "_total"

    return prom


# Build the expected set of Prometheus base names.
EXPECTED_PROMETHEUS_NAMES: dict[str, str] = {}
for otel_name, unit, otel_type in OTEL_METRICS:
    prom_name = otel_to_prometheus(otel_name, unit, otel_type)
    EXPECTED_PROMETHEUS_NAMES[otel_name] = prom_name

# For histograms we also expect _bucket, _sum, _count variants.
HISTOGRAM_SUFFIXES = ("_bucket", "_sum", "_count")
EXPECTED_HISTOGRAM_VARIANTS: set[str] = set()
for otel_name, unit, otel_type in OTEL_METRICS:
    if otel_type == "histogram":
        base = EXPECTED_PROMETHEUS_NAMES[otel_name]
        for sfx in HISTOGRAM_SUFFIXES:
            EXPECTED_HISTOGRAM_VARIANTS.add(base + sfx)

# The full valid set: base names + histogram variants.
ALL_VALID_PROMETHEUS_NAMES: set[str] = (
    set(EXPECTED_PROMETHEUS_NAMES.values()) | EXPECTED_HISTOGRAM_VARIANTS
)

# ---------------------------------------------------------------------------
# 2. Dashboard helpers
# ---------------------------------------------------------------------------

DASHBOARDS_DIR = Path(__file__).resolve().parent.parent / "infra" / "grafana" / "dashboards"
DASHBOARD_FILES = sorted(DASHBOARDS_DIR.glob("*.json"))

# Regex to extract metric names from PromQL expressions.
# Matches sequences of [a-zA-Z_:][a-zA-Z0-9_:]* that look like metric names,
# filtering out PromQL keywords and Grafana variables.
PROMQL_METRIC_RE = re.compile(
    r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:\{|\[|$|\)|\s|>|<|==|!=|\+|-|\*|/|,)',
)

PROMQL_KEYWORDS = {
    "sum", "avg", "min", "max", "count", "count_values",
    "topk", "bottomk", "quantile", "stddev", "stdvar",
    "rate", "irate", "increase", "delta", "idelta",
    "histogram_quantile", "label_replace", "label_join",
    "absent", "absent_over_time", "ceil", "floor", "round",
    "sort", "sort_desc", "clamp", "clamp_max", "clamp_min",
    "vector", "scalar", "time", "timestamp", "resets",
    "changes", "deriv", "predict_linear", "holt_winters",
    "by", "without", "on", "ignoring", "group_left", "group_right",
    "bool", "offset", "or", "and", "unless",
    "last_over_time", "sgn", "acos", "asin", "atan", "cos", "sin", "tan",
    "exp", "ln", "log2", "log10", "sqrt", "abs",
}


def extract_promql_expressions(dashboard: dict) -> list[tuple[str, str, str]]:
    """Extract all PromQL expr strings from a dashboard JSON.

    Also extracts query strings from templating variables.

    Returns list of (panel_title_or_var_name, refId_or_context, expr).
    """
    results = []

    # From templating variables
    for var in dashboard.get("templating", {}).get("list", []):
        if var.get("type") != "query":
            continue
        query = var.get("query", "")
        # query can be a string or a dict with a "query" key
        if isinstance(query, dict):
            query = query.get("query", "")
        if query:
            results.append((f"var:{var.get('name', '?')}", "variable", query))
        defn = var.get("definition", "")
        if defn and defn != query:
            results.append((f"var:{var.get('name', '?')}", "definition", defn))

    # From panels
    for panel in dashboard.get("panels", []):
        title = panel.get("title", "unknown")
        for target in panel.get("targets", []):
            expr = target.get("expr", "")
            if expr:
                results.append((title, target.get("refId", "?"), expr))

    return results


def extract_metric_names_from_expr(expr: str) -> set[str]:
    """Extract Prometheus metric names from a PromQL expression.

    Strategy: find tokens that appear in a "metric position" -- i.e. NOT
    inside curly braces (label matchers) and NOT as a label argument to
    label_values().
    """
    metrics: set[str] = set()

    # 1. Handle label_values(metric_name, label_name) -- first arg is metric.
    label_values_re = re.compile(r'label_values\(\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*,')
    for m in label_values_re.findall(expr):
        if m.startswith("ai_"):
            metrics.add(m)

    # 2. Strip everything inside { } to avoid matching label names.
    stripped = re.sub(r'\{[^}]*\}', '{}', expr)

    # 3. Strip by(...) and without(...) clauses (contain label names, not metrics).
    stripped = re.sub(r'\b(?:by|without)\s*\([^)]*\)', '', stripped)

    # 4. Also strip label_values(...) calls (already handled above).
    stripped = re.sub(r'label_values\([^)]*\)', '', stripped)

    # 5. Strip label_replace(...) arguments beyond the metric (args are label names).
    # label_replace(expr, "dst", "$1", "src", "regex") -- we keep the metric
    # inside but the string args aren't metric names (handled by ai_ prefix filter).

    # 4. Now find metric-like tokens in what remains.
    candidates = set(PROMQL_METRIC_RE.findall(stripped))

    for c in candidates:
        if c.lower() in PROMQL_KEYWORDS:
            continue
        if c.startswith("$") or c.startswith("__"):
            continue
        if len(c) < 3:
            continue
        if c.startswith("ai_"):
            metrics.add(c)

    return metrics


# ---------------------------------------------------------------------------
# 3. Tests
# ---------------------------------------------------------------------------

class TestOtelToPrometheusConversion:
    """Verify the expected Prometheus names for all 16 OTel metrics."""

    def test_all_16_metrics_defined(self):
        assert len(OTEL_METRICS) == 16

    @pytest.mark.parametrize("otel_name,unit,otel_type", OTEL_METRICS,
                             ids=[m[0] for m in OTEL_METRICS])
    def test_conversion_produces_valid_name(self, otel_name, unit, otel_type):
        prom = otel_to_prometheus(otel_name, unit, otel_type)
        # Must not contain dots
        assert "." not in prom
        # Counter must end with _total
        if otel_type == "counter":
            assert prom.endswith("_total"), f"{prom} should end with _total"
        # Gauge/ObservableGauge must NOT end with _total
        if otel_type in ("gauge", "observable_gauge"):
            assert not prom.endswith("_total"), f"{prom} should NOT end with _total"

    def test_no_double_total_suffix(self):
        """Metrics whose OTel name already contains '_total' should not get
        a double '_total_total' suffix."""
        for otel_name, unit, otel_type in OTEL_METRICS:
            prom = otel_to_prometheus(otel_name, unit, otel_type)
            assert "_total_total" not in prom, (
                f"{otel_name} -> {prom} has double _total"
            )

    def test_expected_names_snapshot(self):
        """Snapshot of all expected Prometheus metric names."""
        expected = {
            "ai.app.running":                       "ai_app_running",
            "ai.app.active.duration":               "ai_app_active_duration_seconds_total",
            "ai.app.cpu.usage":                     "ai_app_cpu_usage_percent",
            "ai.app.memory.usage":                  "ai_app_memory_usage_MB",
            "ai.app.estimated.cost":                "ai_app_estimated_cost_USD_total",
            "ai.browser.domain.active.duration":    "ai_browser_domain_active_duration_seconds_total",
            "ai.browser.domain.visit.count":        "ai_browser_domain_visit_count_total",
            "ai.browser.domain.estimated.cost":     "ai_browser_domain_estimated_cost_USD_total",
            "ai.cli.running":                       "ai_cli_running",
            "ai.cli.active.duration":               "ai_cli_active_duration_seconds_total",
            "ai.cli.estimated.cost":                "ai_cli_estimated_cost_USD_total",
            "ai.cli.command.count":                 "ai_cli_command_count_total",
            "ai.tokens.input_total":                "ai_tokens_input_total",
            "ai.tokens.output_total":               "ai_tokens_output_total",
            "ai.tokens.cost_usd_total":             "ai_tokens_cost_usd_total",
            "ai.prompt.count_total":                "ai_prompt_count_total",
        }
        assert EXPECTED_PROMETHEUS_NAMES == expected


class TestDashboardPromQLMetrics:
    """Verify that every PromQL expression in every dashboard uses valid
    Prometheus metric names (matching the OTel definitions)."""

    @pytest.fixture(autouse=True)
    def _load_dashboards(self):
        self.dashboards: dict[str, dict] = {}
        for f in DASHBOARD_FILES:
            self.dashboards[f.name] = json.loads(f.read_text())

    def test_dashboard_files_exist(self):
        assert len(self.dashboards) >= 4, (
            f"Expected at least 4 dashboards, found {len(self.dashboards)}"
        )

    def test_all_dashboard_metrics_are_valid(self):
        """Every metric referenced in PromQL must exist in the expected set."""
        errors = []
        for fname, dashboard in sorted(self.dashboards.items()):
            for panel_title, ref_id, expr in extract_promql_expressions(dashboard):
                metrics = extract_metric_names_from_expr(expr)
                for m in sorted(metrics):
                    if m not in ALL_VALID_PROMETHEUS_NAMES:
                        errors.append(
                            f"  {fname} | {panel_title} [{ref_id}]: "
                            f"'{m}' not in expected set"
                        )
        if errors:
            detail = "\n".join(errors)
            pytest.fail(
                f"Found {len(errors)} invalid metric name(s) in dashboards:\n"
                f"{detail}\n\n"
                f"Valid Prometheus names:\n"
                f"  {sorted(ALL_VALID_PROMETHEUS_NAMES)}"
            )

    def test_every_expected_metric_used_in_at_least_one_dashboard(self):
        """Every OTel metric should appear in at least one dashboard panel."""
        all_used: set[str] = set()
        for dashboard in self.dashboards.values():
            for _, _, expr in extract_promql_expressions(dashboard):
                all_used |= extract_metric_names_from_expr(expr)

        # For histograms, the base name may not appear directly; the
        # dashboard may use the _bucket/_sum/_count variant or the base
        # (which Prometheus auto-resolves for histogram_quantile).
        # We consider a histogram "used" if any of its variants appear.
        missing = []
        for otel_name, unit, otel_type in OTEL_METRICS:
            prom_base = EXPECTED_PROMETHEUS_NAMES[otel_name]
            if otel_type == "histogram":
                variants = {prom_base} | {prom_base + sfx for sfx in HISTOGRAM_SUFFIXES}
                if not (variants & all_used):
                    missing.append(f"  {otel_name} -> {prom_base} (histogram)")
            else:
                if prom_base not in all_used:
                    missing.append(f"  {otel_name} -> {prom_base}")

        if missing:
            detail = "\n".join(missing)
            pytest.fail(
                f"{len(missing)} metric(s) not referenced in any dashboard:\n"
                f"{detail}"
            )

    def test_no_double_total_in_dashboards(self):
        """No dashboard should reference a metric with '_total_total'."""
        errors = []
        for fname, dashboard in sorted(self.dashboards.items()):
            for panel_title, ref_id, expr in extract_promql_expressions(dashboard):
                metrics = extract_metric_names_from_expr(expr)
                for m in sorted(metrics):
                    if "_total_total" in m:
                        errors.append(
                            f"  {fname} | {panel_title} [{ref_id}]: "
                            f"'{m}' contains _total_total (double suffix bug)"
                        )
        if errors:
            detail = "\n".join(errors)
            pytest.fail(
                f"Found {len(errors)} metric(s) with double _total_total:\n"
                f"{detail}"
            )


class TestOtelCollectorConfig:
    """Verify the OTel Collector config has no namespace (prefix)."""

    @pytest.fixture(autouse=True)
    def _load_config(self):
        config_path = (
            Path(__file__).resolve().parent.parent
            / "infra" / "otel-collector-config.yaml"
        )
        self.config_text = config_path.read_text()

    def test_no_namespace_configured(self):
        """If a namespace were configured, all metric names would need a prefix."""
        assert "namespace:" not in self.config_text, (
            "OTel Collector has a namespace configured -- metric names need updating"
        )

    def test_prometheus_exporter_present(self):
        assert "prometheus:" in self.config_text
        assert "endpoint:" in self.config_text
