#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import unicodedata
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


SKILL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INFO_DIRS = (
    SKILL_ROOT / "assets" / "Informacion",
    SKILL_ROOT / "assets" / "informacion",
)

WHITESPACE = b" \t\r\n\x0c\x00"
DELIMITERS = b"()<>[]{}/%"
OBJ_RE = re.compile(rb"(?ms)^(\d+)\s+(\d+)\s+obj\b(.*?)\bendobj\b")
REF_RE = re.compile(rb"(\d+)\s+(\d+)\s+R")

try:
    from pypdf import PdfReader as _PrimaryPdfReader  # type: ignore

    PDF_BACKEND = "pypdf"
except Exception:  # pragma: no cover - environment dependent
    try:
        from PyPDF2 import PdfReader as _PrimaryPdfReader  # type: ignore

        PDF_BACKEND = "PyPDF2"
    except Exception:  # pragma: no cover - environment dependent
        _PrimaryPdfReader = None
        PDF_BACKEND = "builtin"


@dataclass
class FontMap:
    name: str
    source: str
    mapping: Dict[bytes, str] = field(default_factory=dict)

    @property
    def code_lengths(self) -> List[int]:
        lengths = {len(key) for key in self.mapping}
        return sorted(lengths, reverse=True)

    def decode_bytes(self, raw: bytes) -> str:
        if not raw:
            return ""
        if not self.mapping:
            return fallback_decode_bytes(raw)

        pieces: List[str] = []
        index = 0
        lengths = self.code_lengths

        while index < len(raw):
            matched = False
            for size in lengths:
                key = raw[index : index + size]
                if key in self.mapping:
                    pieces.append(self.mapping[key])
                    index += size
                    matched = True
                    break
            if matched:
                continue
            pieces.append(fallback_decode_bytes(raw[index : index + 1]))
            index += 1

        return "".join(pieces)


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    stripped = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", stripped).strip().lower()


def find_input_dir(explicit: Optional[str]) -> Path:
    if explicit:
        candidate = Path(explicit).expanduser().resolve()
        if not candidate.exists():
            raise FileNotFoundError(f"No existe la carpeta de PDFs: {candidate}")
        return candidate

    for candidate in DEFAULT_INFO_DIRS:
        if candidate.exists():
            return candidate

    fallback = DEFAULT_INFO_DIRS[0]
    raise FileNotFoundError(
        f"No se encontro la carpeta de informacion. Cree {fallback} o pase --input-dir."
    )


def list_pdf_files(input_dir: Path) -> List[Path]:
    return sorted(
        (path for path in input_dir.rglob("*.pdf") if path.is_file()),
        key=lambda path: str(path.relative_to(input_dir)).lower(),
    )


def skip_whitespace(data: bytes, index: int) -> int:
    while index < len(data) and data[index] in WHITESPACE:
        index += 1
    return index


def extract_balanced(
    data: bytes, index: int, opening: bytes, closing: bytes
) -> Tuple[bytes, int]:
    depth = 0
    start = index
    step = len(opening)
    close_step = len(closing)

    while index < len(data):
        if data[index : index + step] == opening:
            depth += 1
            index += step
            continue
        if data[index : index + close_step] == closing:
            depth -= 1
            index += close_step
            if depth == 0:
                return data[start:index], index
            continue
        index += 1

    return data[start:], len(data)


def extract_next_value(data: bytes, key: bytes) -> Optional[bytes]:
    marker = data.find(key)
    if marker < 0:
        return None

    index = skip_whitespace(data, marker + len(key))
    if index >= len(data):
        return None

    if data[index : index + 2] == b"<<":
        value, _ = extract_balanced(data, index, b"<<", b">>")
        return value
    if data[index : index + 1] == b"[":
        value, _ = extract_balanced(data, index, b"[", b"]")
        return value
    if data[index : index + 1] == b"/":
        end = index + 1
        while end < len(data) and data[end] not in WHITESPACE + DELIMITERS:
            end += 1
        return data[index:end]

    match = REF_RE.match(data, index)
    if match:
        return match.group(0)

    end = index
    while end < len(data) and data[end] not in WHITESPACE + DELIMITERS:
        end += 1
    return data[index:end]


def parse_object_reference(token: Optional[bytes]) -> Optional[int]:
    if not token:
        return None
    match = REF_RE.fullmatch(token.strip())
    if not match:
        return None
    return int(match.group(1))


