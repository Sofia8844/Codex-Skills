#!/usr/bin/env python3
"""Exporta los artefactos finales del skill de cotizacion.

Este script existe separado del motor de cotizacion porque su responsabilidad
no es seleccionar SKUs ni calcular subtotales, sino empaquetar el resultado
comercial en artefactos persistentes:

- un JSON final de salida del skill
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

import quote_engine


JSON_FILENAME = "network_quote_output.json"
MARKDOWN_FILENAME = "network_quote_explanation.md"
PDF_FILENAME = "network_quote_explanation.pdf"


def resolve_explanation_text(
    source_input: Dict[str, Any],
    result: Dict[str, Any],
    output_path: Path,
    explanation_file: str | None = None,
) -> tuple[str, Path, str]:
    """Resuelve la explicacion comercial visible para Markdown y PDF.

    Prioridad:
    1. Un archivo explicito recibido por argumento.
    2. `network_quote_explanation.md` existente en la carpeta del caso.
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
        explanation_text = quote_engine.build_quote_explanation(source_input, result)

    # Siempre deja persistida la explicacion usada por el PDF en la ruta estable.
    artifact_markdown_path.write_text(f"{explanation_text.rstrip()}\n", encoding="utf-8")
    return explanation_text, artifact_markdown_path, explanation_source


def export_outputs(
    source_input: Dict[str, Any],
    result: Dict[str, Any],
    output_dir: str | None = None,
    explanation_file: str | None = None,
) -> Dict[str, Any]:
    """Genera el JSON final, el Markdown y el PDF del skill de cotizacion.

    `source_input` puede venir como handoff, como `quote_ready_input` o como
    input directo.
    `result` es la salida del motor `quote_engine.py`.

    A diferencia del skill de diseno, aqui si se exporta aun cuando el estado
    sea `needs_input`, porque ese resultado tambien es util como salida formal
    del skill y deja trazabilidad de lo que falto.
    """
    case_name = result.get("site_name") or source_input.get("site_name")
    output_path = ensure_case_output_dir(REPO_ROOT, case_name, output_dir)
    json_path = output_path / JSON_FILENAME
    pdf_path = output_path / PDF_FILENAME

    # La explicacion visible puede venir de un Markdown escrito por Codex
    # o, si no existe, desde el fallback deterministico del motor comercial.
    explanation, explanation_md_path, explanation_source = resolve_explanation_text(
        source_input,
        result,
        output_path,
        explanation_file,
    )

    # Este payload representa la salida formal del skill de cotizacion.
    output_payload = quote_engine.build_quote_output_payload(source_input, result)

    # Escribe todos los artefactos con nombres estables para integracion futura.
    write_json(json_path, output_payload)
    write_pdf(pdf_path, "Network Quote Explanation", explanation)

    return {
        "status": result.get("status"),
        "json_path": str(json_path),
        "explanation_md_path": str(explanation_md_path),
        "pdf_path": str(pdf_path),
        "explanation_source": explanation_source,
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
    parser.add_argument(
        "--explanation-file",
        default=None,
        help="Optional Markdown file with the final visible quote explanation. If omitted, the exporter auto-detects network_quote_explanation.md in the case folder or falls back to the deterministic explanation.",
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print the JSON summary to stdout.")
    args = parser.parse_args()

    # Primero ejecuta el motor comercial y luego exporta los artefactos derivados.
    source_input = load_json(Path(args.input))
    result = quote_engine.evaluate(
        source_input,
        quote_engine.load_catalog(Path(args.catalog_dir)),
        load_json(Path(args.rules)),
    )
    exported = export_outputs(source_input, result, args.output_dir, args.explanation_file)
    print(json.dumps(exported, indent=2 if args.pretty else None, ensure_ascii=False))


if __name__ == "__main__":
    main()
