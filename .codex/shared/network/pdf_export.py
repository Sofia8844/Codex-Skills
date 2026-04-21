"""Minimal PDF export helper for text-based skill outputs."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import List


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _wrap_lines(text: str, width: int = 94) -> List[str]:
    wrapped: List[str] = []
    for raw_line in text.splitlines():
        if not raw_line.strip():
            wrapped.append("")
            continue
        wrapped.extend(textwrap.wrap(raw_line, width=width, replace_whitespace=False) or [""])
    return wrapped or [""]


def build_pdf_bytes(title: str, text: str) -> bytes:
    """Build a simple multi-page PDF using Helvetica."""
    lines = [title, ""] + _wrap_lines(text)
    lines_per_page = 46
    pages = [
        lines[index:index + lines_per_page]
        for index in range(0, len(lines), lines_per_page)
    ] or [[""]]

    objects: List[bytes] = []
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(b"<< /Type /Pages /Kids [] /Count 0 >>")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    page_refs: List[str] = []
    for page_index, page_lines in enumerate(pages):
        page_obj_num = 4 + page_index * 2
        content_obj_num = page_obj_num + 1
        page_refs.append(f"{page_obj_num} 0 R")
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_obj_num} 0 R >>"
            ).encode("latin-1")
        )

        text_commands = ["BT", "/F1 11 Tf", "14 TL", "50 760 Td"]
        first_line = True
        for line in page_lines:
            escaped = _escape(line)
            if first_line:
                text_commands.append(f"({escaped}) Tj")
                first_line = False
            else:
                text_commands.append("T*")
                text_commands.append(f"({escaped}) Tj")
        text_commands.append("ET")
        stream_body = "\n".join(text_commands).encode("latin-1", errors="replace")
        stream = (
            f"<< /Length {len(stream_body)} >>\nstream\n".encode("latin-1")
            + stream_body
            + b"\nendstream"
        )
        objects.append(stream)

    objects[1] = (
        f"<< /Type /Pages /Kids [{' '.join(page_refs)}] /Count {len(page_refs)} >>"
    ).encode("latin-1")

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode("latin-1"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")

    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))
    pdf.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF"
        ).encode("latin-1")
    )
    return bytes(pdf)


def write_pdf(path: Path, title: str, text: str) -> None:
    """Write a simple text PDF to disk."""
    path.write_bytes(build_pdf_bytes(title, text))
