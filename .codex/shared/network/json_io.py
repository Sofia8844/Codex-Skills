"""Helpers compartidos para leer/escribir JSON y manejar carpetas de salida."""

from __future__ import annotations

import json
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