def extract_stream_from_object(obj_body: bytes) -> Tuple[bytes, Optional[bytes]]:
    match = re.search(rb"stream\r?\n(.*?)\r?\nendstream", obj_body, re.S)
    if not match:
        return obj_body, None
    dictionary = obj_body[: match.start()]
    stream = match.group(1)
    return dictionary, stream


def parse_filter_chain(dictionary: bytes) -> List[bytes]:
    token = extract_next_value(dictionary, b"/Filter")
    if not token:
        return []
    if token.startswith(b"["):
        return re.findall(rb"/([A-Za-z0-9]+)", token)
    if token.startswith(b"/"):
        return [token[1:]]
    return []


def decode_stream_bytes(stream: bytes, dictionary: bytes) -> bytes:
    data = stream
    for filter_name in parse_filter_chain(dictionary):
        if filter_name == b"FlateDecode":
            data = zlib.decompress(data)
        elif filter_name == b"ASCII85Decode":
            payload = data.strip()
            if not payload.endswith(b"~>"):
                payload += b"~>"
            data = base64.a85decode(payload, adobe=True)
        elif filter_name == b"ASCIIHexDecode":
            payload = re.sub(rb"\s+", b"", data).rstrip(b">")
            if len(payload) % 2 == 1:
                payload += b"0"
            data = bytes.fromhex(payload.decode("ascii"))
        else:
            return stream
    return data


def decode_pdf_literal(raw: bytes) -> bytes:
    result = bytearray()
    index = 0

    while index < len(raw):
        current = raw[index]
        if current != 0x5C:
            result.append(current)
            index += 1
            continue

        index += 1
        if index >= len(raw):
            break

        escaped = raw[index]
        if escaped in b"nrtbf":
            replacements = {
                ord("n"): b"\n",
                ord("r"): b"\r",
                ord("t"): b"\t",
                ord("b"): b"\b",
                ord("f"): b"\f",
            }
            result.extend(replacements[escaped])
            index += 1
            continue
        if escaped in b"()\\":
            result.append(escaped)
            index += 1
            continue
        if escaped in b"\r\n":
            if escaped == 0x0D and index + 1 < len(raw) and raw[index + 1] == 0x0A:
                index += 2
            else:
                index += 1
            continue
        if 48 <= escaped <= 55:
            digits = bytes([escaped])
            index += 1
            for _ in range(2):
                if index < len(raw) and 48 <= raw[index] <= 55:
                    digits += bytes([raw[index]])
                    index += 1
                else:
                    break
            result.append(int(digits, 8))
            continue

        result.append(escaped)
        index += 1

    return bytes(result)


def fallback_decode_bytes(raw: bytes) -> str:
    if not raw:
        return ""
    if b"\x00" in raw and len(raw) % 2 == 0:
        try:
            return raw.decode("utf-16-be")
        except Exception:
            pass
    for encoding in ("utf-8", "latin-1"):
        try:
            return raw.decode(encoding)
        except Exception:
            continue
    return raw.decode("latin-1", errors="ignore")


def decode_cmap_unicode(hex_value: bytes) -> str:
    raw = bytes.fromhex(hex_value.decode("ascii"))
    if not raw:
        return ""
    if len(raw) % 2 == 0:
        try:
            return raw.decode("utf-16-be")
        except Exception:
            pass
    return fallback_decode_bytes(raw)


