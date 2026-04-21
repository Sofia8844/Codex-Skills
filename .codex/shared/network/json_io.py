"""Shared JSON and output-directory helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def load_json(path: Path) -> Dict[str, Any]:
    """Load UTF-8 JSON from disk."""
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    """Write UTF-8 JSON to disk."""
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def ensure_output_dir(base_dir: Path, output_dir: str | None = None) -> Path:
    """Return an ensured output directory."""
    directory = Path(output_dir) if output_dir else base_dir / "output"
    directory.mkdir(parents=True, exist_ok=True)
    return directory
