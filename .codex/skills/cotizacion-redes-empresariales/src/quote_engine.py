#!/usr/bin/env python3
"""Deterministic quote engine for enterprise network catalog selection."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = ROOT / "catalog"
DEFAULT_RULES = ROOT / "rules" / "quote_rules.json"
REPO_ROOT = Path(__file__).resolve().parents[4]
SHARED_NETWORK_DIR = REPO_ROOT / ".codex" / "shared" / "network"

if str(SHARED_NETWORK_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_NETWORK_DIR))

from contract_validation import extract_quote_ready_input, validate_quote_ready_input


def load_json(path: Path) -> Dict[str, Any]:
    """Carga un archivo JSON desde disco usando UTF-8."""
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def normalize_quote_input(data: Dict[str, Any]) -> Dict[str, Any]:
    """Acepta input directo o wrappers emitidos por skills anteriores."""
    return extract_quote_ready_input(data)


def norm(value: Any, default: str = "") -> str:
    """Normaliza texto libre para comparaciones internas consistentes."""
    if value is None:
        return default
    replacements = str.maketrans("áéíóúüñÁÉÍÓÚÜÑ", "aeiouunAEIOUUN")
    return str(value).strip().lower().translate(replacements).replace("-", "_").replace(" ", "_")


def ceil(value: float) -> int:
    """Redondea requerimientos hacia arriba sin devolver negativos."""
    return int(math.ceil(max(value, 0)))


def money(value: float) -> float:
    """Redondea montos monetarios a dos decimales."""
    return round(float(value), 2)


def load_catalog(catalog_dir: Path) -> Dict[str, List[Dict[str, Any]]]:
    """Carga todos los archivos de catalogo usados por el motor."""
    return {
        "products": load_json(catalog_dir / "products.json")["products"],
        "licenses": load_json(catalog_dir / "licenses.json")["licenses"],
        "support": load_json(catalog_dir / "support.json")["support"],
        "accessories": load_json(catalog_dir / "accessories.json")["accessories"],
        "bundles": load_json(catalog_dir / "bundles.json")["bundles"],
    }


def index_by_sku(items: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Construye un indice por SKU para resolver relaciones rapidamente."""
    return {str(item["sku"]): item for item in items if item.get("sku")}


def item_summary(item: Dict[str, Any], quantity: int, reason: str) -> Dict[str, Any]:
    """Convierte un item de catalogo al formato estandar de salida."""
    price = float(item.get("price_list") or 0)
    return {
        "sku": item["sku"],
        "manufacturer": item.get("manufacturer"),
        "family": item.get("family"),
        "category": item.get("category"),
        "subcategory": item.get("subcategory"),
        "name": item.get("name"),
        "quantity": quantity,
        "unit_price": money(price),
        "total_price": money(price * quantity),
        "currency": item.get("currency", "USD"),
        "selection_reason": reason,
    }


def budget_rank(value: Any, policy: Dict[str, Any]) -> int:
    """Convierte una etiqueta de presupuesto en un rango numerico comparable."""
    ranks = policy["budget_rank"]
    return int(ranks.get(norm(value, "medium"), ranks["medium"]))


def product_budget_rank(product: Dict[str, Any], policy: Dict[str, Any]) -> int:
    """Lee el nivel de presupuesto recomendado declarado en un producto."""
    level = product.get("technical_attributes", {}).get("recommended_budget_level", "medium")
    return budget_rank(level, policy)


