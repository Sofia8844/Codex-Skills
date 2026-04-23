#!/usr/bin/env python3
"""Integra salidas de diseno/cotizacion para poblar una propuesta comercial.

Este helper no recalcula diseno ni cotizacion. Solo transforma contratos JSON
ya emitidos por otros skills a:

- un contexto consolidado para la propuesta
- un spec JSON parcial listo para alimentar `build_presentation.py`
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple
import xml.etree.ElementTree as ET


SKILL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[4]

if str(SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT))

import build_presentation as builder


DEFAULT_TEMPLATE = SKILL_ROOT / "assets" / "plantillas" / "Industrias Ariova.pptx"
DEFAULT_OUTPUT_DIR = SKILL_ROOT / "output"
DEFAULT_CONTEXT_NAME = "proposal_network_context.json"
DEFAULT_SPEC_NAME = "proposal_network_spec.json"

SLIDES_TO_PREPARE = (1, 3, 4, 5, 7, 12)


def load_json(path: Path) -> Dict[str, Any]:
    """Carga un JSON con UTF-8."""
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    """Escribe un JSON legible."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def norm_text(value: Any) -> str:
    """Normaliza texto simple para comparaciones suaves."""
    return "" if value is None else str(value).strip().lower()


def slugify(value: str | None, default: str = "propuesta-red") -> str:
    """Convierte un nombre libre a slug sencillo para archivos."""
    text = norm_text(value)
    if not text:
        return default
    chars = [char if char.isalnum() else "-" for char in text]
    slug = "".join(chars).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or default


def get_path(data: Dict[str, Any], path: str, default: Any = None) -> Any:
    """Lee una ruta anidada con notacion de puntos."""
    current: Any = data
    for key in path.split("."):
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def money_usd(value: float | int | None) -> str:
    """Formatea montos USD para narrativa comercial."""
    if value is None:
        return "{{monto_pendiente}}"
    return f"USD {float(value):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def detect_design_handoff(payload: Dict[str, Any]) -> bool:
    """Detecta el contrato JSON de handoff emitido por el skill de diseno."""
    return isinstance(get_path(payload, "handoff.quote_ready_input"), dict)


def detect_quote_output(payload: Dict[str, Any]) -> bool:
    """Detecta la salida JSON formal del skill de cotizacion."""
    return (
        isinstance(payload.get("recommendation"), dict)
        and isinstance(payload.get("estimated_total"), dict)
    ) or "output_contract_version" in payload


def extract_design_handoff(payload: Dict[str, Any] | None) -> Dict[str, Any]:
    """Normaliza el contrato de diseno al objeto `quote_ready_input`."""
    if not payload:
        return {}
    if detect_design_handoff(payload):
        return get_path(payload, "handoff.quote_ready_input", {}) or {}
    if isinstance(payload.get("quote_ready_input"), dict):
        return payload["quote_ready_input"]
    return payload if isinstance(payload.get("technical_design"), dict) else {}


def extract_quote_output(payload: Dict[str, Any] | None) -> Dict[str, Any]:
    """Normaliza la salida de cotizacion al payload principal del skill."""
    if not payload:
        return {}
    if detect_quote_output(payload):
        return payload
    if isinstance(payload.get("quote_output"), dict):
        return payload["quote_output"]
    return {}


