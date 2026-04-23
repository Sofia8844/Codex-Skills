"""Helpers compartidos para leer/escribir JSON y manejar carpetas de salida."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict


def load_json(path: Path) -> Dict[str, Any]:
    """Carga un archivo JSON desde disco usando UTF-8."""
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    """Escribe un archivo JSON a disco con formato legible."""
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def ensure_output_dir(base_dir: Path, output_dir: str | None = None) -> Path:
    """Garantiza que exista la carpeta de salida y devuelve su ruta."""
    directory = Path(output_dir) if output_dir else base_dir / "output"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def slugify_case_name(value: str | None, default: str = "case") -> str:
    """Convierte un nombre libre en un slug estable para carpetas de salida."""
    text = (value or "").strip().lower()
    if not text:
        return default
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or default


def ensure_case_output_dir(
    repo_root: Path,
    case_name: str | None,
    output_dir: str | None = None,
) -> Path:
    """Resuelve la carpeta de salida por caso.

    Si `output_dir` viene informado, se respeta tal cual.
    Si no, crea y devuelve `analysis_output/<slug-del-caso>/`.
    """
    if output_dir:
        directory = Path(output_dir)
    else:
        directory = repo_root / "analysis_output" / slugify_case_name(case_name)
    directory.mkdir(parents=True, exist_ok=True)
    return directory