def active_products(products: List[Dict[str, Any]], discarded: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Conserva productos activos y registra los inactivos, o de otros estados como descartados."""
    active = []
    for product in products:
        status = norm(product.get("status"))
        if status == "active":
            active.append(product)
        else:
            discarded.append({
                "sku": product.get("sku"),
                "category": product.get("category"),
                "reason": f"Excluded because status is {product.get('status')}.",
                "rule_id": "QUOTE-001",
                "replacement_sku": product.get("replacement_sku"),
            })
    return active


def prefer_manufacturer(
    candidates: List[Dict[str, Any]],
    manufacturer: Optional[str],
    warnings: List[str],
    category: str,
) -> Tuple[List[Dict[str, Any]], bool]:
    """Aplica la preferencia de fabricante como filtro suave y genera advertencias."""
    if not manufacturer:
        warnings.append(f"No manufacturer preference provided for {category}; using vendor-neutral selection.")
        return candidates, False
    preferred = [p for p in candidates if norm(p.get("manufacturer")) == norm(manufacturer)]
    if preferred:
        return preferred, True
    warnings.append(f"No active {category} candidate found for preferred manufacturer {manufacturer}; using best available alternative.")
    return candidates, False


def filter_environment(candidates: List[Dict[str, Any]], environment: Optional[str]) -> Tuple[List[Dict[str, Any]], bool]:
    """Prioriza productos cuyo entorno declarado coincide con el disenio."""
    if not environment:
        return candidates, False
    env = norm(environment)
    matched = [
        p for p in candidates
        if env in {norm(v) for v in p.get("technical_attributes", {}).get("environment_fit", [])}
    ]
    return (matched, True) if matched else (candidates, False)


def filter_budget(candidates: List[Dict[str, Any]], budget_level: Any, policy: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], bool]:
    """Filtra candidatos que encajan con el nivel de presupuesto solicitado."""
    rank = budget_rank(budget_level, policy)
    matched = [p for p in candidates if product_budget_rank(p, policy) <= rank]
    return (matched, True) if matched else (candidates, False)


def sort_by_budget_price(candidates: List[Dict[str, Any]], budget_level: Any, policy: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Ordena candidatos priorizando ajuste a presupuesto y menor precio."""
    rank = budget_rank(budget_level, policy)
    return sorted(
        candidates,
        key=lambda p: (
            product_budget_rank(p, policy) > rank,
            float(p.get("price_list") or 0),
            str(p.get("sku")),
        ),
    )


def missing_for_needs(data: Dict[str, Any]) -> List[str]:
    """Devuelve los campos faltantes segun el contrato compartido."""
    return validate_quote_ready_input(data)["missing_required_fields"]


def select_access_point(
    data: Dict[str, Any],
    products: List[Dict[str, Any]],
    rules: Dict[str, Any],
    discarded: List[Dict[str, Any]],
    warnings: List[str],
) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]], List[str]]:
    """Selecciona el modelo de AP que mejor encaja con entorno, marca y presupuesto."""
    td = data.get("technical_design", {})
    quantity = int(td["recommended_access_points"])
    policy = rules["selection_policy"]
    candidates = active_products([p for p in products if p.get("category") == "access_point"], discarded)
    candidates, manufacturer_matched = prefer_manufacturer(candidates, data.get("manufacturer_preference"), warnings, "access_point")
    candidates, environment_matched = filter_environment(candidates, td.get("environment"))
    candidates, budget_matched = filter_budget(candidates, data.get("budget_level"), policy)
    candidates = sort_by_budget_price(candidates, data.get("budget_level"), policy)
    if not candidates:
        return None, [], ["No active access point candidate exists in catalog."]
    chosen = candidates[0]
    reason_parts = [
        f"Uses AP quantity from technical design ({quantity}).",
        f"Selected active {chosen['manufacturer']} {chosen['family']} model.",
    ]
    if manufacturer_matched:
        reason_parts.append("Matches preferred manufacturer.")
    if environment_matched:
        reason_parts.append(f"Fits environment {td.get('environment')}.")
    if budget_matched:
        reason_parts.append(f"Fits budget level {data.get('budget_level', 'medium')}.")
    selected = item_summary(chosen, quantity, " ".join(reason_parts))
    applied = [
        {"id": "QUOTE-001", "effect": "Excluded non-active APs before selection."},
        {"id": "QUOTE-002", "effect": "Applied manufacturer preference as soft criterion."},
        {"id": "QUOTE-003", "effect": "Selected AP model from catalog using environment and budget fit."},
    ]
    return selected, [chosen], applied


