#!/usr/bin/env python3
"""Exporta los artefactos finales del skill de cotizacion.

Este script existe separado del motor de cotizacion porque su responsabilidad
no es seleccionar SKUs ni calcular subtotales, sino empaquetar el resultado
comercial en artefactos persistentes:

- un JSON final de salida del skill
- un PDF con la explicacion comercial en lenguaje natural
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

import quote_engine


JSON_FILENAME = "network_quote_output.json"
PDF_FILENAME = "network_quote_explanation.pdf"


def export_outputs(source_input: Dict[str, Any], result: Dict[str, Any], output_dir: str | None = None) -> Dict[str, Any]:
    """Genera el JSON final y el PDF del skill de cotizacion.

    `source_input` puede venir como handoff, como `quote_ready_input` o como
    input directo.
    `result` es la salida del motor `quote_engine.py`.

    A diferencia del skill de diseno, aqui si se exporta aun cuando el estado
    sea `needs_input`, porque ese resultado tambien es util como salida formal
    del skill y deja trazabilidad de lo que falto.
    """
    # La explicacion natural se reutiliza para el PDF y para el resumen devuelto.
    explanation = quote_engine.build_quote_explanation(source_input, result)
    # Este payload representa la salida formal del skill de cotizacion.
    output_payload = quote_engine.build_quote_output_payload(source_input, result)
    case_name = result.get("site_name") or source_input.get("site_name")
    output_path = ensure_case_output_dir(REPO_ROOT, case_name, output_dir)
    json_path = output_path / JSON_FILENAME
    pdf_path = output_path / PDF_FILENAME

    # Escribe ambos artefactos con nombres estables para integracion futura.
    write_json(json_path, output_payload)
    write_pdf(pdf_path, "Network Quote Explanation", explanation)

    return {
        "status": result.get("status"),
        "json_path": str(json_path),
        "pdf_path": str(pdf_path),
        "output": output_payload,
        "explanation": explanation,
    }


def main() -> None:
    """CLI simple para exportar los artefactos del skill de cotizacion."""
    parser = argparse.ArgumentParser(description="Export quote JSON and PDF artifacts.")
    parser.add_argument("--input", required=True, help="Path to structured quote input JSON.")
    parser.add_argument("--catalog-dir", default=str(quote_engine.DEFAULT_CATALOG), help="Directory containing catalog JSON files.")
    parser.add_argument("--rules", default=str(quote_engine.DEFAULT_RULES), help="Path to quote_rules.json.")
    parser.add_argument("--output-dir", default=None, help="Optional output directory. Defaults to analysis_output/<site_name>/.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print the JSON summary to stdout.")
    args = parser.parse_args()

    # Primero ejecuta el motor comercial y luego exporta los artefactos derivados.
    source_input = load_json(Path(args.input))
    result = quote_engine.evaluate(
        source_input,
        quote_engine.load_catalog(Path(args.catalog_dir)),
        load_json(Path(args.rules)),
    )
    exported = export_outputs(source_input, result, args.output_dir)
    print(json.dumps(exported, indent=2 if args.pretty else None, ensure_ascii=False))


if __name__ == "__main__":
    main()
