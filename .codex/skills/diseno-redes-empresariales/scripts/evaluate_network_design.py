#!/usr/bin/env python3
"""Deterministic evaluator for enterprise network design sizing."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RULES = ROOT / "rules" / "technical_rules.json"
REPO_ROOT = Path(__file__).resolve().parents[4]
SHARED_NETWORK_DIR = REPO_ROOT / ".codex" / "shared" / "network"

if str(SHARED_NETWORK_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_NETWORK_DIR))

from contract_validation import prune_unknowns, validate_quote_ready_input, wrap_handoff


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def norm_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    replacements = str.maketrans("áéíóúüñ", "aeiouun")
    return str(value).strip().lower().translate(replacements).replace("-", "_").replace(" ", "_")


def normalize_choice(value: Any, aliases: Dict[str, str], default: str) -> str:
    normalized = norm_text(value, default)
    return aliases.get(normalized, normalized)


DEVICE_ALIASES = {
    "laptop": "laptops",
    "laptops": "laptops",
    "portatil": "laptops",
    "portatiles": "laptops",
    "notebook": "laptops",
    "notebooks": "laptops",
    "pc": "laptops",
    "pcs": "laptops",
    "computador": "laptops",
    "computadores": "laptops",
    "mobile": "mobiles",
    "mobiles": "mobiles",
    "movil": "mobiles",
    "moviles": "mobiles",
    "celular": "mobiles",
    "celulares": "mobiles",
    "smartphone": "mobiles",
    "smartphones": "mobiles",
    "iot": "iot",
    "sensor": "iot",
    "sensores": "iot",
    "phone": "phones",
    "phones": "phones",
    "telefono": "phones",
    "telefonos": "phones",
    "voip": "phones",
    "camera": "cameras",
    "cameras": "cameras",
    "camara": "cameras",
    "camaras": "cameras",
    "printer": "printers",
    "printers": "printers",
    "impresora": "printers",
    "impresoras": "printers",
    "server": "servers",
    "servers": "servers",
    "servidor": "servers",
    "servidores": "servers"
}


SERVICE_ALIASES = {
    "voice": "voice",
    "voz": "voice",
    "video": "video",
    "erp": "erp",
    "pos": "pos",
    "ot": "ot_control",
    "control_ot": "ot_control",
    "ot_control": "ot_control",
    "control_industrial": "ot_control",
    "security": "security",
    "seguridad": "security"
}

TRAFFIC_PROFILE_ALIASES = {
    "bajo": "low",
    "baja": "low",
    "low": "low",
    "medio": "medium",
    "media": "medium",
    "moderado": "medium",
    "medium": "medium",
    "alto": "high",
    "alta": "high",
    "high": "high",
    "critico": "critical",
    "critica": "critical",
    "critical": "critical",
}

ENVIRONMENT_ALIASES = {
    "oficina_pequena": "small_office",
    "small_office": "small_office",
    "sucursal": "small_office",
    "corporativo": "corporate",
    "corporativa": "corporate",
    "corporate": "corporate",
    "alta_densidad": "high_density",
    "alta_concentracion": "high_density",
    "high_density": "high_density",
    "industrial": "industrial",
    "mixto": "mixed",
    "mixta": "mixed",
    "mixed": "mixed",
}

BUDGET_LEVEL_ALIASES = {
    "bajo": "low",
    "baja": "low",
    "low": "low",
    "medio": "medium",
    "media": "medium",
    "medium": "medium",
    "alto": "high",
    "alta": "high",
    "high": "high",
}


def ceil(value: float) -> int:
    return int(math.ceil(max(value, 0)))


def normalize_redundancy(value: Any) -> str:
    if isinstance(value, bool):
        return "high" if value else "false"
    aliases = {
        "none": "false",
        "no": "false",
        "false": "false",
        "basic": "basic",
        "medium": "basic",
        "alta": "high",
        "high": "high",
        "ha": "high",
        "mission": "mission_critical",
        "mission_critical": "mission_critical",
        "critical": "mission_critical"
    }
    return aliases.get(norm_text(value, "false"), norm_text(value, "false"))


def normalize_devices(raw: Dict[str, Any]) -> Tuple[Dict[str, int], List[str]]:
    assumptions: List[str] = []
    devices: Dict[str, int] = {}
    raw_devices = raw.get("devices")
    if isinstance(raw_devices, dict):
        for key, value in raw_devices.items():
            try:
                count = int(value)
            except (TypeError, ValueError):
                continue
            if count > 0:
                device_type = DEVICE_ALIASES.get(norm_text(key, "unknown"), norm_text(key, "unknown"))
                devices[device_type] = devices.get(device_type, 0) + count

    if not devices and raw.get("total_devices") is not None:
        total = int(raw["total_devices"])
        if total > 0:
            devices["unknown"] = total
            assumptions.append("Only total_devices was provided; using generic endpoint defaults.")
    return devices, assumptions


def required_fields(data: Dict[str, Any], devices: Dict[str, int]) -> List[str]:
    missing = []
    if not devices:
        missing.append("devices or total_devices")
    if not data.get("traffic_profile"):
        missing.append("traffic_profile")
    if data.get("floors") is None and data.get("area_m2") is None:
        missing.append("floors or area_m2")
    return missing


def get_device_rule(rules: Dict[str, Any], device_type: str) -> Dict[str, Any]:
    defaults = rules["device_type_defaults"]
    return defaults.get(device_type, defaults["unknown"])


def calculate_clients(
    devices: Dict[str, int], traffic_profile: str, rules: Dict[str, Any]
) -> Tuple[Dict[str, Any], List[str]]:
    details: Dict[str, Any] = {}
    assumptions: List[str] = []
    concurrent_total = wired_ports = poe_ports = raw_throughput = 0.0

    for device_type, count in sorted(devices.items()):
        device_rule = get_device_rule(rules, device_type)
        if device_type not in rules["device_type_defaults"]:
            assumptions.append(f"Device type '{device_type}' is unknown; using generic endpoint defaults.")
        concurrent = count * float(device_rule["concurrency_ratio"])
        wired = count * float(device_rule["wired_ratio"])
        poe = count * float(device_rule["poe_ratio"])
        mbps = float(device_rule["mbps_by_profile"][traffic_profile])
        traffic = concurrent * mbps
        concurrent_total += concurrent
        wired_ports += wired
        poe_ports += poe
        raw_throughput += traffic
        details[device_type] = {
            "count": count,
            "concurrency_ratio": device_rule["concurrency_ratio"],
            "concurrent_clients": round(concurrent, 2),
            "wired_ports_estimate": round(wired, 2),
            "poe_ports_estimate": round(poe, 2),
            "mbps_per_concurrent_client": mbps,
            "traffic_mbps": round(traffic, 2),
            "recommended_vlan": device_rule["recommended_vlan"]
        }

    headroom = float(rules["traffic_profiles"][traffic_profile]["internet_headroom_factor"])
    return {
        "devices": details,
        "total_devices": sum(devices.values()),
        "concurrent_clients": round(concurrent_total, 2),
        "estimated_raw_throughput_mbps": round(raw_throughput, 2),
        "internet_headroom_factor": headroom,
        "estimated_required_throughput_mbps": round(raw_throughput * headroom, 2),
        "wired_ports_before_reserve": round(wired_ports, 2),
        "poe_ports_before_reserve": round(poe_ports, 2)
    }, assumptions


def derive_vlans(
    devices: Dict[str, int], critical_services: Iterable[str], rules: Dict[str, Any]
) -> Tuple[List[str], List[Dict[str, str]]]:
    segmentation = rules["segmentation"]
    vlans = set(segmentation["base_vlans"])
    applied = [{
        "id": "SEG-001",
        "reason": "Base segmentation separates management, corporate and guest traffic.",
        "calculation": "base_vlans = management, corporate, guest"
    }]

    added_device_vlans = []
    for device_type, count in sorted(devices.items()):
        if count > 0 and device_type in segmentation["device_vlans"]:
            vlan = segmentation["device_vlans"][device_type]
            vlans.add(vlan)
            added_device_vlans.append(vlan)
    if added_device_vlans:
        applied.append({
            "id": "SEG-002",
            "reason": "Dedicated VLANs isolate device classes with different risk and traffic behavior.",
            "calculation": ", ".join(sorted(set(added_device_vlans)))
        })

    added_service_vlans = []
    for service in critical_services:
        service_key = norm_text(service)
        if service_key in segmentation["critical_service_vlans"]:
            vlan = segmentation["critical_service_vlans"][service_key]
            vlans.add(vlan)
            added_service_vlans.append(vlan)
    if added_service_vlans:
        applied.append({
            "id": "SEG-003",
            "reason": "Critical services need restricted policy and QoS-aware segmentation.",
            "calculation": ", ".join(sorted(set(added_service_vlans)))
        })
    return sorted(vlans), applied


def effective_redundancy(
    requested: Any, traffic_profile: str, critical_services: List[str], rules: Dict[str, Any]
) -> Tuple[str, List[Dict[str, str]]]:
    level = normalize_redundancy(requested)
    if level not in rules["redundancy"]["levels"]:
        level = "false"
    applied: List[Dict[str, str]] = []
    if traffic_profile == "critical" or critical_services:
        minimum = rules["redundancy"]["critical_services_raise_minimum_to"]
        ranks = {"false": 0, "basic": 1, "high": 2, "mission_critical": 3}
        if ranks[level] < ranks[minimum]:
            applied.append({
                "id": "RED-002",
                "reason": "Critical services raise minimum availability target.",
                "calculation": f"requested={level}; effective={minimum}"
            })
            level = minimum
    red = rules["redundancy"]["levels"][level]
    applied.append({
        "id": "RED-001",
        "reason": "Availability design derived from effective redundancy level.",
        "calculation": f"level={level}; edge_devices={red['edge_devices']}; dual_isp={red.get('dual_isp', False)}; core_pair={red.get('core_pair', False)}"
    })
    return level, applied


def calculate_wireless(
    data: Dict[str, Any], client_summary: Dict[str, Any], rules: Dict[str, Any],
    traffic_profile: str, environment: str
) -> Tuple[Dict[str, Any], List[Dict[str, str]]]:
    env = rules["environment_profiles"][environment]
    traffic = rules["traffic_profiles"][traffic_profile]
    floors = int(data.get("floors") or 1)
    area_m2 = float(data.get("area_m2") or floors * env["coverage_m2_per_ap"])
    wireless_clients = max(client_summary["concurrent_clients"] - client_summary["wired_ports_before_reserve"], 0)
    target_clients = max(1, float(traffic["target_clients_per_ap"]) * float(env["capacity_factor"]))
    coverage = max(1, float(env["coverage_m2_per_ap"]) * float(traffic["coverage_multiplier"]))
    min_by_floor = int(env["min_ap_per_floor"]) * floors
    by_capacity = ceil(wireless_clients / target_clients)
    by_coverage = ceil(area_m2 / coverage)
    ap_count = max(by_capacity, by_coverage, min_by_floor)
    applied = [
        {"id": "WIFI-001", "reason": "APs sized by concurrent wireless client capacity.", "calculation": f"ceil({wireless_clients:.2f} / {target_clients:.2f}) = {by_capacity}"},
        {"id": "WIFI-002", "reason": "APs sized by adjusted RF coverage area.", "calculation": f"ceil({area_m2:.2f} / {coverage:.2f}) = {by_coverage}"},
        {"id": "WIFI-003", "reason": "AP count must satisfy minimum distribution per floor.", "calculation": f"{env['min_ap_per_floor']} AP/floor * {floors} floors = {min_by_floor}"}
    ]
    return {
        "recommended_access_points": ap_count,
        "recommended_ap_per_floor": ceil(ap_count / floors),
        "wireless_concurrent_clients_estimate": round(wireless_clients, 2),
        "ap_count_by_capacity": by_capacity,
        "ap_count_by_coverage": by_coverage,
        "ap_minimum_by_floor": min_by_floor,
        "adjusted_target_clients_per_ap": round(target_clients, 2),
        "adjusted_coverage_m2_per_ap": round(coverage, 2),
        "controller_or_cloud_management_recommended": ap_count >= int(rules["wireless"]["controller_recommended_when_ap_count_gte"]),
        "load_balancing_recommended": ap_count >= int(rules["wireless"]["load_balancing_recommended_when_ap_count_gte"])
    }, applied


def select_edge_tier(
    client_summary: Dict[str, Any], redundancy_level: str, rules: Dict[str, Any]
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    clients = client_summary["concurrent_clients"]
    throughput = client_summary["estimated_required_throughput_mbps"]
    selected = rules["edge_device_tiers"][-1]
    for tier in rules["edge_device_tiers"]:
        if clients <= tier["max_supported_clients"] and throughput <= tier["recommended_throughput_mbps"]:
            selected = tier
            break
    red = rules["redundancy"]["levels"][redundancy_level]
    result = {
        "tier": selected["name"],
        "edge_router_firewall_count": int(red["edge_devices"]),
        "tier_supported_clients": selected["max_supported_clients"],
        "tier_recommended_throughput_mbps": selected["recommended_throughput_mbps"],
        "ha_pair": int(red["edge_devices"]) > 1,
        "dual_isp": bool(red.get("dual_isp", False)),
        "selection_basis": selected["use_when"]
    }
    applied = {
        "id": "EDGE-001",
        "reason": "Selected smallest edge tier that satisfies client and throughput demand.",
        "calculation": f"clients {clients:.2f} <= {selected['max_supported_clients']}; throughput {throughput:.2f} Mbps <= {selected['recommended_throughput_mbps']} Mbps"
    }
    return result, applied


def calculate_switching(
    data: Dict[str, Any], client_summary: Dict[str, Any], wireless: Dict[str, Any],
    vlan_count: int, redundancy_level: str, rules: Dict[str, Any]
) -> Tuple[Dict[str, Any], List[Dict[str, str]]]:
    sw = rules["switching"]
    floors = int(data.get("floors") or 1)
    wired_ports = client_summary["wired_ports_before_reserve"] + wireless["recommended_access_points"]
    poe_ports = client_summary["poe_ports_before_reserve"] + wireless["recommended_access_points"]
    ports_with_reserve = ceil(wired_ports * float(sw["port_reserve_factor"]))
    poe_with_reserve = ceil(poe_ports * float(sw["poe_reserve_factor"]))
    port_size = 24 if ports_with_reserve <= 24 else 48
    access_switches = max(1, ceil(ports_with_reserve / port_size))
    needs_distribution = (
        floors >= int(sw["distribution_required_when_floors_gte"])
        or access_switches >= int(sw["distribution_required_when_access_switches_gte"])
    )
    needs_l3 = vlan_count >= int(sw["l3_core_required_when_vlans_gte"])
    red = rules["redundancy"]["levels"][redundancy_level]
    result = {
        "recommended_access_switches": access_switches,
        "access_switch_port_size": port_size,
        "required_switch_ports_with_reserve": ports_with_reserve,
        "required_poe_ports_with_reserve": poe_with_reserve,
        "distribution_layer_recommended": needs_distribution,
        "l3_core_or_distribution_recommended": needs_l3,
        "stacking_or_mlag_recommended": bool(red.get("stacking", False)) and access_switches > 1,
        "redundant_core_pair_recommended": bool(red.get("core_pair", False)) and (needs_distribution or needs_l3)
    }
    applied = [{
        "id": "SW-001",
        "reason": "Access switch count includes wired endpoints, AP uplinks and reserve.",
        "calculation": f"ceil(({wired_ports:.2f}) * {sw['port_reserve_factor']}) = {ports_with_reserve}; switches = ceil({ports_with_reserve} / {port_size}) = {access_switches}"
    }]
    if needs_l3:
        applied.append({
            "id": "SW-002",
            "reason": "Multiple VLANs require Layer 3 gateway design at core/distribution.",
            "calculation": f"{vlan_count} VLANs >= {sw['l3_core_required_when_vlans_gte']}"
        })
    return result, applied


def estimate_cost(
    wireless: Dict[str, Any], switching: Dict[str, Any], edge: Dict[str, Any],
    budget_level: str, rules: Dict[str, Any]
) -> Dict[str, Any]:
    budget_level = budget_level if budget_level in rules["budget"]["level_multipliers"] else "medium"
    ap_cost = rules["wireless"]["ap_cost_by_budget"][budget_level]
    edge_tier = next(t for t in rules["edge_device_tiers"] if t["name"] == edge["tier"])
    sw_costs = rules["switching"]["costs"]
    access_cost = sw_costs["access_24_poe"] if switching["access_switch_port_size"] == 24 else sw_costs["access_48_poe"]
    subtotal = wireless["recommended_access_points"] * ap_cost
    subtotal += switching["recommended_access_switches"] * access_cost
    subtotal += edge["edge_router_firewall_count"] * edge_tier["typical_cost"]
    if wireless["controller_or_cloud_management_recommended"]:
        subtotal += rules["wireless"]["controller_cost"]
    if switching["distribution_layer_recommended"]:
        subtotal += sw_costs["distribution_l3"]
    if switching["redundant_core_pair_recommended"]:
        subtotal += sw_costs["core_l3_pair"]
    adjusted = subtotal * rules["budget"]["level_multipliers"][budget_level]
    return {
        "budget_level_used": budget_level,
        "rough_equipment_cost_usd": ceil(adjusted),
        "includes": ["APs", "PoE access switching", "edge router/firewall", "controller/cloud management when applicable", "distribution/core allowance when applicable"],
        "excludes": ["cabling", "licenses", "installation", "support", "taxes", "site survey"]
    }


def budget_constraints(data: Dict[str, Any], redundancy_level: str, estimate: Dict[str, Any], rules: Dict[str, Any]) -> List[Dict[str, str]]:
    constraints: List[Dict[str, str]] = []
    budget_level = norm_text(data.get("budget_level"), "medium")
    if budget_level == "low" and redundancy_level in {"high", "mission_critical"}:
        constraints.append({"id": "BUD-001", "severity": "high", "message": rules["budget"]["conflict_rules"][0]["message"]})
    numeric_budget = data.get("budget_usd")
    if numeric_budget is not None:
        try:
            budget_usd = float(numeric_budget)
        except (TypeError, ValueError):
            budget_usd = None
        if budget_usd is not None and budget_usd < estimate["rough_equipment_cost_usd"]:
            constraints.append({
                "id": "BUD-002",
                "severity": "high",
                "message": f"{rules['budget']['conflict_rules'][1]['message']} budget={budget_usd:.0f}, estimate={estimate['rough_equipment_cost_usd']}"
            })
    return constraints


def qos_reasons(
    traffic_profile: str, critical_services: List[str], wireless: Dict[str, Any], rules: Dict[str, Any]
) -> Tuple[List[str], List[Dict[str, str]]]:
    reasons: List[str] = []
    applied: List[Dict[str, str]] = []
    if rules["traffic_profiles"][traffic_profile]["requires_qos"] or critical_services:
        reasons.append("Apply QoS for latency-sensitive or critical traffic.")
        applied.append({
            "id": "QOS-001",
            "reason": "Traffic profile or critical services require QoS policy.",
            "calculation": f"traffic_profile={traffic_profile}; services={critical_services}"
        })
    fast_services = set(rules["wireless"]["fast_roaming_required_for_services"])
    if fast_services.intersection({norm_text(s) for s in critical_services}):
        reasons.append("Enable fast roaming and band steering/load balancing for mobile voice/video clients.")
    if wireless["load_balancing_recommended"]:
        reasons.append("Enable WLAN load balancing because multiple APs share client density.")
    return reasons, applied


def vendor_notes(manufacturers: List[str]) -> List[str]:
    if not manufacturers:
        return ["No manufacturer specified; keep design vendor-neutral and validate final SKUs against datasheets."]
    names = [str(m).strip() for m in manufacturers if str(m).strip()]
    notes = [f"Manufacturer candidates: {', '.join(names)}."]
    if len(names) > 1:
        notes.append("Avoid mixing WLAN controller ecosystems unless managed through a common platform or standards-only design.")
    notes.append("Verify AP radio count, PoE class, firewall inspected throughput, VPN throughput and license limits before purchase.")
    return notes


def evaluate(data: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    devices, assumptions = normalize_devices(data)
    missing = required_fields(data, devices)
    if missing:
        return {
            "status": "needs_input",
            "missing_fields": missing,
            "message": "Cannot produce a deterministic design without the missing fields.",
            "assumptions": assumptions
        }

    traffic_profile = normalize_choice(data.get("traffic_profile"), TRAFFIC_PROFILE_ALIASES, "medium")
    if traffic_profile not in rules["traffic_profiles"]:
        assumptions.append(f"Unknown traffic_profile '{data.get('traffic_profile')}'; using medium.")
        traffic_profile = "medium"
    environment = normalize_choice(data.get("environment"), ENVIRONMENT_ALIASES, "corporate")
    if environment not in rules["environment_profiles"]:
        assumptions.append(f"Unknown environment '{data.get('environment')}'; using corporate.")
        environment = "corporate"
    budget_level = normalize_choice(data.get("budget_level"), BUDGET_LEVEL_ALIASES, "medium")
    if budget_level not in rules["budget"]["level_multipliers"]:
        assumptions.append(f"Unknown budget_level '{data.get('budget_level')}'; using medium.")
        budget_level = "medium"

    critical_services = [
        SERVICE_ALIASES.get(norm_text(s), norm_text(s))
        for s in data.get("critical_services", [])
    ]
    redundancy_level, redundancy_rules = effective_redundancy(data.get("redundancy_required", "false"), traffic_profile, critical_services, rules)
    client_summary, client_assumptions = calculate_clients(devices, traffic_profile, rules)
    assumptions.extend(client_assumptions)
    vlans, segmentation_rules = derive_vlans(devices, critical_services, rules)
    wireless, wifi_rules = calculate_wireless(data, client_summary, rules, traffic_profile, environment)
    edge, edge_rule = select_edge_tier(client_summary, redundancy_level, rules)
    switching, switching_rules = calculate_switching(data, client_summary, wireless, len(vlans), redundancy_level, rules)
    estimate = estimate_cost(wireless, switching, edge, budget_level, rules)
    constraints = budget_constraints(data, redundancy_level, estimate, rules)
    qos, qos_rules = qos_reasons(traffic_profile, critical_services, wireless, rules)

    applied_rules = wifi_rules + [edge_rule] + switching_rules + segmentation_rules + redundancy_rules + qos_rules
    for constraint in constraints:
        applied_rules.append({"id": constraint["id"], "reason": constraint["message"], "calculation": "budget constraint"})

    technical_reasons = [
        f"Total devices: {client_summary['total_devices']}; estimated concurrent clients: {client_summary['concurrent_clients']}.",
        f"Required internet/headend throughput estimate: {client_summary['estimated_required_throughput_mbps']} Mbps after headroom.",
        f"Wi-Fi AP count is max(capacity {wireless['ap_count_by_capacity']}, coverage {wireless['ap_count_by_coverage']}, floor minimum {wireless['ap_minimum_by_floor']}).",
        f"Edge tier '{edge['tier']}' satisfies client and throughput thresholds.",
        f"Segmentation creates {len(vlans)} VLANs: {', '.join(vlans)}."
    ] + qos

    return {
        "status": "ok",
        "site_name": data.get("site_name"),
        "decision": {
            "architecture": "enterprise_lan_wlan_edge",
            "summary": f"Recommend {wireless['recommended_access_points']} APs, {switching['recommended_access_switches']} access switches, {edge['edge_router_firewall_count']} {edge['tier']} edge device(s), and {len(vlans)} VLANs.",
            "effective_redundancy_level": redundancy_level
        },
        "normalized_input": {
            "traffic_profile": traffic_profile,
            "environment": environment,
            "budget_level": budget_level
        },
        "sizing": {
            "client_and_throughput": client_summary,
            "wireless": wireless,
            "switching": switching,
            "edge": edge,
            "vlans": vlans,
            "estimated_cost": estimate
        },
        "rules_applied": applied_rules,
        "technical_reasons": technical_reasons,
        "constraints": constraints,
        "assumptions": assumptions,
        "vendor_notes": vendor_notes(data.get("manufacturers", [])),
        "knowledge_suggestions": [
            "knowledge/dimensioning-principles.md",
            "knowledge/segmentation-and-security.md",
            "knowledge/redundancy-and-availability.md",
            "knowledge/vendor-guidance.md"
        ]
    }


def manufacturer_preference_from_input(data: Dict[str, Any]) -> Any:
    """Return a deterministic manufacturer preference only when the input truly provides one."""
    direct = data.get("manufacturer_preference")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    manufacturers = data.get("manufacturers")
    if isinstance(manufacturers, list):
        names = [str(item).strip() for item in manufacturers if str(item).strip()]
        if len(names) == 1:
            return names[0]
    return None


def build_quote_ready_input(source_input: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    """Build the canonical quote-ready payload from a successful technical design."""
    if result.get("status") != "ok":
        raise ValueError("Cannot build quote-ready input from a non-ok design result.")

    normalized = result.get("normalized_input") or {}
    sizing = result.get("sizing") or {}
    wireless = sizing.get("wireless") or {}
    switching = sizing.get("switching") or {}
    edge = sizing.get("edge") or {}

    quote_ready_input = {
        "site_name": source_input.get("site_name"),
        "manufacturer_preference": manufacturer_preference_from_input(source_input),
        "budget_level": source_input.get("budget_level") or normalized.get("budget_level"),
        "budget_usd": source_input.get("budget_usd"),
        "technical_design": {
            "recommended_access_points": wireless.get("recommended_access_points"),
            "recommended_access_switches": switching.get("recommended_access_switches"),
            "required_switch_ports_with_reserve": switching.get("required_switch_ports_with_reserve"),
            "required_poe_ports_with_reserve": switching.get("required_poe_ports_with_reserve"),
            "effective_redundancy_level": result.get("decision", {}).get("effective_redundancy_level"),
            "edge_category": edge.get("tier"),
            "edge_router_firewall_count": edge.get("edge_router_firewall_count"),
            "estimated_required_throughput_mbps": sizing.get("client_and_throughput", {}).get("estimated_required_throughput_mbps"),
            "environment": normalized.get("environment"),
        },
        "needs": {
            "wireless": wireless.get("recommended_access_points") is not None,
            "switching": switching.get("recommended_access_switches") is not None,
            "edge": edge.get("tier") is not None,
            "support": (
                bool(source_input.get("needs", {}).get("support"))
                if isinstance(source_input.get("needs"), dict) and "support" in source_input["needs"]
                else None
            ),
        },
    }
    return prune_unknowns(quote_ready_input)


def build_design_handoff_payload(source_input: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    """Wrap the quote-ready payload in the shared handoff envelope."""
    quote_ready_input = build_quote_ready_input(source_input, result)
    validation = validate_quote_ready_input(quote_ready_input)
    if not validation["valid"]:
        missing = ", ".join(validation["missing_required_fields"])
        raise ValueError(f"Cannot emit handoff contract because required fields are missing: {missing}")
    payload = wrap_handoff(quote_ready_input)
    payload["handoff"]["validation"] = validation
    return payload


def build_design_explanation(source_input: Dict[str, Any], result: Dict[str, Any]) -> str:
    """Render a deterministic natural-language explanation for export."""
    if result.get("status") != "ok":
        missing = ", ".join(result.get("missing_fields", []))
        return (
            "No fue posible producir un diseño determinístico.\n\n"
            f"Campos faltantes: {missing or 'sin detalle'}.\n"
            f"Mensaje: {result.get('message', 'No additional context available.')}"
        )

    sizing = result.get("sizing", {})
    client_summary = sizing.get("client_and_throughput", {})
    wireless = sizing.get("wireless", {})
    switching = sizing.get("switching", {})
    edge = sizing.get("edge", {})
    constraints = result.get("constraints", [])
    assumptions = result.get("assumptions", [])
    rules = result.get("rules_applied", [])

    lines = [
        f"Sitio: {result.get('site_name') or source_input.get('site_name') or 'Sin nombre'}",
        "",
        "Decision recomendada",
        result.get("decision", {}).get("summary", "No summary available."),
        "",
        "Calculos clave",
        f"- Dispositivos totales: {client_summary.get('total_devices')}",
        f"- Clientes concurrentes estimados: {client_summary.get('concurrent_clients')}",
        f"- Throughput requerido estimado: {client_summary.get('estimated_required_throughput_mbps')} Mbps",
        (
            f"- Wi-Fi: {wireless.get('recommended_access_points')} APs "
            f"(capacidad {wireless.get('ap_count_by_capacity')}, "
            f"cobertura {wireless.get('ap_count_by_coverage')}, "
            f"minimo por piso {wireless.get('ap_minimum_by_floor')})"
        ),
        (
            f"- Switching: {switching.get('recommended_access_switches')} switches de acceso, "
            f"{switching.get('required_switch_ports_with_reserve')} puertos totales con reserva, "
            f"{switching.get('required_poe_ports_with_reserve')} puertos PoE con reserva"
        ),
        (
            f"- Edge: {edge.get('edge_router_firewall_count')} equipo(s) categoria {edge.get('tier')} "
            f"para {client_summary.get('estimated_required_throughput_mbps')} Mbps"
        ),
        f"- Segmentacion: {', '.join(sizing.get('vlans', []))}",
        "",
        "Reglas aplicadas",
    ]
    for rule in rules:
        lines.append(f"- {rule.get('id')}: {rule.get('reason')}")

    lines.extend(["", "Restricciones y supuestos"])
    if constraints:
        for constraint in constraints:
            lines.append(f"- {constraint.get('id')}: {constraint.get('message')}")
    else:
        lines.append("- Sin restricciones criticas.")
    if assumptions:
        for assumption in assumptions:
            lines.append(f"- Supuesto: {assumption}")
    else:
        lines.append("- Sin supuestos adicionales.")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate enterprise network design requirements.")
    parser.add_argument("--input", required=True, help="Path to a structured JSON requirement file.")
    parser.add_argument("--rules", default=str(DEFAULT_RULES), help="Path to technical_rules.json.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args()
    result = evaluate(load_json(Path(args.input)), load_json(Path(args.rules)))
    print(json.dumps(result, indent=2 if args.pretty else None, ensure_ascii=False))


if __name__ == "__main__":
    main()