def select_switch(
    data: Dict[str, Any],
    products: List[Dict[str, Any]],
    rules: Dict[str, Any],
    discarded: List[Dict[str, Any]],
    warnings: List[str],
) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, str]]]:
    """Selecciona el switch de acceso que cumple puertos, PoE y redundancia."""
    td = data.get("technical_design", {})
    quantity = int(td["recommended_access_switches"])
    required_ports = int(td["required_switch_ports_with_reserve"])
    required_poe = int(td.get("required_poe_ports_with_reserve") or 0)
    ports_per_switch = ceil(required_ports / quantity)
    poe_per_switch = ceil(required_poe / quantity)
    redundancy = norm(td.get("effective_redundancy_level"), "false")
    policy = rules["selection_policy"]

    candidates = active_products([p for p in products if p.get("category") == "switch"], discarded)
    candidates, manufacturer_matched = prefer_manufacturer(candidates, data.get("manufacturer_preference"), warnings, "switch")
    capacity = [
        p for p in candidates
        if int(p.get("technical_attributes", {}).get("ports") or 0) >= ports_per_switch
        and int(p.get("technical_attributes", {}).get("poe_ports") or 0) >= poe_per_switch
    ]
    if not capacity:
        capacity = sorted(candidates, key=lambda p: int(p.get("technical_attributes", {}).get("ports") or 0), reverse=True)[:1]
        warnings.append("No switch exactly covers required ports/PoE per switch; selected nearest higher catalog option if available.")

    if redundancy in {"high", "mission_critical"}:
        stackable = [p for p in capacity if bool(p.get("technical_attributes", {}).get("stackable"))]
        if stackable:
            capacity = stackable
        else:
            warnings.append("Redundancy requires stackable switching, but no stackable candidate was available.")

    capacity, environment_matched = filter_environment(capacity, td.get("environment"))
    capacity, budget_matched = filter_budget(capacity, data.get("budget_level"), policy)
    candidates_sorted = sorted(
        capacity,
        key=lambda p: (
            int(p.get("technical_attributes", {}).get("ports") or 999),
            int(p.get("technical_attributes", {}).get("poe_ports") or 999),
            product_budget_rank(p, policy) > budget_rank(data.get("budget_level"), policy),
            float(p.get("price_list") or 0),
            str(p.get("sku")),
        ),
    )
    if not candidates_sorted:
        return None, [], [{"id": "QUOTE-004", "effect": "No switch candidate exists in catalog."}]
    chosen = candidates_sorted[0]
    reason_parts = [
        f"Uses switch quantity from technical design ({quantity}).",
        f"Requires at least {ports_per_switch} ports and {poe_per_switch} PoE ports per switch.",
        f"Selected {chosen['sku']} with {chosen['technical_attributes'].get('ports')} ports.",
    ]
    if manufacturer_matched:
        reason_parts.append("Matches preferred manufacturer.")
    if environment_matched:
        reason_parts.append(f"Fits environment {td.get('environment')}.")
    if budget_matched:
        reason_parts.append(f"Fits budget level {data.get('budget_level', 'medium')}.")
    if redundancy in {"high", "mission_critical"} and chosen["technical_attributes"].get("stackable"):
        reason_parts.append("Supports stacking for redundant access design.")
    selected = item_summary(chosen, quantity, " ".join(reason_parts))
    applied = [
        {"id": "QUOTE-001", "effect": "Excluded non-active switches before selection."},
        {"id": "QUOTE-002", "effect": "Applied manufacturer preference as soft criterion."},
        {"id": "QUOTE-004", "effect": "Selected switch by required ports and PoE per switch."},
    ]
    return selected, [chosen], applied


