from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATOR_PATH = ROOT / ".codex" / "skills" / "generar-presentacion" / "build_presentation.py"
IKUSI_SPEC = ROOT / ".codex" / "skills" / "generar-presentacion" / "ikusi-spec.json"


def load_generator_module():
    module_spec = importlib.util.spec_from_file_location("generar_presentacion_skill", GENERATOR_PATH)
    if module_spec is None or module_spec.loader is None:
        raise RuntimeError(f"Could not load generator module from {GENERATOR_PATH}")
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


def main() -> None:
    generator = load_generator_module()
    result = generator.build_from_spec(IKUSI_SPEC)
    print(f"PPTX: {result['output_pptx']}")
    if result["output_notes"] is not None:
        print(f"NOTES: {result['output_notes']}")
    for copied_path in result["extra_output_paths"]:
        print(f"COPY: {copied_path}")
    for warning in result["warnings"]:
        print(f"WARNING: {warning}")


if __name__ == "__main__":
    main()
