#!/usr/bin/env python3
"""Smoke tests for the deterministic network quote engine."""

from __future__ import annotations

import json
from pathlib import Path

import quote_engine


ROOT = Path(__file__).resolve().parents[1]


def load_example(name: str) -> dict:
    with (ROOT / "examples" / name).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def assert_equal(actual, expected, label: str) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def main() -> None:
    catalog = quote_engine.load_catalog(quote_engine.DEFAULT_CATALOG)
    rules = quote_engine.load_json(quote_engine.DEFAULT_RULES)

    direct = quote_engine.evaluate(load_example("input_example.json"), catalog, rules)
    assert_equal(direct["status"], "ok", "direct status")
    assert_equal(direct["contract_validation"]["valid"], True, "direct contract validation")
    assert_equal(direct["recommendation"]["selected_products"][2]["quantity"], 2, "direct edge quantity")

    handoff = quote_engine.evaluate(load_example("input_handoff_example.json"), catalog, rules)
    assert_equal(handoff["status"], "ok", "handoff status")
    assert_equal(handoff["contract_validation"]["valid"], True, "handoff contract validation")

    missing = quote_engine.evaluate(
        {
            "handoff": {
                "contract_version": "1.0",
                "source_skill": "diseno-redes-empresariales",
                "target_skill": "cotizacion-redes-empresariales",
                "quote_ready_input": {
                    "site_name": "Sitio incompleto",
                    "technical_design": {
                        "recommended_access_switches": 2
                    },
                    "needs": {
                        "switching": True
                    }
                }
            }
        },
        catalog,
        rules,
    )
    assert_equal(missing["status"], "needs_input", "missing status")
    assert "technical_design.required_switch_ports_with_reserve" in missing["missing_information"]

    print("All quote engine smoke tests passed.")


if __name__ == "__main__":
    main()