def select_firewall(
    data: Dict[str, Any],
    products: List[Dict[str, Any]],
    rules: Dict[str, Any],
    discarded: List[Dict[str, Any]],
    warnings: List[str],
) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, str]]]:
    """Selecciona el equipo edge segun throughput, categoria y requerimientos HA."""
    td = data.get("technical_design", {})
    required_throughput = float(td["estimated_required_throughput_mbps"])
    edge_category = norm(td.get("edge_category"))
    redundancy = norm(td.get("effective_redundancy_level"), "false")
    quantity = int(td.get("edge_router_firewall_count") or (2 if redundancy in {"high", "mission_critical"} else 1))
    policy = rules["selection_policy"]

    candidates = active_products([p for p in products if p.get("category") == "firewall"], discarded)
    candidates, manufacturer_matched = prefer_manufacturer(candidates, data.get("manufacturer_preference"), warnings, "firewall")
    throughput = [p for p in candidates if float(p.get("technical_attributes", {}).get("throughput_mbps") or 0) >= required_throughput]
    if not throughput:
        throughput = sorted(candidates, key=lambda p: float(p.get("technical_attributes", {}).get("throughput_mbps") or 0), reverse=True)[:1]
        warnings.append("No firewall meets required throughput; selected highest catalog throughput as constrained alternative.")
    category_match = [
        p for p in throughput
        if norm(p.get("technical_attributes", {}).get("edge_category")) == edge_category
    ]
    if category_match:
        throughput = category_match
    else:
        warnings.append(f"No exact firewall edge_category match for {td.get('edge_category')}; selected nearest valid throughput option.")
    if redundancy in {"high", "mission_critical"}:
        ha = [p for p in throughput if bool(p.get("technical_attributes", {}).get("ha_capable"))]
        if ha:
            throughput = ha
        else:
            warnings.append("Redundancy requires HA-capable firewall, but no HA-capable candidate was available.")
    throughput, environment_matched = filter_environment(throughput, td.get("environment"))
    throughput, budget_matched = filter_budget(throughput, data.get("budget_level"), policy)
    candidates_sorted = sorted(
        throughput,
        key=lambda p: (
            float(p.get("technical_attributes", {}).get("throughput_mbps") or 0),
            product_budget_rank(p, policy) > budget_rank(data.get("budget_level"), policy),
            float(p.get("price_list") or 0),
            str(p.get("sku")),
        ),
    )
    if not candidates_sorted:
        return None, [], [{"id": "QUOTE-005", "effect": "No firewall candidate exists in catalog."}]
    chosen = candidates_sorted[0]
    reason_parts = [
        f"Requires throughput >= {required_throughput:.0f} Mbps.",
        f"Selected {chosen['sku']} with {chosen['technical_attributes'].get('throughput_mbps')} Mbps catalog throughput.",
    ]
    if quantity > 1:
        reason_parts.append(f"Quantity {quantity} follows redundancy level {td.get('effective_redundancy_level')}.")
    if manufacturer_matched:
        reason_parts.append("Matches preferred manufacturer.")
    if environment_matched:
        reason_parts.append(f"Fits environment {td.get('environment')}.")
    if budget_matched:
        reason_parts.append(f"Fits budget level {data.get('budget_level', 'medium')}.")
    selected = item_summary(chosen, quantity, " ".join(reason_parts))
    applied = [
        {"id": "QUOTE-001", "effect": "Excluded non-active firewalls before selection."},
        {"id": "QUOTE-002", "effect": "Applied manufacturer preference as soft criterion."},
        {"id": "QUOTE-005", "effect": "Selected firewall by edge category and throughput."},
    ]
    if redundancy in {"high", "mission_critical"}:
        applied.append({"id": "QUOTE-010", "effect": "Set edge quantity minimum to 2 and required HA-capable product."})
    return selected, [chosen], applied


def related_quantity(rule: str, parent_quantity: int) -> int:
    """Convierte reglas de cantidad del catalogo en unidades concretas."""
    if rule == "per_device":
        return parent_quantity
    if rule in {"two_per_device", "two_per_switch"}:
        return parent_quantity * 2
    if rule == "per_stack_pair":
        return max(parent_quantity - 1, 0)
    if rule == "fixed_1":
        return 1
    return parent_quantity


