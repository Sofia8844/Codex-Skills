"""Helper para exportar Markdown simple a PDF legible."""

from __future__ import annotations

import re
import textwrap
from pathlib import Path
from typing import Any, Dict, List


RenderLine = Dict[str, Any]


def _escape(text: str) -> str:
    """Escapa caracteres especiales para que el texto sea valido en PDF."""
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _clean_inline(text: str) -> str:
    """Limpia marcas Markdown inline que no renderizamos como estilos parciales."""
    return text.replace("**", "").replace("`", "").strip()


def _is_table_line(line: str) -> bool:
    """Detecta filas Markdown de tabla."""
    stripped = line.strip()
    return stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 2


def _is_separator_row(cells: List[str]) -> bool:
    """Detecta la fila separadora de una tabla Markdown."""
    return all(re.fullmatch(r":?-{3,}:?", cell.strip()) for cell in cells)


def _split_table_row(line: str) -> List[str]:
    """Divide una fila Markdown de tabla en celdas limpias."""
    return [_clean_inline(cell) for cell in line.strip().strip("|").split("|")]


def _table_widths(column_count: int) -> List[int]:
    """Define anchos estables para tablas frecuentes en documentos tecnicos."""
    if column_count == 2:
        return [32, 52]
    if column_count == 3:
        return [22, 20, 42]
    if column_count == 4:
        return [16, 18, 24, 26]
    return [max(12, 84 // max(column_count, 1))] * column_count


def _add_line(lines: List[RenderLine], text: str, font: str = "F1", size: float = 10.5, leading: float = 14.0) -> None:
    """Agrega una linea con estilo al buffer de renderizado."""
    lines.append({"text": text, "font": font, "size": size, "leading": leading})


def _add_blank(lines: List[RenderLine], leading: float = 8.0) -> None:
    """Agrega espacio vertical sin texto."""
    lines.append({"text": "", "font": "F1", "size": 10.5, "leading": leading})


def _add_wrapped_text(
    lines: List[RenderLine],
    text: str,
    width: int = 92,
    font: str = "F1",
    size: float = 10.5,
    leading: float = 14.0,
    initial_indent: str = "",
    subsequent_indent: str = "",
) -> None:
    """Agrega texto con wrapping para evitar lineas largas en el PDF."""
    wrapped = textwrap.wrap(
        _clean_inline(text),
        width=width,
        initial_indent=initial_indent,
        subsequent_indent=subsequent_indent,
        replace_whitespace=False,
    )
    for item in wrapped or [""]:
        _add_line(lines, item, font=font, size=size, leading=leading)


def _format_table_row(cells: List[str], widths: List[int]) -> List[str]:
    """Convierte una fila de tabla en una o varias lineas monoespaciadas."""
    normalized = cells + [""] * (len(widths) - len(cells))
    wrapped_cells = [
        textwrap.wrap(cell, width=width, replace_whitespace=False) or [""]
        for cell, width in zip(normalized, widths)
    ]
    row_height = max(len(cell_lines) for cell_lines in wrapped_cells)
    formatted: List[str] = []
    for index in range(row_height):
        parts = []
        for cell_lines, width in zip(wrapped_cells, widths):
            value = cell_lines[index] if index < len(cell_lines) else ""
            parts.append(value.ljust(width))
        formatted.append("| " + " | ".join(parts) + " |")
    return formatted


def _add_table(lines: List[RenderLine], table_lines: List[str]) -> None:
    """Renderiza una tabla Markdown como bloque monoespaciado y legible."""
    rows = [_split_table_row(line) for line in table_lines if _is_table_line(line)]
    rows = [row for row in rows if not _is_separator_row(row)]
    if not rows:
        return

    widths = _table_widths(max(len(row) for row in rows))
    header, body = rows[0], rows[1:]
    for rendered in _format_table_row(header, widths):
        _add_line(lines, rendered, font="F4", size=8.4, leading=11.0)
    _add_line(lines, "-" * min(96, sum(widths) + len(widths) * 3 + 1), font="F3", size=8.4, leading=11.0)
    for row in body:
        for rendered in _format_table_row(row, widths):
            _add_line(lines, rendered, font="F3", size=8.4, leading=11.0)
    _add_blank(lines, leading=7.0)


def _markdown_to_render_lines(title: str, text: str) -> List[RenderLine]:
    """Convierte Markdown simple en lineas con estilos basicos para PDF."""
    lines: List[RenderLine] = []
    _add_line(lines, title, font="F2", size=16.0, leading=21.0)
    _add_blank(lines, leading=10.0)

    raw_lines = text.splitlines()
    index = 0
    while index < len(raw_lines):
        raw_line = raw_lines[index]
        stripped = raw_line.strip()

        if not stripped:
            _add_blank(lines)
            index += 1
            continue

        if _is_table_line(stripped):
            table_block: List[str] = []
            while index < len(raw_lines) and _is_table_line(raw_lines[index].strip()):
                table_block.append(raw_lines[index])
                index += 1
            _add_table(lines, table_block)
            continue

        if stripped.startswith("# "):
            _add_blank(lines, leading=8.0)
            _add_wrapped_text(lines, stripped[2:], width=70, font="F2", size=15.0, leading=20.0)
            index += 1
            continue

        if stripped.startswith("## "):
            _add_blank(lines, leading=7.0)
            _add_wrapped_text(lines, stripped[3:], width=76, font="F2", size=13.0, leading=18.0)
            index += 1
            continue

        if stripped.startswith("### "):
            _add_blank(lines, leading=6.0)
            _add_wrapped_text(lines, stripped[4:], width=82, font="F2", size=11.5, leading=16.0)
            index += 1
            continue

        if stripped.startswith("- "):
            _add_wrapped_text(
                lines,
                stripped[2:],
                width=88,
                initial_indent="- ",
                subsequent_indent="  ",
            )
            index += 1
            continue

        _add_wrapped_text(lines, stripped)
        index += 1

    return lines or [{"text": "", "font": "F1", "size": 10.5, "leading": 14.0}]


def _paginate(lines: List[RenderLine]) -> List[List[RenderLine]]:
    """Divide las lineas renderizadas en paginas segun su alto estimado."""
    pages: List[List[RenderLine]] = []
    current: List[RenderLine] = []
    remaining = 710.0

    for line in lines:
        leading = float(line.get("leading", 14.0))
        if current and remaining - leading < 35:
            pages.append(current)
            current = []
            remaining = 710.0
        current.append(line)
        remaining -= leading

    if current:
        pages.append(current)
    return pages or [[{"text": "", "font": "F1", "size": 10.5, "leading": 14.0}]]


def build_pdf_bytes(title: str, text: str) -> bytes:
    """Construye un PDF simple de varias paginas con estilos basicos."""
    pages = _paginate(_markdown_to_render_lines(title, text))

    objects: List[bytes] = []
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(b"<< /Type /Pages /Kids [] /Count 0 >>")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier-Bold >>")

    page_refs: List[str] = []
    for page_index, page_lines in enumerate(pages):
        page_obj_num = 7 + page_index * 2
        content_obj_num = page_obj_num + 1
        page_refs.append(f"{page_obj_num} 0 R")
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                f"/Resources << /Font << /F1 3 0 R /F2 4 0 R /F3 5 0 R /F4 6 0 R >> >> "
                f"/Contents {content_obj_num} 0 R >>"
            ).encode("latin-1")
        )

        text_commands: List[str] = []
        y = 760.0
        for line in page_lines:
            escaped = _escape(str(line.get("text", "")))
            font = line.get("font", "F1")
            size = float(line.get("size", 10.5))
            leading = float(line.get("leading", 14.0))
            text_commands.extend([
                "BT",
                f"/{font} {size:.1f} Tf",
                f"50 {y:.1f} Td",
                f"({escaped}) Tj",
                "ET",
            ])
            y -= leading

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
    """Genera el binario PDF y lo escribe a disco."""
    path.write_bytes(build_pdf_bytes(title, text))
