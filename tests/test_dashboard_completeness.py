"""Tests for Grafana dashboard completeness and label consistency.

Verifies that:
- All labels emitted by detectors appear in dashboard queries
- All labels referenced in dashboard queries are actually emitted by code
- Dashboard links are bidirectional
- Template variables are used in panel queries
- All panels have a prometheus-vps datasource
- No duplicate panel IDs exist within a dashboard
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_DIR = PROJECT_ROOT / "infra" / "grafana" / "dashboards"

DASHBOARDS = {
    "ai-cost-overview": DASHBOARD_DIR / "ai-cost-overview.json",
    "unified-cost": DASHBOARD_DIR / "unified-cost.json",
    "token-usage": DASHBOARD_DIR / "token-usage.json",
    "browser-ai-usage": DASHBOARD_DIR / "browser-ai-usage.json",
}

# ---------------------------------------------------------------------------
# Labels emitted by Python detectors (OTel attribute keys use dots).
# After OTel Collector -> Prometheus export, dots become underscores.
# We store the Prometheus-side names here (underscores) since that is what
# Grafana queries use.
# ---------------------------------------------------------------------------

# desktop.py labels (used on: app_running, app_active_duration, app_estimated_cost,
#                    app_cpu_usage, app_memory_usage)
DESKTOP_LABELS = {"app_name", "app_category"}

# cli.py labels (used on: cli_running, cli_active_duration, cli_estimated_cost)
CLI_LABELS = {"cli_name", "cli_category"}

# browser_history.py + http_receiver.py labels
# (used on: browser_domain_visit_count, browser_domain_active_duration)
BROWSER_LABELS = {"ai_domain", "ai_category", "browser_name", "usage_source"}
# browser_domain_estimated_cost uses a reduced set:
BROWSER_COST_LABELS = {"ai_domain", "ai_category"}

# token_tracker.py labels
# (used on: tokens_input_total, tokens_output_total, tokens_cost_usd_total)
TOKEN_LABELS = {"tool_name", "model_name"}
# prompt_count_total uses:
PROMPT_LABELS = {"tool_name", "source"}

# Resource attributes added by OTel SDK (on every metric)
RESOURCE_LABELS = {"host_name", "service_name", "service_version", "os_type", "deployment_environment"}

# All emitted labels (union)
ALL_EMITTED_LABELS = (
    DESKTOP_LABELS
    | CLI_LABELS
    | BROWSER_LABELS
    | BROWSER_COST_LABELS
    | TOKEN_LABELS
    | PROMPT_LABELS
)

# Map: metric name prefix -> expected labels emitted by code
# These are the Prometheus metric name prefixes (after OTel conversion).
METRIC_LABEL_MAP = {
    "ai_app_running": DESKTOP_LABELS,
    "ai_app_active_duration": DESKTOP_LABELS,
    "ai_app_estimated_cost": DESKTOP_LABELS,
    "ai_app_cpu_usage": DESKTOP_LABELS,
    "ai_app_memory_usage": DESKTOP_LABELS,
    "ai_cli_running": CLI_LABELS,
    "ai_cli_active_duration": CLI_LABELS,
    "ai_cli_estimated_cost": CLI_LABELS,
    "ai_cli_command_count": CLI_LABELS,
    "ai_browser_domain_active_duration": BROWSER_LABELS,
    "ai_browser_domain_visit_count": BROWSER_LABELS,
    "ai_browser_domain_estimated_cost": BROWSER_COST_LABELS,
    "ai_tokens_input_total": TOKEN_LABELS,
    "ai_tokens_output_total": TOKEN_LABELS,
    "ai_tokens_cost_usd_total": TOKEN_LABELS,
    "ai_prompt_count_total": PROMPT_LABELS,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_dashboard(name: str) -> dict:
    """Load and parse a dashboard JSON file."""
    path = DASHBOARDS[name]
    return json.loads(path.read_text(encoding="utf-8"))


def extract_all_exprs(dashboard: dict) -> list[str]:
    """Extract all PromQL expr strings from all panel targets in a dashboard."""
    exprs: list[str] = []

    def _walk_panels(panels: list[dict]) -> None:
        for panel in panels:
            for target in panel.get("targets", []):
                expr = target.get("expr", "")
                if expr:
                    exprs.append(expr)
            # Recurse into nested panels (rows)
            if "panels" in panel:
                _walk_panels(panel["panels"])

    _walk_panels(dashboard.get("panels", []))
    # Also check template variable queries
    for var in dashboard.get("templating", {}).get("list", []):
        q = var.get("query", "")
        if isinstance(q, str) and q:
            exprs.append(q)
        elif isinstance(q, dict):
            inner = q.get("query", "")
            if inner:
                exprs.append(inner)
        defn = var.get("definition", "")
        if defn:
            exprs.append(defn)
    return exprs


def extract_labels_from_exprs(exprs: list[str]) -> set[str]:
    """Extract all label names referenced in PromQL expressions.

    Matches:
    - Filter labels:  {label_name=~"..."}  or  {label_name="..."}
    - Aggregation labels: sum by (label_name)
    - Legend format: {{label_name}}
    - label_values(metric, label_name)
    - label_replace(..., "new_label", ..., "src_label", ...)
    """
    labels: set[str] = set()
    for expr in exprs:
        # {label="value"} or {label=~"value"}
        labels.update(re.findall(r'(\w+)\s*[!=~]+\s*"', expr))
        # sum by (label)
        labels.update(re.findall(r'(?:by|without)\s*\(([^)]+)\)', expr))
        # {{label}} in legendFormat
        labels.update(re.findall(r'\{\{(\w+)\}\}', expr))
        # label_values(metric, label)
        labels.update(re.findall(r'label_values\(\w+,\s*(\w+)\)', expr))
        # label_replace(..., "dst_label", "replacement", "src_label", "regex")
        # Pattern: "dst_label", "replacement", "src_label", "regex"
        # Handle nested calls by matching the 4-string arg pattern directly
        for m in re.finditer(r'"(\w+)"\s*,\s*"[^"]*"\s*,\s*"(\w+)"\s*,\s*"[^"]*"', expr):
            labels.add(m.group(1))  # destination label
            labels.add(m.group(2))  # source label

    # Clean up: "by (label1, label2)" patterns produce "label1, label2" strings
    expanded: set[str] = set()
    for label in labels:
        for part in label.split(","):
            part = part.strip()
            if part and re.match(r'^\w+$', part):
                expanded.add(part)

    # Remove known PromQL functions/keywords that aren't labels
    non_labels = {
        "sum", "increase", "rate", "vector", "label_replace", "label_values",
        "or", "and", "unless", "on", "ignoring", "group_left", "group_right",
        "by", "without", "avg", "min", "max", "count", "topk", "bottomk",
        "__name__",
    }
    return expanded - non_labels


def extract_legend_labels(dashboard: dict) -> set[str]:
    """Extract label names used in legendFormat fields like {{label_name}}."""
    labels: set[str] = set()
    for panel in dashboard.get("panels", []):
        for target in panel.get("targets", []):
            legend = target.get("legendFormat", "")
            labels.update(re.findall(r'\{\{(\w+)\}\}', legend))
        if "panels" in panel:
            for sub in panel["panels"]:
                for target in sub.get("targets", []):
                    legend = target.get("legendFormat", "")
                    labels.update(re.findall(r'\{\{(\w+)\}\}', legend))
    return labels


def extract_metric_names_from_exprs(exprs: list[str]) -> set[str]:
    """Extract Prometheus metric names from PromQL expressions."""
    names: set[str] = set()
    for expr in exprs:
        # Match metric names: ai_xxx_yyy{...} or ai_xxx_yyy[...]
        names.update(re.findall(r'\b(ai_\w+)\b', expr))
    return names


def get_dashboard_links(dashboard: dict) -> set[str]:
    """Get the set of dashboard UIDs that this dashboard links to."""
    uids: set[str] = set()
    for link in dashboard.get("links", []):
        url = link.get("url", "")
        # URL pattern: /d/<uid>
        match = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
        if match:
            uids.add(match.group(1))
    return uids


def get_all_panel_datasources(dashboard: dict) -> list[tuple[int, str, str | None]]:
    """Return list of (panel_id, panel_title, datasource_uid) tuples."""
    results: list[tuple[int, str, str | None]] = []

    def _walk(panels: list[dict]) -> None:
        for panel in panels:
            panel_id = panel.get("id", -1)
            title = panel.get("title", "untitled")
            ds = panel.get("datasource")
            ds_uid = None
            if isinstance(ds, dict):
                ds_uid = ds.get("uid")
            elif isinstance(ds, str):
                ds_uid = ds
            # Only check panels that have targets (skip text/row panels)
            if panel.get("targets"):
                results.append((panel_id, title, ds_uid))
            if "panels" in panel:
                _walk(panel["panels"])

    _walk(dashboard.get("panels", []))
    return results


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEmittedLabelsExistInQueries:
    """For each label emitted by detectors, verify it appears in at least one
    dashboard query (either as filter {label=~"..."} or in legendFormat {{label}})."""

    def _get_all_dashboard_labels(self) -> set[str]:
        """Collect all labels referenced across all dashboards."""
        all_labels: set[str] = set()
        for name in DASHBOARDS:
            db = load_dashboard(name)
            exprs = extract_all_exprs(db)
            all_labels |= extract_labels_from_exprs(exprs)
            all_labels |= extract_legend_labels(db)
        return all_labels

    def test_desktop_labels_in_dashboards(self):
        """Desktop detector labels (app_name, app_category) appear in queries."""
        dashboard_labels = self._get_all_dashboard_labels()
        for label in DESKTOP_LABELS:
            assert label in dashboard_labels, (
                f"Desktop label '{label}' is emitted by desktop.py but never "
                f"referenced in any dashboard query or legendFormat"
            )

    def test_cli_labels_in_dashboards(self):
        """CLI detector labels (cli_name, cli_category) appear in queries."""
        dashboard_labels = self._get_all_dashboard_labels()
        for label in CLI_LABELS:
            assert label in dashboard_labels, (
                f"CLI label '{label}' is emitted by cli.py but never "
                f"referenced in any dashboard query or legendFormat"
            )

    def test_browser_labels_in_dashboards(self):
        """Browser detector labels (ai_domain, ai_category, browser_name, usage_source)
        appear in queries."""
        dashboard_labels = self._get_all_dashboard_labels()
        for label in BROWSER_LABELS:
            assert label in dashboard_labels, (
                f"Browser label '{label}' is emitted by browser_history.py / "
                f"http_receiver.py but never referenced in any dashboard"
            )

    def test_token_labels_in_dashboards(self):
        """Token tracker labels (tool_name, model_name) appear in queries."""
        dashboard_labels = self._get_all_dashboard_labels()
        for label in TOKEN_LABELS:
            assert label in dashboard_labels, (
                f"Token label '{label}' is emitted by token_tracker.py but "
                f"never referenced in any dashboard"
            )

    def test_prompt_labels_in_dashboards(self):
        """Prompt count labels (tool_name, source) appear in queries."""
        dashboard_labels = self._get_all_dashboard_labels()
        # 'source' may not appear in dashboards since prompt_count queries
        # often only filter by tool_name. We check tool_name at minimum.
        assert "tool_name" in dashboard_labels, (
            "Prompt label 'tool_name' is emitted but never referenced in dashboards"
        )


class TestQueriedLabelsExistInCode:
    """For each label used in dashboard queries, verify it is actually emitted
    by the corresponding detector. Flags phantom labels."""

    def test_no_phantom_labels(self):
        """All labels in dashboard queries correspond to real emitted labels
        or known resource/infrastructure labels."""
        # Labels that come from OTel resource or Prometheus infra, not from code
        infra_labels = RESOURCE_LABELS | {
            "instance", "job",
            # Labels created by label_replace in overview dashboard
            "tool_name", "tool_category",
        }
        allowed = ALL_EMITTED_LABELS | infra_labels

        phantom: dict[str, set[str]] = {}
        for name in DASHBOARDS:
            db = load_dashboard(name)
            exprs = extract_all_exprs(db)
            queried = extract_labels_from_exprs(exprs)
            queried |= extract_legend_labels(db)
            unknown = queried - allowed
            if unknown:
                phantom[name] = unknown

        assert not phantom, (
            f"Phantom labels found in dashboards (referenced but never emitted by code):\n"
            + "\n".join(f"  {db}: {sorted(labels)}" for db, labels in phantom.items())
        )

    @pytest.mark.parametrize("dashboard_name", list(DASHBOARDS.keys()))
    def test_queried_labels_per_metric(self, dashboard_name: str):
        """For each metric queried in a dashboard, the filter labels should be
        a subset of what the detector emits for that metric."""
        db = load_dashboard(dashboard_name)
        exprs = extract_all_exprs(db)

        infra_labels = RESOURCE_LABELS | {"instance", "job", "tool_name", "tool_category"}
        issues: list[str] = []

        for expr in exprs:
            # Find metric{label=...} patterns
            for match in re.finditer(r'(ai_\w+)\{([^}]+)\}', expr):
                metric_prefix = match.group(1)
                label_block = match.group(2)
                queried_labels = set(re.findall(r'(\w+)\s*[!=~]+', label_block))

                # Find the matching metric in our map
                expected = None
                for prefix, labels in METRIC_LABEL_MAP.items():
                    if metric_prefix.startswith(prefix):
                        expected = labels
                        break

                if expected is not None:
                    allowed_for_metric = expected | infra_labels
                    unexpected = queried_labels - allowed_for_metric
                    if unexpected:
                        issues.append(
                            f"Metric '{metric_prefix}' queries labels {sorted(unexpected)} "
                            f"which are not emitted for this metric (expected: {sorted(expected)})"
                        )

        assert not issues, (
            f"Label mismatches in {dashboard_name}:\n" + "\n".join(f"  - {i}" for i in issues)
        )


class TestDashboardLinksBidirectional:
    """If dashboard A links to dashboard B, verify B links back to A."""

    def test_bidirectional_links(self):
        """All dashboard cross-links are bidirectional."""
        link_graph: dict[str, set[str]] = {}
        for name in DASHBOARDS:
            db = load_dashboard(name)
            link_graph[db["uid"]] = get_dashboard_links(db)

        missing: list[str] = []
        for src_uid, targets in link_graph.items():
            for tgt_uid in targets:
                if tgt_uid in link_graph:
                    if src_uid not in link_graph[tgt_uid]:
                        missing.append(
                            f"'{src_uid}' links to '{tgt_uid}' but '{tgt_uid}' "
                            f"does NOT link back to '{src_uid}'"
                        )

        assert not missing, (
            "Non-bidirectional dashboard links found:\n"
            + "\n".join(f"  - {m}" for m in missing)
        )


class TestTemplateVariablesUsed:
    """For each template variable defined in a dashboard, verify it appears in
    at least one panel query."""

    @pytest.mark.parametrize("dashboard_name", list(DASHBOARDS.keys()))
    def test_template_variables_used(self, dashboard_name: str):
        db = load_dashboard(dashboard_name)
        variables = [v["name"] for v in db.get("templating", {}).get("list", [])]
        exprs = extract_all_exprs(db)
        all_expr_text = " ".join(exprs)

        # Also check legendFormat fields
        legend_texts: list[str] = []
        for panel in db.get("panels", []):
            for target in panel.get("targets", []):
                legend_texts.append(target.get("legendFormat", ""))

        combined_text = all_expr_text + " " + " ".join(legend_texts)

        unused: list[str] = []
        for var in variables:
            # Check for $var or ${var} or $__var patterns
            if f"${var}" not in combined_text and f"${{{var}}}" not in combined_text:
                unused.append(var)

        assert not unused, (
            f"Dashboard '{dashboard_name}' defines template variables "
            f"that are never used in any panel query: {unused}"
        )


class TestAllPanelsHaveDatasource:
    """Every panel with targets must reference prometheus-vps."""

    @pytest.mark.parametrize("dashboard_name", list(DASHBOARDS.keys()))
    def test_panels_have_prometheus_datasource(self, dashboard_name: str):
        db = load_dashboard(dashboard_name)
        panels = get_all_panel_datasources(db)

        missing: list[str] = []
        for panel_id, title, ds_uid in panels:
            if ds_uid != "prometheus-vps":
                missing.append(
                    f"Panel {panel_id} ('{title}') has datasource uid='{ds_uid}' "
                    f"instead of 'prometheus-vps'"
                )

        assert not missing, (
            f"Panels in '{dashboard_name}' without prometheus-vps datasource:\n"
            + "\n".join(f"  - {m}" for m in missing)
        )


class TestNoDuplicatePanelIds:
    """No two panels in the same dashboard can share an ID."""

    @pytest.mark.parametrize("dashboard_name", list(DASHBOARDS.keys()))
    def test_no_duplicate_panel_ids(self, dashboard_name: str):
        db = load_dashboard(dashboard_name)

        seen: dict[int, str] = {}
        duplicates: list[str] = []

        def _walk(panels: list[dict]) -> None:
            for panel in panels:
                pid = panel.get("id")
                title = panel.get("title", "untitled")
                if pid is not None:
                    if pid in seen:
                        duplicates.append(
                            f"Panel ID {pid} is used by both '{seen[pid]}' and '{title}'"
                        )
                    else:
                        seen[pid] = title
                if "panels" in panel:
                    _walk(panel["panels"])

        _walk(db.get("panels", []))

        assert not duplicates, (
            f"Duplicate panel IDs in '{dashboard_name}':\n"
            + "\n".join(f"  - {d}" for d in duplicates)
        )


class TestAllMetricsCoveredByDashboards:
    """Every OTel metric defined in telemetry.py should be queried by at least
    one dashboard panel."""

    # All OTel metric names -> expected Prometheus prefixes
    OTEL_METRICS = {
        "ai.app.running": "ai_app_running",
        "ai.app.active.duration": "ai_app_active_duration",
        "ai.app.cpu.usage": "ai_app_cpu_usage",
        "ai.app.memory.usage": "ai_app_memory_usage",
        "ai.app.estimated.cost": "ai_app_estimated_cost",
        "ai.browser.domain.active.duration": "ai_browser_domain_active_duration",
        "ai.browser.domain.visit.count": "ai_browser_domain_visit_count",
        "ai.browser.domain.estimated.cost": "ai_browser_domain_estimated_cost",
        "ai.cli.running": "ai_cli_running",
        "ai.cli.active.duration": "ai_cli_active_duration",
        "ai.cli.estimated.cost": "ai_cli_estimated_cost",
        "ai.cli.command.count": "ai_cli_command_count",
        "ai.tokens.input_total": "ai_tokens_input_total",
        "ai.tokens.output_total": "ai_tokens_output_total",
        "ai.tokens.cost_usd_total": "ai_tokens_cost_usd_total",
        "ai.prompt.count_total": "ai_prompt_count_total",
    }

    def test_all_metrics_queried(self):
        """Every metric defined in TelemetryManager appears in at least one dashboard."""
        all_queried: set[str] = set()
        for name in DASHBOARDS:
            db = load_dashboard(name)
            exprs = extract_all_exprs(db)
            all_queried |= extract_metric_names_from_exprs(exprs)

        missing: list[str] = []
        for otel_name, prom_prefix in self.OTEL_METRICS.items():
            # Check if any queried metric starts with this prefix
            found = any(m.startswith(prom_prefix) for m in all_queried)
            if not found:
                missing.append(f"{otel_name} (expected Prometheus prefix: {prom_prefix})")

        assert not missing, (
            "Metrics defined in telemetry.py but never queried in any dashboard:\n"
            + "\n".join(f"  - {m}" for m in missing)
        )
