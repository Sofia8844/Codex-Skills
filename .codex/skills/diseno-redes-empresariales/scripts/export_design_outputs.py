#!/usr/bin/env python3
"""Exporta los artefactos finales del skill de diseno de red.

Este script existe porque su responsabilidad  transformar el resultado ya calculado en
artefactos de integracion:

- un JSON de handoff para el siguiente skill
- un PDF con la explicacion en lenguaje natural
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

from json_io import ensure_output_dir, load_json, write_json
from pdf_export import write_pdf

import evaluate_network_design as evaluator


HANDOFF_FILENAME = "network_design_handoff.json"
PDF_FILENAME = "network_design_explanation.pdf"


def export_outputs(
    source_input: Dict[str, Any],
    result: Dict[str, Any],
    output_dir: str | None = None,
) -> Dict[str, Any]:
    """Genera el JSON de handoff y el PDF del skill de diseno.

    `source_input` es la entrada original del usuario ya estructurada.
    `result` es la salida del motor `evaluate_network_design.py`.

    Si el resultado no esta en estado `ok`, no se escribe el handoff porque
    el contrato solo debe emitirse cuando el diseno es valido y completo.
    """
    # La explicacion natural se arma una vez y se reutiliza tanto para respuesta
    # humana como para el PDF exportado.
    explanation = evaluator.build_design_explanation(source_input, result)
    if result.get("status") != "ok":
        return {
            "status": "needs_input",
            "message": result.get("message"),
            "missing_fields": result.get("missing_fields", []),
            "explanation": explanation,
        }

    # Convierte el resultado tecnico al contrato desacoplado que consumira
    # el skill de cotizacion.
    handoff_payload = evaluator.build_design_handoff_payload(source_input, result)
    output_path = ensure_output_dir(SKILL_ROOT, output_dir)
    handoff_path = output_path / HANDOFF_FILENAME
    pdf_path = output_path / PDF_FILENAME

    # Escribe ambos artefactos con nombres estables para integracion futura.
    write_json(handoff_path, handoff_payload)
    write_pdf(pdf_path, "Network Design Explanation", explanation)

    return {
        "status": "ok",
        "handoff_path": str(handoff_path),
        "pdf_path": str(pdf_path),
        "handoff": handoff_payload,
        "explanation": explanation,
    }


def main() -> None:
    """CLI simple para exportar los artefactos del skill de diseno."""
    parser = argparse.ArgumentParser(description="Export handoff JSON and PDF for a network design.")
    parser.add_argument("--input", required=True, help="Path to structured network design input JSON.")
    parser.add_argument("--rules", default=str(evaluator.DEFAULT_RULES), help="Path to technical_rules.json.")
    parser.add_argument("--output-dir", default=None, help="Optional output directory. Defaults to skill output/.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print the JSON summary to stdout.")
    args = parser.parse_args()

    # Primero evalua el diseno y despues exporta los artefactos derivados.
    source_input = load_json(Path(args.input))
    result = evaluator.evaluate(source_input, load_json(Path(args.rules)))
    exported = export_outputs(source_input, result, args.output_dir)
    print(json.dumps(exported, indent=2 if args.pretty else None, ensure_ascii=False))


if __name__ == "__main__":
    main()
