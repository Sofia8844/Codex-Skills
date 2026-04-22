#!/usr/bin/env python3
"""Pruebas rapidas del evaluador deterministico de diseno de red.

Este archivo valida que el motor tecnico siga devolviendo resultados esperados
para casos de referencia. Sirve para detectar regresiones cuando se cambian
reglas, normalizacion, handoff o calculos principales.
"""

from __future__ import annotations

import json
from pathlib import Path

import evaluate_network_design as evaluator


ROOT = Path(__file__).resolve().parents[1]


def load_example(name: str) -> dict:
    """Carga un JSON de ejemplo desde la carpeta `examples/`."""
    with (ROOT / "examples" / name).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def assert_equal(actual, expected, label: str) -> None:
    """Falla explicitamente cuando un valor no coincide con el esperado."""
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def main() -> None:
    """Ejecuta una bateria pequena de validaciones del evaluador."""
    rules = evaluator.load_json(evaluator.DEFAULT_RULES)

    # Caso corporativo multi-piso:
    # valida dimensionamiento principal y que el handoff generado sea usable.
    corporate = evaluator.evaluate(load_example("corporate-multifloor-input.json"), rules)
    assert_equal(corporate["status"], "ok", "corporate status")
    assert_equal(corporate["sizing"]["wireless"]["recommended_access_points"], 16, "corporate APs")
    assert_equal(corporate["sizing"]["switching"]["recommended_access_switches"], 3, "corporate switches")
    assert_equal(corporate["decision"]["effective_redundancy_level"], "high", "corporate redundancy")
    corporate_handoff = evaluator.build_design_handoff_payload(load_example("corporate-multifloor-input.json"), corporate)
    assert_equal(corporate_handoff["handoff"]["validation"]["valid"], True, "corporate handoff validation")
    assert_equal(corporate_handoff["handoff"]["quote_ready_input"]["technical_design"]["edge_router_firewall_count"], 2, "corporate handoff edge count")

    # Caso de oficina pequena:
    # asegura que el motor no sobredimensione y escoja un edge de sucursal.
    small = evaluator.evaluate(load_example("small-office-input.json"), rules)
    assert_equal(small["status"], "ok", "small office status")
    assert_equal(small["sizing"]["wireless"]["recommended_access_points"], 2, "small office APs")
    assert_equal(small["sizing"]["edge"]["tier"], "branch_router_firewall", "small office edge")

    # Caso industrial critico:
    # valida un escenario pesado con mayor cantidad de APs y conflicto presupuestal.
    industrial = evaluator.evaluate(load_example("industrial-critical-input.json"), rules)
    assert_equal(industrial["status"], "ok", "industrial status")
    assert_equal(industrial["sizing"]["wireless"]["recommended_access_points"], 51, "industrial APs")
    assert_equal(industrial["constraints"][0]["id"], "BUD-002", "industrial budget constraint")

    # Caso con aliases en espanol:
    # comprueba que el motor normalice correctamente entradas no canonicas.
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

    # Caso incompleto:
    # confirma que el motor no inventa datos y devuelve `needs_input`.
    incomplete = evaluator.evaluate({"traffic_profile": "high"}, rules)
    assert_equal(incomplete["status"], "needs_input", "incomplete status")
    assert "devices or total_devices" in incomplete["missing_fields"]

    print("All evaluator smoke tests passed.")


if __name__ == "__main__":
    main()
