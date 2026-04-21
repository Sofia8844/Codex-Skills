#!/usr/bin/env python3
"""Smoke tests for the deterministic network design evaluator."""

from __future__ import annotations

import json
from pathlib import Path

import evaluate_network_design as evaluator


ROOT = Path(__file__).resolve().parents[1]


def load_example(name: str) -> dict:
    with (ROOT / "examples" / name).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def assert_equal(actual, expected, label: str) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def main() -> None:
    rules = evaluator.load_json(evaluator.DEFAULT_RULES)

    corporate = evaluator.evaluate(load_example("corporate-multifloor-input.json"), rules)
    assert_equal(corporate["status"], "ok", "corporate status")
    assert_equal(corporate["sizing"]["wireless"]["recommended_access_points"], 16, "corporate APs")
    assert_equal(corporate["sizing"]["switching"]["recommended_access_switches"], 3, "corporate switches")
    assert_equal(corporate["decision"]["effective_redundancy_level"], "high", "corporate redundancy")
    corporate_handoff = evaluator.build_design_handoff_payload(load_example("corporate-multifloor-input.json"), corporate)
    assert_equal(corporate_handoff["handoff"]["validation"]["valid"], True, "corporate handoff validation")
    assert_equal(corporate_handoff["handoff"]["quote_ready_input"]["technical_design"]["edge_router_firewall_count"], 2, "corporate handoff edge count")

    small = evaluator.evaluate(load_example("small-office-input.json"), rules)
    assert_equal(small["status"], "ok", "small office status")
    assert_equal(small["sizing"]["wireless"]["recommended_access_points"], 2, "small office APs")
    assert_equal(small["sizing"]["edge"]["tier"], "branch_router_firewall", "small office edge")

    industrial = evaluator.evaluate(load_example("industrial-critical-input.json"), rules)
    assert_equal(industrial["status"], "ok", "industrial status")
    assert_equal(industrial["sizing"]["wireless"]["recommended_access_points"], 51, "industrial APs")
    assert_equal(industrial["constraints"][0]["id"], "BUD-002", "industrial budget constraint")

    spanish = evaluator.evaluate({
        "environment": "oficina pequena",
        "devices": {
            "portatiles": 30,
            "moviles": 20,
            "camaras": 4,
            "telefonos": 10
        },
        "traffic_profile": "alto",
        "floors": 1,
        "area_m2": 300,
        "redundancy_required": "alta",
        "budget_level": "bajo",
        "critical_services": ["voz", "seguridad"]
    }, rules)
    assert_equal(spanish["status"], "ok", "spanish aliases status")
    assert_equal(spanish["assumptions"], [], "spanish aliases assumptions")
    assert_equal(spanish["decision"]["effective_redundancy_level"], "high", "spanish redundancy")
    assert "voice" in spanish["sizing"]["vlans"]
    assert "security" in spanish["sizing"]["vlans"]

    incomplete = evaluator.evaluate({"traffic_profile": "high"}, rules)
    assert_equal(incomplete["status"], "needs_input", "incomplete status")
    assert "devices or total_devices" in incomplete["missing_fields"]

    print("All evaluator smoke tests passed.")


if __name__ == "__main__":
    main()