def accessory_condition_applies(required_when: Optional[str], parent: Dict[str, Any], parent_quantity: int, data: Dict[str, Any]) -> bool:
    """Evalua si un accesorio condicional debe incluirse para el item padre."""
    if not required_when:
        return True
    td = data.get("technical_design", {})
    redundancy = norm(td.get("effective_redundancy_level"), "false")
    if required_when == "stacking":
        return parent.get("category") == "switch" and parent_quantity > 1 and bool(parent.get("technical_attributes", {}).get("stackable"))
    if required_when == "uplink":
        return parent.get("category") == "switch"
    if required_when == "ha_or_dual_wan":
        return parent.get("category") == "firewall" and (parent_quantity > 1 or redundancy in {"basic", "high", "mission_critical"})
    return False


def add_related_item(
    accumulator: Dict[str, Dict[str, Any]],
    item: Dict[str, Any],
    quantity: int,
    reason: str,
) -> None:
    """Agrega o acumula un item relacionado dentro de la cotizacion."""
    if quantity <= 0:
        return
    sku = item["sku"]
    if sku not in accumulator:
        accumulator[sku] = item_summary(item, quantity, reason)
        accumulator[sku]["selection_reasons"] = [reason]
    else:
        accumulator[sku]["quantity"] += quantity
        accumulator[sku]["total_price"] = money(accumulator[sku]["unit_price"] * accumulator[sku]["quantity"])
        accumulator[sku]["selection_reasons"].append(reason)
        accumulator[sku]["selection_reason"] = " ".join(accumulator[sku]["selection_reasons"])


