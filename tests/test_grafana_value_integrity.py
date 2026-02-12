"""Evaluation tests for Grafana dashboard query correctness."""

from __future__ import annotations

import json
from pathlib import Path


_DASHBOARDS_DIR = Path("infra/grafana/dashboards")
_PROM_DS_UID = "prometheus-vps"


def _load_dashboard(filename: str) -> dict:
    path = _DASHBOARDS_DIR / filename
    return json.loads(path.read_text(encoding="utf-8"))


def _find_panel(dashboard: dict, title: str) -> dict:
    for panel in dashboard.get("panels", []):
        if panel.get("title") == title:
            return panel
    raise AssertionError(f"Panel not found: {title}")


def _iter_dict_nodes(node: object):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _iter_dict_nodes(value)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_dict_nodes(item)


def test_browser_panels_apply_global_filters() -> None:
    dashboard = _load_dashboard("browser-ai-usage.json")

    for title in ("Duration by Category", "Domain Details"):
        panel = _find_panel(dashboard, title)
        expr = panel["targets"][0]["expr"]
        assert 'host_name=~"$host"' in expr
        assert 'browser_name=~"$browser"' in expr
        assert 'ai_category=~"$category"' in expr
        assert 'usage_source=~"$source"' in expr


def test_cost_accumulation_uses_running_total_counters() -> None:
    dashboard = _load_dashboard("unified-cost.json")
    panel = _find_panel(dashboard, "Cost Accumulation Over Time")

    for target in panel.get("targets", []):
        expr = target["expr"]
        assert "increase(" not in expr
        assert "$__rate_interval" not in expr
        assert "_estimated_cost_USD_total" in expr or "_cost_usd_total" in expr


def test_all_dashboards_use_provisioned_prometheus_uid() -> None:
    for path in sorted(_DASHBOARDS_DIR.glob("*.json")):
        dashboard = json.loads(path.read_text(encoding="utf-8"))
        for node in _iter_dict_nodes(dashboard):
            if node.get("type") == "prometheus" and "uid" in node:
                assert node["uid"] == _PROM_DS_UID, f"{path}: wrong datasource uid"