def infer_input_files(input_files: Iterable[Path]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Autodetecta handoff de diseno y salida de cotizacion desde una lista de archivos."""
    design_handoff: Dict[str, Any] = {}
    quote_output: Dict[str, Any] = {}
    for path in input_files:
        payload = load_json(path)
        if not design_handoff and detect_design_handoff(payload):
            design_handoff = payload
        elif not quote_output and detect_quote_output(payload):
            quote_output = payload
    return design_handoff, quote_output


def choose_value(*values: Any, default: Any = None) -> Any:
    """Devuelve el primer valor no vacio."""
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return default


def split_related_items(items: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Agrupa items relacionados por categoria comercial."""
    grouped = {"license": [], "support": [], "accessory": [], "other": []}
    for item in items:
        category = norm_text(item.get("category"))
        if category in grouped:
            grouped[category].append(item)
        else:
            grouped["other"].append(item)
    return grouped


def sum_prices(items: Iterable[Dict[str, Any]]) -> float:
    """Suma total_price de una coleccion de items."""
    total = 0.0
    for item in items:
        try:
            total += float(item.get("total_price") or 0)
        except (TypeError, ValueError):
            continue
    return round(total, 2)


def translate_environment(value: Any) -> str:
    """Convierte etiquetas tecnicas de entorno a redaccion comercial breve."""
    labels = {
        "corporate": "corporativo",
        "enterprise": "empresarial",
        "office": "oficina",
        "industrial": "industrial",
        "retail": "retail",
        "education": "educativo",
        "healthcare": "salud",
    }
    normalized = norm_text(value)
    return labels.get(normalized, str(value).strip() if str(value).strip() else "{{entorno}}")


def translate_redundancy(value: Any) -> str:
    """Convierte niveles de redundancia a texto natural en espanol."""
    labels = {
        "high": "alta",
        "medium": "media",
        "low": "basica",
        "basic": "basica",
        "none": "sin redundancia dedicada",
    }
    normalized = norm_text(value)
    return labels.get(normalized, str(value).strip() if str(value).strip() else "{{redundancia}}")


def infer_primary_manufacturer(
    selected_products: List[Dict[str, Any]],
    related_items: List[Dict[str, Any]],
) -> str | None:
    """Infiera el fabricante predominante cuando el handoff no lo informe."""
    counts: Dict[str, int] = {}
    for item in selected_products + related_items:
        manufacturer = str(item.get("manufacturer") or "").strip()
        if not manufacturer:
            continue
        key = manufacturer.casefold()
        counts[key] = counts.get(key, 0) + int(item.get("quantity") or 1)
    if not counts:
        return None
    winner = max(counts.items(), key=lambda pair: pair[1])[0]
    for item in selected_products + related_items:
        manufacturer = str(item.get("manufacturer") or "").strip()
        if manufacturer.casefold() == winner:
            return manufacturer
    return None


def default_payment_terms(currency: str) -> List[str]:
    """Devuelve bullets pendientes pero presentables cuando no hay forma de pago."""
    reference_currency = currency or "USD"
    return [
        f"Moneda de referencia: {reference_currency}.",
        "Forma de pago pendiente de definicion comercial.",
        "Hitos de facturacion por confirmar con el cliente.",
        "Condiciones finales sujetas a aprobacion de la propuesta.",
    ]


def commercial_condition_bullets(
    quote: Dict[str, Any],
    currency: str,
    manufacturer: str,
) -> List[str]:
    """Resume advertencias y condiciones en bullets comerciales legibles."""
    bullets: List[str] = []
    warnings = [str(item).strip() for item in quote.get("warnings", []) if str(item).strip()]
    manufacturer_missing = [
        item for item in warnings if item.lower().startswith("no manufacturer preference provided")
    ]
    if manufacturer_missing:
        bullets.append(
            f"La seleccion se elaboro sin preferencia de fabricante declarada y se consolido sobre portafolio {manufacturer}."
        )
    for warning in warnings:
        if warning in manufacturer_missing:
            continue
        bullets.append(warning)

    if not quote.get("constraints"):
        bullets.append("Las cantidades y referencias comerciales provienen del diseno tecnico y la cotizacion validados.")
    else:
        for item in quote.get("constraints", []):
            message = str(item.get("message") if isinstance(item, dict) else item).strip()
            if message:
                bullets.append(message)

    estimated_total = quote.get("estimated_total", {}) or {}
    if float(estimated_total.get("bundle_discount") or 0) == 0:
        bullets.append("La estimacion no incorpora descuentos adicionales por bundle.")
    bullets.append(f"Los valores economicos estan expresados en {currency or 'USD'} y quedan sujetos a validacion comercial final.")

    deduped: List[str] = []
    seen = set()
    for bullet in bullets:
        key = norm_text(bullet)
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(bullet)
    return deduped


def ensure_technical_reasons(
    reasons: List[str],
    grouped_related: Dict[str, List[Dict[str, Any]]],
) -> List[str]:
    """Completa la justificacion tecnica con una nota de licencias/soporte cuando falte."""
    cleaned = [str(item).strip() for item in reasons if str(item).strip()]
    if len(cleaned) >= 4:
        return cleaned[:4]

    complements: List[str] = []
    if grouped_related["license"]:
        complements.append("La propuesta incorpora el licenciamiento requerido para operar y administrar la solucion recomendada.")
    if grouped_related["support"]:
        complements.append("La configuracion considera soporte asociado para continuidad operativa de la plataforma.")
    if grouped_related["accessory"] or grouped_related["other"]:
        complements.append("Se incluyen accesorios y complementos necesarios para instalacion y puesta en marcha.")

    for item in complements:
        if len(cleaned) >= 4:
            break
        cleaned.append(item)
    while len(cleaned) < 4:
        cleaned.append("La arquitectura propuesta mantiene coherencia entre capacidad, disponibilidad y operacion de la sede.")
    return cleaned[:4]


def top_texts(values: Iterable[str], limit: int, fallback_prefix: str) -> List[str]:
    """Recorta una lista de textos o agrega placeholders cuando faltan datos."""
    cleaned = [str(value).strip() for value in values if str(value).strip()]
    padded = cleaned[:limit]
    while len(padded) < limit:
        padded.append(f"{{{{{fallback_prefix}_{len(padded) + 1}}}}}")
    return padded


def proposal_context_from_sources(
    design_payload: Dict[str, Any],
    quote_payload: Dict[str, Any],
    user_payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Construye el contexto consolidado para la propuesta a partir de JSON previos."""
    design = extract_design_handoff(design_payload)
    quote = extract_quote_output(quote_payload)

    technical_design = design.get("technical_design", {})
    selected_products = get_path(quote, "recommendation.selected_products", []) or []
    related_items = get_path(quote, "recommendation.related_items", []) or []
    grouped_related = split_related_items(related_items)
    estimated_total = quote.get("estimated_total", {}) or {}
    inferred_manufacturer = infer_primary_manufacturer(selected_products, related_items)
    currency = str(estimated_total.get("currency") or "USD")

    site_name = choose_value(
        user_payload.get("site_name"),
        user_payload.get("client_name"),
        quote.get("site_name"),
        design.get("site_name"),
        default="{{cliente_nombre}}",
    )
    manufacturer = choose_value(
        user_payload.get("manufacturer_preference"),
        design.get("manufacturer_preference"),
        inferred_manufacturer,
        default="seleccionado",
    )
    environment = choose_value(
        translate_environment(technical_design.get("environment")),
        default="{{entorno}}",
    )
    redundancy = choose_value(
        translate_redundancy(technical_design.get("effective_redundancy_level")),
        default="{{redundancia}}",
    )

    ap_count = choose_value(technical_design.get("recommended_access_points"), default="{{aps}}")
    switch_count = choose_value(technical_design.get("recommended_access_switches"), default="{{switches}}")
    edge_count = choose_value(technical_design.get("edge_router_firewall_count"), default="{{edge}}")

    executive_points = [
        choose_value(
            user_payload.get("executive_context"),
            f"{site_name} requiere una propuesta integrada LAN/WLAN/edge para un entorno {environment} con redundancia {redundancy}.",
        ),
        choose_value(
            user_payload.get("executive_solution"),
            f"La solucion propuesta parte de {ap_count} access points, {switch_count} switches de acceso y {edge_count} equipos de borde definidos en el diseno validado.",
        ),
        choose_value(
            user_payload.get("executive_commercial"),
            f"La narrativa comercial prioriza capacidades alineadas al fabricante {manufacturer} y a las restricciones declaradas por la cotizacion.",
        ),
        choose_value(
            user_payload.get("executive_risks"),
            "; ".join([
                str(item.get("message") if isinstance(item, dict) else item).strip()
                for item in quote.get("constraints", [])[:2]
                if str(item.get("message") if isinstance(item, dict) else item).strip()
            ])
            or "No se registran restricciones criticas adicionales en los JSON recibidos.",
        ),
    ]

    context_bullets = top_texts([
        choose_value(
            user_payload.get("client_context_1"),
            f"Proyecto para {site_name} en entorno {environment}.",
        ),
        choose_value(
            user_payload.get("client_context_2"),
            f"Fabricante preferido reportado: {manufacturer}.",
        ),
        choose_value(
            user_payload.get("client_context_3"),
            f"Nivel de redundancia objetivo: {redundancy}.",
        ),
    ], 3, "contexto")

    objective_bullets = top_texts([
        choose_value(
            user_payload.get("objective_1"),
            f"Asegurar una arquitectura con {ap_count} APs y cobertura empresarial consistente.",
        ),
        choose_value(
            user_payload.get("objective_2"),
            f"Proveer switching con {switch_count} equipos y capacidad alineada al diseno aprobado.",
        ),
        choose_value(
            user_payload.get("objective_3"),
            f"Presentar una propuesta comercial soportada por {edge_count} equipos de borde y restricciones explicitas.",
        ),
    ], 3, "objetivo")

    solution_blocks = top_texts([
        choose_value(
            user_payload.get("solution_1"),
            f"Infraestructura WLAN con {ap_count} access points y gestion centralizada segun el diseno tecnico.",
        ),
        choose_value(
            user_payload.get("solution_2"),
            f"Plataforma de switching con {switch_count} switches de acceso y reserva de puertos definida por el skill de cotizacion.",
        ),
        choose_value(
            user_payload.get("solution_3"),
            f"Edge empresarial con {edge_count} equipos y disponibilidad {redundancy} para proteger conectividad y seguridad.",
        ),
        choose_value(
            user_payload.get("solution_4"),
            f"Portafolio comercial basado en productos {manufacturer} o en seleccion vendor-neutral validada por la salida de cotizacion.",
        ),
    ], 4, "solucion")

    architecture_bullets = top_texts([
        choose_value(
            user_payload.get("architecture_1"),
            f"Access points: {ap_count}",
        ),
        choose_value(
            user_payload.get("architecture_2"),
            f"Switches de acceso: {switch_count}",
        ),
        choose_value(
            user_payload.get("architecture_3"),
            f"Equipos de borde: {edge_count}",
        ),
        choose_value(
            user_payload.get("architecture_4"),
            f"Entorno / redundancia: {environment} / {redundancy}",
        ),
    ], 4, "arquitectura")

    hardware_subtotal = float(estimated_total.get("hardware_subtotal") or 0)
    licenses_subtotal = sum_prices(grouped_related["license"])
    support_subtotal = sum_prices(grouped_related["support"])
    accessories_subtotal = sum_prices(grouped_related["accessory"] + grouped_related["other"])
    proposal_economic = [
        choose_value(
            user_payload.get("concept_1"),
            f"Infraestructura principal: {money_usd(hardware_subtotal)}",
        ),
        choose_value(
            user_payload.get("concept_2"),
            f"Licencias y suscripciones: {money_usd(licenses_subtotal)}",
        ),
        choose_value(
            user_payload.get("concept_3"),
            f"Soporte y servicios asociados: {money_usd(support_subtotal)}",
        ),
        choose_value(
            user_payload.get("concept_4"),
            f"Accesorios y complementos: {money_usd(accessories_subtotal)}",
        ),
        choose_value(
            user_payload.get("total_proposal"),
            f"Total estimado: {money_usd(estimated_total.get('subtotal'))}",
        ),
    ]

    payment_terms_input = user_payload.get("payment_terms", [])
    payment_terms = (
        top_texts(payment_terms_input, 4, "forma_pago")
        if payment_terms_input
        else default_payment_terms(currency)
    )

    condition_values = list(user_payload.get("commercial_conditions", [])) or commercial_condition_bullets(
        quote,
        currency,
        manufacturer,
    )
    conditions = top_texts(condition_values, 4, "condicion")

    technical_reasons = ensure_technical_reasons(list(quote.get("technical_reasons", [])), grouped_related)

    product_rows = []
    for item in selected_products + related_items:
        product_rows.append({
            "sku": item.get("sku"),
            "name": item.get("name"),
            "category": item.get("category"),
            "quantity": item.get("quantity"),
            "unit_price": item.get("unit_price"),
            "total_price": item.get("total_price"),
            "selection_reason": item.get("selection_reason"),
        })

    return {
        "sources": {
            "design_handoff_present": bool(design),
            "quote_output_present": bool(quote),
        },
        "resolved": {
            "site_name": site_name,
            "manufacturer_preference": manufacturer,
            "environment": environment,
            "effective_redundancy_level": redundancy,
            "recommended_access_points": ap_count,
            "recommended_access_switches": switch_count,
            "edge_router_firewall_count": edge_count,
        },
        "sections": {
            "executive_summary_blocks": executive_points,
            "context_bullets": context_bullets,
            "objective_bullets": objective_bullets,
            "solution_blocks": solution_blocks,
            "architecture_bullets": architecture_bullets,
            "proposal_economic_lines": proposal_economic,
            "payment_terms": payment_terms,
            "commercial_conditions": conditions,
            "technical_reasons": technical_reasons,
        },
        "quote_tables": {
            "selected_products": selected_products,
            "related_items": related_items,
            "all_rows": product_rows,
        },
        "totals": estimated_total,
        "constraints": quote.get("constraints", []),
        "warnings": quote.get("warnings", []),
    }


def template_slide_defaults(template_path: Path, slide_numbers: Iterable[int]) -> Dict[int, List[List[str]]]:
    """Lee la plantilla actual y devuelve sus textos por shape para slides concretas."""
    defaults: Dict[int, List[List[str]]] = {}
    with zipfile.ZipFile(template_path, "r") as source_zip:
        for slide_number in slide_numbers:
            slide_path = builder.slide_path_for_number(slide_number)
            root = ET.fromstring(source_zip.read(slide_path))
            defaults[slide_number] = [
                builder.shape_paragraph_texts(target.element)
                for target in builder.text_shape_targets_from_slide(root)
            ]
    return defaults


def set_shape(replacements: Dict[int, List[List[str]]], slide: int, shape_index: int, paragraphs: List[str] | str) -> None:
    """Sobrescribe el contenido de un shape especifico respetando la estructura del builder."""
    value = paragraphs if isinstance(paragraphs, list) else [paragraphs]
    replacements[slide][shape_index - 1] = [str(item) for item in value if str(item).strip()] or [""]


def build_builder_spec(
    context: Dict[str, Any],
    output_dir: Path,
    template_path: Path,
) -> Dict[str, Any]:
    """Convierte el contexto integrado en un spec JSON parcial para el builder existente."""
    defaults = template_slide_defaults(template_path, SLIDES_TO_PREPARE)
    replacements = {slide: deepcopy(values) for slide, values in defaults.items()}
    sections = context["sections"]
    resolved = context["resolved"]
    output_name = f"propuesta-economica-{slugify(str(resolved['site_name']), 'propuesta-red')}.pptx"

    set_shape(replacements, 1, 1, f"PROYECTO {str(resolved['site_name']).upper()}")

    set_shape(replacements, 3, 1, "Resumen Ejecutivo")
    set_shape(replacements, 3, 2, sections["executive_summary_blocks"][0])
    set_shape(replacements, 3, 5, sections["executive_summary_blocks"][1])
    set_shape(replacements, 3, 8, sections["executive_summary_blocks"][2])
    set_shape(replacements, 3, 9, sections["executive_summary_blocks"][3])

    set_shape(replacements, 4, 1, "Contexto y objetivos del proyecto")
    set_shape(replacements, 4, 3, sections["context_bullets"][:3])
    set_shape(replacements, 4, 4, sections["objective_bullets"][:3])

    set_shape(replacements, 5, 1, "Propuesta de Solucion")
    set_shape(replacements, 5, 2, sections["solution_blocks"][0])
    set_shape(replacements, 5, 5, sections["solution_blocks"][1])
    set_shape(replacements, 5, 8, sections["solution_blocks"][2])
    set_shape(replacements, 5, 9, sections["solution_blocks"][3])

    set_shape(replacements, 7, 1, "Arquitectura tecnologica")
    set_shape(replacements, 7, 2, "Componentes principales")
    set_shape(replacements, 7, 3, sections["architecture_bullets"][:4])

    set_shape(replacements, 12, 1, "PROPUESTA ECONOMICA Y CONDICIONES")
    set_shape(replacements, 12, 6, sections["proposal_economic_lines"][:5])
    set_shape(replacements, 12, 7, sections["payment_terms"][:4])
    set_shape(replacements, 12, 8, sections["commercial_conditions"][:4])

    notes_lines = [
        f"# Propuesta integrada para {resolved['site_name']}",
        "",
        "## Justificacion tecnica",
        *[f"- {item}" for item in sections["technical_reasons"]],
        "",
        "## Productos seleccionados",
    ]
    for item in context["quote_tables"]["all_rows"]:
        notes_lines.append(
            f"- {item.get('sku')}: {item.get('quantity')} x {item.get('name')} "
            f"({item.get('category')}) - {money_usd(item.get('total_price'))}"
        )

    return {
        "template_path": str(template_path),
        "output_pptx": str((builder.OUTPUT_ROOT / output_name).resolve()),
        "slide_replacements": {str(slide): value for slide, value in replacements.items()},
        "notes_markdown": "\n".join(notes_lines),
    }


def build_argument_parser() -> argparse.ArgumentParser:
    """Construye la CLI del integrador."""
    parser = argparse.ArgumentParser(description="Integrate design/quote JSON into a proposal-ready context and builder spec.")
    parser.add_argument("--design-handoff", help="Path to network design handoff JSON.")
    parser.add_argument("--quote-output", help="Path to network quote output JSON.")
    parser.add_argument("--user-input", help="Optional JSON with explicit user overrides for proposal fields.")
    parser.add_argument("--input-files", nargs="*", default=[], help="Optional list of JSON files. The script auto-detects design_handoff and quote_output if explicit paths are not provided.")
    parser.add_argument("--template", default=str(DEFAULT_TEMPLATE), help="Template PPTX used to infer default slide content.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory where context/spec files will be written.")
    parser.add_argument("--context-name", default=DEFAULT_CONTEXT_NAME, help="Filename for the consolidated proposal context JSON.")
    parser.add_argument("--spec-name", default=DEFAULT_SPEC_NAME, help="Filename for the builder-ready spec JSON.")
    parser.add_argument("--build", action="store_true", help="Build the PPTX immediately using the generated spec and the existing builder.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print the resulting payload to stdout.")
    return parser


def main() -> None:
    """Resuelve entradas de otros skills y genera contexto/spec para propuesta."""
    parser = build_argument_parser()
    args = parser.parse_args()

    explicit_design = load_json(Path(args.design_handoff)) if args.design_handoff else {}
    explicit_quote = load_json(Path(args.quote_output)) if args.quote_output else {}
    inferred_design, inferred_quote = infer_input_files([Path(path) for path in args.input_files])
    user_input = load_json(Path(args.user_input)) if args.user_input else {}

    design_payload = explicit_design or inferred_design
    quote_payload = explicit_quote or inferred_quote
    context = proposal_context_from_sources(design_payload, quote_payload, user_input)

    output_dir = Path(args.output_dir)
    context_path = output_dir / args.context_name
    spec_path = output_dir / args.spec_name
    spec_payload = build_builder_spec(context, output_dir, Path(args.template))

    write_json(context_path, context)
    write_json(spec_path, spec_payload)

    result: Dict[str, Any] = {
        "context_path": str(context_path),
        "spec_path": str(spec_path),
        "sources": context["sources"],
    }

    if args.build:
        build_result = builder.build_from_spec_data(spec_payload, REPO_ROOT)
        result["build"] = {
            "output_pptx": str(build_result["output_pptx"]),
            "warnings": build_result["warnings"],
        }

    print(json.dumps(result, indent=2 if args.pretty else None, ensure_ascii=False))


if __name__ == "__main__":
    main()