def parse_to_unicode_map(stream_data: bytes, source: str) -> FontMap:
    mapping: Dict[bytes, str] = {}

    for match in re.finditer(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", stream_data):
        raw_key = bytes.fromhex(match.group(1).decode("ascii"))
        mapping[raw_key] = decode_cmap_unicode(match.group(2))

    range_pattern = re.compile(
        rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>"
    )
    for match in range_pattern.finditer(stream_data):
        start = int(match.group(1), 16)
        end = int(match.group(2), 16)
        target = int(match.group(3), 16)
        key_width = max(1, len(match.group(1)) // 2)
        width = max(1, len(match.group(3)) // 2)

        for offset, codepoint in enumerate(range(start, end + 1)):
            raw_key = codepoint.to_bytes(key_width, "big")
            raw_value = (target + offset).to_bytes(width, "big")
            mapping[raw_key] = decode_cmap_unicode(raw_value.hex().encode("ascii"))

    return FontMap(name=source, source=source, mapping=mapping)


def tokenize_content_stream(data: bytes) -> Iterable[bytes]:
    index = 0
    length = len(data)

    while index < length:
        current = data[index]

        if current in WHITESPACE:
            index += 1
            continue
        if current == 0x25:
            newline = data.find(b"\n", index)
            if newline < 0:
                break
            index = newline + 1
            continue
        if data[index : index + 2] == b"<<":
            yield b"<<"
            index += 2
            continue
        if data[index : index + 2] == b">>":
            yield b">>"
            index += 2
            continue
        if current == 0x28:
            start = index
            depth = 1
            index += 1
            while index < length and depth > 0:
                if data[index] == 0x5C:
                    index += 2
                    continue
                if data[index] == 0x28:
                    depth += 1
                elif data[index] == 0x29:
                    depth -= 1
                index += 1
            yield data[start:index]
            continue
        if current == 0x3C and data[index : index + 2] != b"<<":
            end = data.find(b">", index + 1)
            if end < 0:
                end = length - 1
            yield data[index : end + 1]
            index = end + 1
            continue
        if current == 0x5B:
            token, index = extract_array_token(data, index)
            yield token
            continue
        if current == 0x2F:
            end = index + 1
            while end < length and data[end] not in WHITESPACE + DELIMITERS:
                end += 1
            yield data[index:end]
            index = end
            continue

        end = index
        while end < length and data[end] not in WHITESPACE + DELIMITERS:
            end += 1
        yield data[index:end]
        index = end


def extract_array_token(data: bytes, index: int) -> Tuple[bytes, int]:
    start = index
    depth = 1
    index += 1

    while index < len(data) and depth > 0:
        current = data[index]
        if current == 0x5C:
            index += 2
            continue
        if current == 0x28:
            _, index = extract_literal_token(data, index)
            continue
        if current == 0x5B:
            depth += 1
            index += 1
            continue
        if current == 0x5D:
            depth -= 1
            index += 1
            continue
        index += 1

    return data[start:index], index


def extract_literal_token(data: bytes, index: int) -> Tuple[bytes, int]:
    start = index
    depth = 1
    index += 1

    while index < len(data) and depth > 0:
        if data[index] == 0x5C:
            index += 2
            continue
        if data[index] == 0x28:
            depth += 1
        elif data[index] == 0x29:
            depth -= 1
        index += 1

    return data[start:index], index


def decode_pdf_string(token: bytes, font_map: Optional[FontMap]) -> str:
    if not token:
        return ""

    if token.startswith(b"(") and token.endswith(b")"):
        raw = decode_pdf_literal(token[1:-1])
        if font_map and (b"\x00" in raw or not raw.isascii()):
            return font_map.decode_bytes(raw)
        return fallback_decode_bytes(raw)

    if token.startswith(b"<") and token.endswith(b">") and token not in (b"<<", b">>"):
        payload = re.sub(rb"\s+", b"", token[1:-1])
        if len(payload) % 2 == 1:
            payload += b"0"
        raw = bytes.fromhex(payload.decode("ascii"))
        if font_map:
            return font_map.decode_bytes(raw)
        return fallback_decode_bytes(raw)

    return ""


def decode_tj_array(token: bytes, font_map: Optional[FontMap]) -> str:
    if not token.startswith(b"[") or not token.endswith(b"]"):
        return ""

    pieces: List[str] = []
    for inner in tokenize_content_stream(token[1:-1]):
        if inner.startswith((b"(", b"<")):
            pieces.append(decode_pdf_string(inner, font_map))
    return "".join(pieces)


def is_operator(token: bytes) -> bool:
    return bool(re.fullmatch(rb"[A-Za-z\*'\"]{1,4}", token))


def extract_text_from_stream(stream_data: bytes, fonts: Dict[str, FontMap]) -> str:
    if b"BT" not in stream_data:
        return ""

    pieces: List[str] = []
    text_blocks = re.finditer(rb"BT(.*?)ET", stream_data, re.S)

    for block_match in text_blocks:
        block = block_match.group(1)
        current_font: Optional[FontMap] = None
        operands: List[bytes] = []

        for token in tokenize_content_stream(block):
            if not is_operator(token):
                operands.append(token)
                continue

            if token == b"Tf":
                if len(operands) >= 2 and operands[-2].startswith(b"/"):
                    font_name = operands[-2][1:].decode("latin-1", errors="ignore")
                    current_font = fonts.get(font_name)
                operands.clear()
                continue

            if token == b"Tj":
                if operands:
                    pieces.append(decode_pdf_string(operands[-1], current_font))
                    pieces.append(" ")
                operands.clear()
                continue

            if token == b"TJ":
                if operands:
                    pieces.append(decode_tj_array(operands[-1], current_font))
                    pieces.append(" ")
                operands.clear()
                continue

            if token == b"'":
                pieces.append("\n")
                if operands:
                    pieces.append(decode_pdf_string(operands[-1], current_font))
                    pieces.append(" ")
                operands.clear()
                continue

            if token == b'"':
                pieces.append("\n")
                if operands:
                    pieces.append(decode_pdf_string(operands[-1], current_font))
                    pieces.append(" ")
                operands.clear()
                continue

            if token in {b"T*", b"Td", b"TD"}:
                pieces.append("\n")

            operands.clear()

    return clean_text("".join(pieces))


def clean_text(text: str) -> str:
    text = text.replace("\x06", " ")
    text = text.replace("\r", "\n")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    blocks = []
    for raw_block in re.split(r"\n{2,}", text):
        lines = [line.strip() for line in raw_block.splitlines() if line.strip()]
        if not lines:
            continue
        short_lines = sum(1 for line in lines if len(line) <= 2)
        if short_lines / max(1, len(lines)) >= 0.45:
            block = "".join(lines)
        else:
            block = " ".join(lines)
        block = re.sub(r"\s+", " ", block).strip()
        if block:
            blocks.append(block)
    if not blocks:
        return ""
    short_blocks = sum(1 for block in blocks if len(block) <= 24)
    if short_blocks / len(blocks) >= 0.5:
        return re.sub(r"\s+", " ", " ".join(blocks)).strip()
    return "\n\n".join(blocks).strip()


def load_pdf_objects(pdf_path: Path) -> Dict[int, bytes]:
    data = pdf_path.read_bytes()
    objects: Dict[int, bytes] = {}
    for match in OBJ_RE.finditer(data):
        object_number = int(match.group(1))
        objects[object_number] = match.group(3).strip()
    return objects


def build_font_maps(objects: Dict[int, bytes]) -> Dict[int, FontMap]:
    font_maps: Dict[int, FontMap] = {}
    for object_number, body in objects.items():
        reference = parse_object_reference(extract_next_value(body, b"/ToUnicode"))
        if not reference or reference not in objects:
            continue
        cmap_dictionary, cmap_stream = extract_stream_from_object(objects[reference])
        if cmap_stream is None:
            continue
        decoded = decode_stream_bytes(cmap_stream, cmap_dictionary)
        font_maps[object_number] = parse_to_unicode_map(decoded, source=str(object_number))
    return font_maps


def resolve_resources_body(
    page_body: bytes, objects: Dict[int, bytes], visited: Optional[set[int]] = None
) -> bytes:
    visited = visited or set()
    token = extract_next_value(page_body, b"/Resources")
    if not token:
        return b""
    if token.startswith(b"<<"):
        return token

    reference = parse_object_reference(token)
    if reference is None or reference in visited or reference not in objects:
        return b""
    visited.add(reference)
    return objects[reference]


def resolve_page_fonts(
    page_body: bytes, objects: Dict[int, bytes], font_maps: Dict[int, FontMap]
) -> Dict[str, FontMap]:
    resources_body = resolve_resources_body(page_body, objects)
    if not resources_body:
        return {}

    font_token = extract_next_value(resources_body, b"/Font")
    if not font_token:
        return {}
    if not font_token.startswith(b"<<"):
        reference = parse_object_reference(font_token)
        if reference and reference in objects:
            font_token = objects[reference]

    fonts: Dict[str, FontMap] = {}
    for name, object_ref in re.findall(rb"/([A-Za-z0-9_.-]+)\s+(\d+)\s+\d+\s+R", font_token):
        font_map = font_maps.get(int(object_ref))
        if font_map:
            fonts[name.decode("latin-1")] = font_map
    return fonts


def resolve_content_references(page_body: bytes) -> List[int]:
    token = extract_next_value(page_body, b"/Contents")
    if not token:
        return []

    if token.startswith(b"["):
        refs = []
        for object_ref, _generation in re.findall(rb"(\d+)\s+(\d+)\s+R", token):
            refs.append(int(object_ref))
        return refs

    reference = parse_object_reference(token)
    return [reference] if reference is not None else []


def extract_with_builtin(pdf_path: Path) -> List[Dict[str, object]]:
    objects = load_pdf_objects(pdf_path)
    font_maps = build_font_maps(objects)
    pages: List[Dict[str, object]] = []

    for page_body in (
        body
        for _object_number, body in sorted(objects.items())
        if re.search(rb"/Type\s*/Page\b", body) and not re.search(rb"/Type\s*/Pages\b", body)
    ):
        page_number = len(pages) + 1
        fonts = resolve_page_fonts(page_body, objects, font_maps)
        content_refs = resolve_content_references(page_body)
        text_parts: List[str] = []

        for reference in content_refs:
            if reference not in objects:
                continue
            dictionary, stream = extract_stream_from_object(objects[reference])
            if stream is None:
                continue
            try:
                decoded_stream = decode_stream_bytes(stream, dictionary)
            except Exception:
                decoded_stream = stream
            if b"BT" not in decoded_stream and b"Tj" not in decoded_stream and b"TJ" not in decoded_stream:
                continue
            extracted = extract_text_from_stream(decoded_stream, fonts)
            if extracted:
                text_parts.append(extracted)

        pages.append(
            {
                "page": page_number,
                "text": clean_text("\n\n".join(part for part in text_parts if part)),
            }
        )

    return pages


def extract_with_primary_backend(pdf_path: Path) -> List[Dict[str, object]]:
    if _PrimaryPdfReader is None:
        raise RuntimeError("No hay backend PDF principal disponible")

    reader = _PrimaryPdfReader(str(pdf_path))
    pages: List[Dict[str, object]] = []

    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.append({"page": index, "text": clean_text(text)})

    return pages


def extract_pdf(pdf_path: Path) -> Dict[str, object]:
    backend_used = PDF_BACKEND
    pages: List[Dict[str, object]]

    if _PrimaryPdfReader is not None:
        try:
            pages = extract_with_primary_backend(pdf_path)
        except Exception:
            backend_used = "builtin"
            pages = extract_with_builtin(pdf_path)
        else:
            if not any(page["text"] for page in pages):
                backend_used = "builtin"
                pages = extract_with_builtin(pdf_path)
    else:
        pages = extract_with_builtin(pdf_path)

    combined_text = "\n\n".join(
        page["text"] for page in pages if isinstance(page.get("text"), str) and page["text"]
    )

    return {
        "file": pdf_path.name,
        "path": str(pdf_path),
        "backend": backend_used,
        "page_count": len(pages),
        "pages": pages,
        "text": combined_text,
    }


def split_chunks(text: str, limit: int = 700) -> List[str]:
    base_chunks = [chunk.strip() for chunk in re.split(r"\n{2,}", text) if chunk.strip()]
    chunks: List[str] = []
    for chunk in base_chunks:
        if len(chunk) <= limit:
            chunks.append(chunk)
            continue
        sentences = re.split(r"(?<=[.!?])\s+", chunk)
        current = ""
        for sentence in sentences:
            if not sentence:
                continue
            candidate = f"{current} {sentence}".strip()
            if current and len(candidate) > limit:
                chunks.append(current.strip())
                current = sentence
            else:
                current = candidate
        if current.strip():
            chunks.append(current.strip())
    return chunks or [text.strip()]


def score_chunk(query: str, chunk: str, file_name: str) -> int:
    normalized_query = normalize_text(query)
    normalized_chunk = normalize_text(chunk)
    normalized_file = normalize_text(file_name)
    tokens = [token for token in normalized_query.split(" ") if token]

    if not normalized_chunk:
        return 0

    score = 0
    if normalized_query and normalized_query in normalized_chunk:
        score += 120
    if normalized_query and normalized_query in normalized_file:
        score += 60

    unique_tokens = set(tokens)
    token_hits = sum(1 for token in unique_tokens if token in normalized_chunk)
    score += token_hits * 18

    if tokens:
        coverage = token_hits / len(unique_tokens)
        score += int(coverage * 25)

    return score


def search_documents(
    documents: Sequence[Dict[str, object]],
    query: str,
    top: int,
    max_snippets: int,
) -> List[Dict[str, object]]:
    matches: List[Dict[str, object]] = []

    for document in documents:
        file_name = str(document["file"])
        for page in document["pages"]:
            page_number = int(page["page"])
            page_text = str(page["text"] or "")
            if not page_text:
                continue
            page_matches = []
            for chunk in split_chunks(page_text):
                score = score_chunk(query, chunk, file_name)
                if score > 0:
                    page_matches.append(
                        {
                            "file": file_name,
                            "path": document["path"],
                            "backend": document["backend"],
                            "page": page_number,
                            "score": score,
                            "snippet": chunk,
                        }
                    )
            page_matches.sort(key=lambda item: item["score"], reverse=True)
            matches.extend(page_matches[:max_snippets])

    matches.sort(key=lambda item: (item["score"], -int(item["page"])), reverse=True)
    return matches[:top]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Lee y busca informacion dentro de PDFs locales del skill."
    )
    parser.add_argument(
        "--input-dir",
        help=(
            "Carpeta con PDFs. Si no se pasa, usa assets/Informacion o assets/informacion "
            "y busca tambien en sus subcarpetas."
        ),
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="Lista los PDFs disponibles.")
    list_parser.add_argument("--pretty", action="store_true")

    extract_parser = subparsers.add_parser(
        "extract", help="Extrae el texto de un PDF o de todos los PDFs."
    )
    extract_parser.add_argument("--file", help="Nombre exacto del PDF a extraer.")
    extract_parser.add_argument("--pretty", action="store_true")

    search_parser = subparsers.add_parser(
        "search", help="Busca contenido relevante dentro de los PDFs."
    )
    search_parser.add_argument("--query", required=True, help="Consulta a buscar.")
    search_parser.add_argument("--file", help="Nombre exacto del PDF a consultar.")
    search_parser.add_argument("--top", type=int, default=5, help="Numero maximo de matches.")
    search_parser.add_argument(
        "--max-snippets",
        type=int,
        default=2,
        help="Numero maximo de snippets por pagina.",
    )
    search_parser.add_argument("--pretty", action="store_true")

    return parser


def select_documents(pdf_files: Sequence[Path], file_name: Optional[str]) -> List[Path]:
    if not file_name:
        return list(pdf_files)

    normalized_target = normalize_text(file_name)
    exact = [path for path in pdf_files if normalize_text(path.name) == normalized_target]
    if exact:
        return exact

    stem_matches = [path for path in pdf_files if normalize_text(path.stem) == normalized_target]
    if stem_matches:
        return stem_matches

    raise FileNotFoundError(f"No se encontro el PDF solicitado: {file_name}")


def print_json(payload: Dict[str, object], pretty: bool) -> None:
    indent = 2 if pretty else None
    rendered = json.dumps(payload, ensure_ascii=False, indent=indent)
    sys.stdout.buffer.write(rendered.encode("utf-8", errors="replace"))
    sys.stdout.buffer.write(b"\n")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    input_dir = find_input_dir(args.input_dir)
    pdf_files = list_pdf_files(input_dir)

    if args.command == "list":
        payload = {
            "input_dir": str(input_dir),
            "backend_preference": PDF_BACKEND,
            "documents": [{"file": path.name, "path": str(path)} for path in pdf_files],
        }
        print_json(payload, args.pretty)
        return 0

    selected_files = select_documents(pdf_files, getattr(args, "file", None))
    documents = [extract_pdf(path) for path in selected_files]

    if args.command == "extract":
        payload = {
            "input_dir": str(input_dir),
            "document_count": len(documents),
            "documents": documents,
        }
        print_json(payload, args.pretty)
        return 0

    if args.command == "search":
        matches = search_documents(
            documents=documents,
            query=args.query,
            top=max(1, args.top),
            max_snippets=max(1, args.max_snippets),
        )
        payload = {
            "input_dir": str(input_dir),
            "query": args.query,
            "document_count": len(documents),
            "matches": matches,
            "documents": [
                {
                    "file": document["file"],
                    "path": document["path"],
                    "backend": document["backend"],
                    "page_count": document["page_count"],
                }
                for document in documents
            ],
        }
        print_json(payload, args.pretty)
        return 0

    parser.error("Comando no soportado")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
