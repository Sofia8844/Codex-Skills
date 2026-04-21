"""Shared validation helpers for the design-to-quote handoff contract."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping


CONTRACT_VERSION = "1.0"
SOURCE_SKILL = "diseno-redes-empresariales"
TARGET_SKILL = "cotizacion-redes-empresariales"

KNOWN_NEEDS = ("wireless", "switching", "edge", "support")
ALWAYS_REQUIRED_FIELDS = ("site_name",)
REQUIRED_FIELDS_BY_NEED = {
    "wireless": ["technical_design.recommended_access_points"],
    "switching": [
        "technical_design.recommended_access_switches",
        "technical_design.required_switch_ports_with_reserve",
        "technical_design.required_poe_ports_with_reserve",
    ],
    "edge": [
        "technical_design.edge_category",
        "technical_design.estimated_required_throughput_mbps",
    ],
}
OPTIONAL_FIELDS = [
    "manufacturer_preference",
    "budget_level",
    "budget_usd",
    "technical_design.effective_redundancy_level",
    "technical_design.edge_router_firewall_count",
    "technical_design.environment",
    "needs.support",
]


def prune_unknowns(value: Any) -> Any:
    """Remove unknown values while preserving deterministic false and zero values."""
    if isinstance(value, dict):
        cleaned: Dict[str, Any] = {}
        for key, nested_value in value.items():
            pruned = prune_unknowns(nested_value)
            if pruned is None:
                continue
            if isinstance(pruned, dict) and not pruned:
                continue
            if isinstance(pruned, list) and not pruned:
                continue
            cleaned[key] = pruned
        return cleaned
    if isinstance(value, list):
        cleaned_list = [prune_unknowns(item) for item in value]
        return [
            item
            for item in cleaned_list
            if item is not None and not (isinstance(item, (dict, list)) and not item)
        ]
    return value


def get_nested(data: Mapping[str, Any], dotted_path: str) -> Any:
    """Read a nested value using dot notation."""
    current: Any = data
    for part in dotted_path.split("."):
        if not isinstance(current, Mapping):
            return None
        current = current.get(part)
    return current


def infer_active_needs(data: Mapping[str, Any]) -> Dict[str, bool]:
    """Resolve active scopes from explicit needs or known technical design fields."""
    technical_design = data.get("technical_design")
    technical_design = technical_design if isinstance(technical_design, Mapping) else {}
    raw_needs = data.get("needs")
    raw_needs = raw_needs if isinstance(raw_needs, Mapping) else {}

    active: Dict[str, bool] = {}
    for need in KNOWN_NEEDS:
        value = raw_needs.get(need)
        if isinstance(value, bool):
            active[need] = value

    inferred_checks = {
        "wireless": technical_design.get("recommended_access_points") is not None,
        "switching": any(
            technical_design.get(field) is not None
            for field in (
                "recommended_access_switches",
                "required_switch_ports_with_reserve",
                "required_poe_ports_with_reserve",
            )
        ),
        "edge": any(
            technical_design.get(field) is not None
            for field in (
                "edge_category",
                "estimated_required_throughput_mbps",
            )
        ),
    }
    for need, inferred in inferred_checks.items():
        active.setdefault(need, inferred)

    if "support" not in active and isinstance(raw_needs.get("support"), bool):
        active["support"] = bool(raw_needs["support"])

    return active


def determine_missing_required_fields(data: Mapping[str, Any]) -> List[str]:
    """Return missing required fields according to the active scope."""
    missing: List[str] = []
    if not data.get("site_name"):
        missing.append("site_name")

    active_needs = infer_active_needs(data)
    for need, fields in REQUIRED_FIELDS_BY_NEED.items():
        if not active_needs.get(need):
            continue
        for field in fields:
            if get_nested(data, field) is None:
                missing.append(field)
    return sorted(set(missing))


def validate_quote_ready_input(data: Mapping[str, Any]) -> Dict[str, Any]:
    """Validate the quote-ready payload used as handoff between skills."""
    active_needs = infer_active_needs(data)
    missing = determine_missing_required_fields(data)
    return {
        "contract_version": CONTRACT_VERSION,
        "valid": not missing,
        "active_needs": active_needs,
        "missing_required_fields": missing,
        "always_required_fields": list(ALWAYS_REQUIRED_FIELDS),
        "required_fields_by_need": REQUIRED_FIELDS_BY_NEED,
        "optional_fields": list(OPTIONAL_FIELDS),
        "rule": "Si el skill anterior lo sabe: lo envía. Si no lo sabe: se omite.",
    }


def extract_quote_ready_input(payload: Mapping[str, Any]) -> Dict[str, Any]:
    """Accept direct input or a wrapper with handoff.quote_ready_input."""
    handoff = payload.get("handoff")
    if isinstance(handoff, Mapping):
        quote_ready = handoff.get("quote_ready_input")
        if isinstance(quote_ready, Mapping):
            return dict(quote_ready)
    quote_ready = payload.get("quote_ready_input")
    if isinstance(quote_ready, Mapping):
        return dict(quote_ready)
    return dict(payload)


def wrap_handoff(quote_ready_input: Mapping[str, Any]) -> Dict[str, Any]:
    """Build the canonical handoff wrapper."""
    return {
        "handoff": {
            "contract_version": CONTRACT_VERSION,
            "source_skill": SOURCE_SKILL,
            "target_skill": TARGET_SKILL,
            "quote_ready_input": prune_unknowns(dict(quote_ready_input)),
        }
    }
