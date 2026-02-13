"""Ensure extension tracking data stays aligned with backend configuration."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

_AI_CONFIG_PATH = Path("src/ai_cost_observer/data/ai_config.yaml")
_BACKGROUND_JS_PATH = Path("chrome-extension/background.js")
_POPUP_JS_PATH = Path("chrome-extension/popup.js")


def _load_config_domains_and_costs() -> tuple[set[str], dict[str, float]]:
    payload = yaml.safe_load(_AI_CONFIG_PATH.read_text(encoding="utf-8"))
    domains = payload.get("ai_domains", [])
    expected_domains = {entry["domain"] for entry in domains}
    expected_costs = {entry["domain"]: float(entry.get("cost_per_hour", 0)) for entry in domains}
    return expected_domains, expected_costs


def _extract_background_domains() -> set[str]:
    src = _BACKGROUND_JS_PATH.read_text(encoding="utf-8")
    match = re.search(r"const DEFAULT_AI_DOMAINS = \[(.*?)\];", src, flags=re.S)
    assert match, "DEFAULT_AI_DOMAINS constant not found in background.js"
    return {m.group(1) for m in re.finditer(r'"([^"]+)"', match.group(1))}


def _extract_popup_cost_rates() -> dict[str, float]:
    src = _POPUP_JS_PATH.read_text(encoding="utf-8")
    match = re.search(r"const DEFAULT_COST_RATES = \{(.*?)\};", src, flags=re.S)
    assert match, "DEFAULT_COST_RATES constant not found in popup.js"
    rates: dict[str, float] = {}
    for pair in re.finditer(r'"([^"]+)":\s*([0-9]+(?:\.[0-9]+)?)', match.group(1)):
        rates[pair.group(1)] = float(pair.group(2))
    return rates


def test_background_domains_match_ai_config() -> None:
    expected_domains, _ = _load_config_domains_and_costs()
    background_domains = _extract_background_domains()
    assert background_domains == expected_domains


def test_popup_cost_rates_match_ai_config() -> None:
    expected_domains, expected_costs = _load_config_domains_and_costs()
    popup_rates = _extract_popup_cost_rates()

    assert set(popup_rates) == expected_domains
    for domain, expected in expected_costs.items():
        assert popup_rates[domain] == pytest.approx(expected, rel=0, abs=1e-12)


def test_background_export_requires_success_response_before_ack() -> None:
    src = _BACKGROUND_JS_PATH.read_text(encoding="utf-8")

    assert "if (!response.ok)" in src
    assert "pendingDeltas = {};" in src
    assert "await updateDailyTotals(events);" in src

    clear_idx = src.index("pendingDeltas = {};")
    totals_idx = src.index("await updateDailyTotals(events);")
    assert clear_idx < totals_idx
