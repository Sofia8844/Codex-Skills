#!/usr/bin/env python3
"""Export deterministic handoff JSON and PDF for the network design skill."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict


SKILL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[4]
SHARED_NETWORK_DIR = REPO_ROOT / ".codex" / "shared" / "network"

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
    """Generate the handoff JSON and explanation PDF for a successful design."""
    explanation = evaluator.build_design_explanation(source_input, result)
    if result.get("status") != "ok":
        return {
            "status": "needs_input",
            "message": result.get("message"),
            "missing_fields": result.get("missing_fields", []),
            "explanation": explanation,
        }

    handoff_payload = evaluator.build_design_handoff_payload(source_input, result)
    output_path = ensure_output_dir(SKILL_ROOT, output_dir)
    handoff_path = output_path / HANDOFF_FILENAME
    pdf_path = output_path / PDF_FILENAME

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
    parser = argparse.ArgumentParser(description="Export handoff JSON and PDF for a network design.")
    parser.add_argument("--input", required=True, help="Path to structured network design input JSON.")
    parser.add_argument("--rules", default=str(evaluator.DEFAULT_RULES), help="Path to technical_rules.json.")
    parser.add_argument("--output-dir", default=None, help="Optional output directory. Defaults to skill output/.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print the JSON summary to stdout.")
    args = parser.parse_args()

    source_input = load_json(Path(args.input))
    result = evaluator.evaluate(source_input, load_json(Path(args.rules)))
    exported = export_outputs(source_input, result, args.output_dir)
    print(json.dumps(exported, indent=2 if args.pretty else None, ensure_ascii=False))


if __name__ == "__main__":
    main()
