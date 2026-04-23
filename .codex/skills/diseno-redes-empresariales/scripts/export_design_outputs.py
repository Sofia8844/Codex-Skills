#!/usr/bin/env python3
"""Exporta los artefactos finales del skill de diseno de red.

Este script transforma el resultado ya calculado en artefactos de integracion:

- un JSON de handoff para el siguiente skill
- un Markdown con la explicacion visible
- un PDF generado desde esa misma explicacion
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict


SKILL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[4]
SHARED_NETWORK_DIR = REPO_ROOT / ".codex" / "shared" / "network"

# Agrega la carpeta compartida al path para reutilizar helpers neutrales.
if str(SHARED_NETWORK_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_NETWORK_DIR))

from json_io import ensure_case_output_dir, load_json, write_json
from pdf_export import write_pdf

import evaluate_network_design as evaluator


HANDOFF_FILENAME = "network_design_handoff.json"
MARKDOWN_FILENAME = "network_design_explanation.md"
PDF_FILENAME = "network_design_explanation.pdf"


def resolve_explanation_text(
    source_input: Dict[str, Any],
    result: Dict[str, Any],
    output_path: Path,
    explanation_file: str | None = None,
) -> tuple[str, Path, str]:
    """Resuelve la explicacion visible que debe reutilizarse para Markdown y PDF.

    Prioridad:
    1. Un archivo explicito recibido por argumento.
    2. `network_design_explanation.md` existente en la carpeta del caso.
    3. Fallback al texto base generado por el motor deterministico.
    """
    artifact_markdown_path = output_path / MARKDOWN_FILENAME
    candidate_path = Path(explanation_file) if explanation_file else artifact_markdown_path

    explanation_source = "deterministic_fallback"
    explanation_text = ""
    if candidate_path.exists():
        explanation_text = candidate_path.read_text(encoding="utf-8-sig").strip()
        explanation_source = "external_markdown" if explanation_file else "case_markdown"

    if not explanation_text:
        explanation_text = evaluator.build_design_explanation(source_input, result)

    # Siempre persiste la fuente visible usada para el PDF en la ruta estable del caso.
    artifact_markdown_path.write_text(f"{explanation_text.rstrip()}\n", encoding="utf-8")
    return explanation_text, artifact_markdown_path, explanation_source


def export_outputs(
    source_input: Dict[str, Any],
    result: Dict[str, Any],
    output_dir: str | None = None,
    explanation_file: str | None = None,
) -> Dict[str, Any]:
    """Genera el JSON de handoff, el Markdown y el PDF del skill de diseno.

    `source_input` es la entrada original del usuario ya estructurada.
    `result` es la salida del motor `evaluate_network_design.py`.

    Si el resultado no esta en estado `ok`, no se escribe el handoff porque
    el contrato solo debe emitirse cuando el diseno es valido y completo.
    """
    case_name = source_input.get("site_name")
    output_path = ensure_case_output_dir(REPO_ROOT, case_name, output_dir)

    # La explicacion visible puede venir de un Markdown previo escrito por Codex
    # o, si aun no existe, desde el fallback deterministico del motor.
    explanation, explanation_md_path, explanation_source = resolve_explanation_text(
        source_input,
        result,
        output_path,
        explanation_file,
    )

    if result.get("status") != "ok":
        return {
            "status": "needs_input",
            "message": result.get("message"),
            "missing_fields": result.get("missing_fields", []),
            "explanation": explanation,
            "explanation_md_path": str(explanation_md_path),
            "explanation_source": explanation_source,
        }

    # Convierte el resultado tecnico al contrato desacoplado que consumira
    # el skill de cotizacion.
    handoff_payload = evaluator.build_design_handoff_payload(source_input, result)
    handoff_path = output_path / HANDOFF_FILENAME
    pdf_path = output_path / PDF_FILENAME

    # Escribe todos los artefactos con nombres estables para integracion futura.
    write_json(handoff_path, handoff_payload)
    write_pdf(pdf_path, "Network Design Explanation", explanation)

    return {
        "status": "ok",
        "handoff_path": str(handoff_path),
        "explanation_md_path": str(explanation_md_path),
        "pdf_path": str(pdf_path),
        "explanation_source": explanation_source,
        "handoff": handoff_payload,
        "explanation": explanation,
    }


def main() -> None:
    """CLI simple para exportar los artefactos del skill de diseno."""
    parser = argparse.ArgumentParser(description="Export handoff JSON and PDF for a network design.")
    parser.add_argument("--input", required=True, help="Path to structured network design input JSON.")
    parser.add_argument("--rules", default=str(evaluator.DEFAULT_RULES), help="Path to technical_rules.json.")
    parser.add_argument("--output-dir", default=None, help="Optional output directory. Defaults to analysis_output/<site_name>/.")
    parser.add_argument(
        "--explanation-file",
        default=None,
        help="Optional Markdown file with the final visible explanation. If omitted, the exporter auto-detects network_design_explanation.md in the case folder or falls back to the deterministic explanation.",
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print the JSON summary to stdout.")
    args = parser.parse_args()

    # Primero evalua el diseno y despues exporta los artefactos derivados.
    source_input = load_json(Path(args.input))
    result = evaluator.evaluate(source_input, load_json(Path(args.rules)))
    exported = export_outputs(source_input, result, args.output_dir, args.explanation_file)
    print(json.dumps(exported, indent=2 if args.pretty else None, ensure_ascii=False))


if __name__ == "__main__":
    main()