def include_related_items(
    selected_parent_records: List[Tuple[Dict[str, Any], int]],
    catalog: Dict[str, List[Dict[str, Any]]],
    data: Dict[str, Any],
    warnings: List[str],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
    """Adjunta licencias, soporte y accesorios a los productos base seleccionados."""
    indexes = {
        "licenses": index_by_sku(catalog["licenses"]),
        "support": index_by_sku(catalog["support"]),
        "accessories": index_by_sku(catalog["accessories"]),
    }
    related_items: Dict[str, Dict[str, Any]] = {}
    applied: List[Dict[str, str]] = []
    needs_support = bool((data.get("needs") or {}).get("support"))

    for parent, parent_quantity in selected_parent_records:
        related = parent.get("related", {})
        if parent.get("requires_license"):
            for rel in related.get("licenses", []):
                item = indexes["licenses"].get(rel["sku"])
                if not item:
                    warnings.append(f"Required license {rel['sku']} for {parent['sku']} is not present in catalog.")
                    continue
                if parent["sku"] not in item.get("compatible_with", []):
                    warnings.append(f"License {item['sku']} is not declared compatible with {parent['sku']}.")
                    continue
                qty = related_quantity(rel.get("quantity_rule", "per_device"), parent_quantity)
                add_related_item(related_items, item, qty, f"License required by {parent['sku']}.")
            applied.append({"id": "QUOTE-007", "effect": f"Included license dependencies for {parent['sku']}."})

        if parent.get("requires_support") or needs_support:
            for rel in related.get("support", []):
                item = indexes["support"].get(rel["sku"])
                if not item:
                    warnings.append(f"Support SKU {rel['sku']} for {parent['sku']} is not present in catalog.")
                    continue
                if parent["sku"] not in item.get("compatible_with", []):
                    warnings.append(f"Support {item['sku']} is not declared compatible with {parent['sku']}.")
                    continue
                qty = related_quantity(rel.get("quantity_rule", "per_device"), parent_quantity)
                add_related_item(related_items, item, qty, f"Support added for {parent['sku']}.")
            applied.append({"id": "QUOTE-008", "effect": f"Included support dependencies for {parent['sku']}."})

        for rel in related.get("accessories", []):
            if not rel.get("required") and not accessory_condition_applies(rel.get("required_when"), parent, parent_quantity, data):
                continue
            item = indexes["accessories"].get(rel["sku"])
            if not item:
                warnings.append(f"Accessory SKU {rel['sku']} for {parent['sku']} is not present in catalog.")
                continue
            if parent["sku"] not in item.get("compatible_with", []):
                warnings.append(f"Accessory {item['sku']} is not declared compatible with {parent['sku']}.")
                continue
            qty = related_quantity(rel.get("quantity_rule", "per_device"), parent_quantity)
            add_related_item(related_items, item, qty, f"Accessory required for {parent['sku']}.")
        if related.get("accessories"):
            applied.append({"id": "QUOTE-009", "effect": f"Evaluated required accessories for {parent['sku']}."})

    return list(related_items.values()), applied


def suggest_bundles(
    selected_products: List[Dict[str, Any]],
    related_items: List[Dict[str, Any]],
    bundles: List[Dict[str, Any]],
    environment: Optional[str],
    subtotal_before_discount: float,
) -> Tuple[List[Dict[str, Any]], float, List[Dict[str, str]]]:
    """Sugiere bundles comerciales y calcula descuentos cuando correspondan."""
    selected_categories = {item.get("category") for item in selected_products + related_items}
    env = norm(environment)
    suggestions: List[Dict[str, Any]] = []
    total_discount = 0.0
    applied: List[Dict[str, str]] = []
    for bundle in bundles:
        required = set(bundle.get("requires_categories", []))
        recommended_for = {norm(v) for v in bundle.get("recommended_for", [])}
        if not required.issubset(selected_categories):
            continue
        if env and recommended_for and env not in recommended_for:
            continue
        discount = 0.0
        if bundle.get("pricing_behavior") == "discount":
            discount = subtotal_before_discount * float(bundle.get("discount_percent") or 0) / 100
            total_discount += discount
        suggestions.append({
            "bundle_id": bundle["bundle_id"],
            "manufacturer": bundle.get("manufacturer"),
            "name": bundle.get("name"),
            "pricing_behavior": bundle.get("pricing_behavior"),
            "discount_percent": bundle.get("discount_percent", 0),
            "estimated_discount": money(discount),
            "reason": "Selected categories satisfy bundle requirements.",
        })
    if suggestions:
        applied.append({"id": "QUOTE-014", "effect": "Suggested bundles whose required categories are present."})
    return suggestions, total_discount, applied


def subtotal(items: Iterable[Dict[str, Any]]) -> float:
    """Suma el total_price de una lista de lineas de cotizacion."""
    return sum(float(item.get("total_price") or 0) for item in items)


def knowledge_suggestions(applied_categories: Iterable[str], warnings: List[str], rules: Dict[str, Any]) -> List[str]:
    """Mapea categorias y advertencias a documentos de conocimiento relevantes."""
    mapping = rules.get("knowledge_map", {})
    suggestions: List[str] = []
    for category in applied_categories:
        for path in mapping.get(category, []):
            if path not in suggestions:
                suggestions.append(path)
    if any("budget" in warning.lower() for warning in warnings):
        for path in mapping.get("budget_conflict", []):
            if path not in suggestions:
                suggestions.append(path)
    if any("compatible" in warning.lower() for warning in warnings):
        for path in mapping.get("compatibility", []):
            if path not in suggestions:
                suggestions.append(path)
    return suggestions


def evaluate(data: Dict[str, Any], catalog: Dict[str, List[Dict[str, Any]]], rules: Dict[str, Any]) -> Dict[str, Any]:
    """Ejecuta el flujo completo de cotizacion y devuelve una salida estructurada."""
    data = normalize_quote_input(data)
    contract_validation = validate_quote_ready_input(data)
    missing = contract_validation["missing_required_fields"]
    if missing:
        return {
            "status": "needs_input",
            "site_name": data.get("site_name"),
            "missing_information": missing,
            "message": "Cannot produce deterministic quote without required technical design fields.",
            "contract_validation": contract_validation,
            "knowledge_suggestions": ["knowledge/vendor-guidance.md"],
        }

    needs = data.get("needs") or {}
    td = data.get("technical_design", {})
    selected_products: List[Dict[str, Any]] = []
    selected_parent_records: List[Tuple[Dict[str, Any], int]] = []
    discarded: List[Dict[str, Any]] = []
    warnings: List[str] = []
    constraints: List[Dict[str, str]] = []
    applied_rules: List[Dict[str, str]] = []
    technical_reasons: List[str] = []

    if needs.get("wireless") or (not needs and td.get("recommended_access_points") is not None):
        selected, records, applied = select_access_point(data, catalog["products"], rules, discarded, warnings)
        applied_rules.extend(applied)
        if selected and records:
            selected_products.append(selected)
            selected_parent_records.append((records[0], selected["quantity"]))
            technical_reasons.append(selected["selection_reason"])

    if needs.get("switching") or (not needs and td.get("recommended_access_switches") is not None):
        selected, records, applied = select_switch(data, catalog["products"], rules, discarded, warnings)
        applied_rules.extend(applied)
        if selected and records:
            selected_products.append(selected)
            selected_parent_records.append((records[0], selected["quantity"]))
            technical_reasons.append(selected["selection_reason"])

    if needs.get("edge") or (not needs and td.get("edge_category") is not None):
        selected, records, applied = select_firewall(data, catalog["products"], rules, discarded, warnings)
        applied_rules.extend(applied)
        if selected and records:
            selected_products.append(selected)
            selected_parent_records.append((records[0], selected["quantity"]))
            technical_reasons.append(selected["selection_reason"])

    related_items, related_rules = include_related_items(selected_parent_records, catalog, data, warnings)
    applied_rules.extend(related_rules)

    hardware_subtotal = subtotal(selected_products)
    related_subtotal = subtotal(related_items)
    before_discount = hardware_subtotal + related_subtotal
    bundles, discount, bundle_rules = suggest_bundles(
        selected_products,
        related_items,
        catalog["bundles"],
        td.get("environment"),
        before_discount,
    )
    applied_rules.extend(bundle_rules)
    estimated_subtotal = before_discount - discount

    budget = data.get("budget_usd")
    if budget is not None:
        try:
            numeric_budget = float(budget)
        except (TypeError, ValueError):
            numeric_budget = None
        if numeric_budget is None:
            warnings.append("budget_usd is present but is not numeric.")
        elif numeric_budget < estimated_subtotal:
            constraints.append({
                "id": "BUDGET-001",
                "severity": "high",
                "message": f"Budget {numeric_budget:.0f} USD is below estimated subtotal {estimated_subtotal:.0f} USD.",
            })
            applied_rules.append({"id": "QUOTE-011", "effect": "Detected numeric budget conflict."})

    categories = [item["category"] for item in selected_products]
    return {
        "status": "ok" if selected_products else "no_match",
        "site_name": data.get("site_name"),
        "contract_validation": contract_validation,
        "recommendation": {
            "selected_products": selected_products,
            "related_items": related_items,
            "suggested_bundles": bundles,
        },
        "discarded_products": discarded,
        "applied_rules": applied_rules,
        "technical_reasons": technical_reasons,
        "constraints": constraints,
        "warnings": warnings,
        "missing_information": [],
        "estimated_total": {
            "currency": "USD",
            "hardware_subtotal": money(hardware_subtotal),
            "related_items_subtotal": money(related_subtotal),
            "bundle_discount": money(discount),
            "subtotal": money(estimated_subtotal),
        },
        "knowledge_suggestions": knowledge_suggestions(categories, warnings, rules),
    }


def build_quote_output_payload(source_input: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    """Build the canonical JSON output persisted by the quoting skill."""
    normalized_input = normalize_quote_input(source_input)
    return {
        "output_contract_version": "1.0",
        "source_input_type": (
            "handoff"
            if isinstance(source_input.get("handoff"), dict)
            else "quote_ready_input"
            if isinstance(source_input.get("quote_ready_input"), dict)
            else "direct"
        ),
        "input_contract_validation": validate_quote_ready_input(normalized_input),
        **result,
    }


def build_quote_explanation(source_input: Dict[str, Any], result: Dict[str, Any]) -> str:
    """Render a deterministic natural-language explanation for export."""
    normalized_input = normalize_quote_input(source_input)
    if result.get("status") == "needs_input":
        missing = ", ".join(result.get("missing_information", []))
        return (
            "No fue posible producir una cotización determinística.\n\n"
            f"Campos faltantes: {missing or 'sin detalle'}.\n"
            f"Mensaje: {result.get('message', 'No additional context available.')}"
        )

    recommendation = result.get("recommendation", {})
    selected_products = recommendation.get("selected_products", [])
    related_items = recommendation.get("related_items", [])
    bundles = recommendation.get("suggested_bundles", [])

    lines = [
        f"Sitio: {result.get('site_name') or normalized_input.get('site_name') or 'Sin nombre'}",
        "",
        "Resultado",
        (
            f"Estado: {result.get('status')}. "
            f"Subtotal preliminar: {result.get('estimated_total', {}).get('subtotal')} "
            f"{result.get('estimated_total', {}).get('currency', 'USD')}."
        ),
        "",
        "Productos seleccionados",
    ]
    if selected_products:
        for item in selected_products:
            lines.append(
                f"- {item.get('sku')}: {item.get('quantity')} x {item.get('name')} "
                f"({item.get('category')}) por {item.get('total_price')} {item.get('currency')}. "
                f"Razón: {item.get('selection_reason')}"
            )
    else:
        lines.append("- No hubo productos seleccionados.")

    lines.extend(["", "Licencias, soporte y accesorios"])
    if related_items:
        for item in related_items:
            lines.append(
                f"- {item.get('sku')}: {item.get('quantity')} unidad(es), total {item.get('total_price')} "
                f"{item.get('currency')}. Razón: {item.get('selection_reason')}"
            )
    else:
        lines.append("- No se agregaron dependencias relacionadas.")

    lines.extend(["", "Bundles y reglas"])
    if bundles:
        for bundle in bundles:
            lines.append(
                f"- {bundle.get('bundle_id')}: {bundle.get('name')} "
                f"(descuento estimado {bundle.get('estimated_discount')})."
            )
    else:
        lines.append("- Sin bundles sugeridos.")
    for rule in result.get("applied_rules", []):
        lines.append(f"- {rule.get('id')}: {rule.get('effect')}")

    lines.extend(["", "Advertencias y restricciones"])
    if result.get("warnings"):
        for warning in result["warnings"]:
            lines.append(f"- Advertencia: {warning}")
    if result.get("constraints"):
        for constraint in result["constraints"]:
            lines.append(f"- {constraint.get('id')}: {constraint.get('message')}")
    if not result.get("warnings") and not result.get("constraints"):
        lines.append("- Sin advertencias ni restricciones críticas.")

    return "\n".join(lines)


def main() -> None:
    """Expone una CLI simple para ejecutar el motor desde terminal."""
    parser = argparse.ArgumentParser(description="Select network catalog SKUs from technical design output.")
    parser.add_argument("--input", required=True, help="Path to structured quote input JSON.")
    parser.add_argument("--catalog-dir", default=str(DEFAULT_CATALOG), help="Directory containing catalog JSON files.")
    parser.add_argument("--rules", default=str(DEFAULT_RULES), help="Path to quote_rules.json.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args()

    result = evaluate(
        load_json(Path(args.input)),
        load_catalog(Path(args.catalog_dir)),
        load_json(Path(args.rules)),
    )
    print(json.dumps(result, indent=2 if args.pretty else None, ensure_ascii=False))


if __name__ == "__main__":
    main()
