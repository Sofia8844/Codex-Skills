from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import sys
import unicodedata
import zipfile
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET


XLSX_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
DOC_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
XML_NS = "http://www.w3.org/XML/1998/namespace"
MC_NS = "http://schemas.openxmlformats.org/markup-compatibility/2006"
X14AC_NS = "http://schemas.microsoft.com/office/spreadsheetml/2009/9/ac"
XR_NS = "http://schemas.microsoft.com/office/spreadsheetml/2014/revision"
XR2_NS = "http://schemas.microsoft.com/office/spreadsheetml/2015/revision2"
XR3_NS = "http://schemas.microsoft.com/office/spreadsheetml/2016/revision3"

NS = {"x": XLSX_NS, "r": DOC_REL_NS, "rel": PKG_REL_NS}

ET.register_namespace("", XLSX_NS)
ET.register_namespace("r", DOC_REL_NS)
ET.register_namespace("mc", MC_NS)
ET.register_namespace("x14ac", X14AC_NS)
ET.register_namespace("xr", XR_NS)
ET.register_namespace("xr2", XR2_NS)
ET.register_namespace("xr3", XR3_NS)

SCRIPT_PATH = Path(__file__).resolve()
SKILL_ROOT = SCRIPT_PATH.parent.parent
ASSETS_DIR = SKILL_ROOT / "assets"
OUTPUT_DIR = SKILL_ROOT / "output"
DEFAULT_BASE_FILE = ASSETS_DIR / "Datos_Financieros_Semanales.xlsx"
DEFAULT_WORKING_FILE = OUTPUT_DIR / DEFAULT_BASE_FILE.name

REQUIRED_UPDATE_FIELDS = ("revenue", "losses", "customers")
OPTIONAL_UPDATE_FIELDS = ("previous_customers", "retained_customers")
METRIC_FIELDS = ("retention_rate", "loss_percentage", "margin")
MANAGED_COLUMN_ORDER = (
    "week",
    "revenue",
    "losses",
    "customers",
    "previous_customers",
    "retained_customers",
    "retention_rate",
    "loss_percentage",
    "margin",
)
SUPPORTED_SUFFIXES = {".csv", ".xlsx", ".xlsm"}

FIELD_ALIASES = {
    "week": {"week", "semana", "period", "periodo"},
    "revenue": {"revenue", "revenues", "ingresos", "income", "sales"},
    "losses": {"losses", "loss", "perdidas", "perdida"},
    "customers": {"customers", "customer", "clientes", "cliente"},
    "previous_customers": {
        "previous_customers",
        "prior_customers",
        "clientes_previos",
        "clientes_anteriores",
        "customer_base_previous",
    },
    "retained_customers": {
        "retained_customers",
        "clientes_retenidos",
        "retained",
    },
    "retention_rate": {
        "retention_rate",
        "retention",
        "retencion",
        "tasa_retencion",
    },
    "loss_percentage": {
        "loss_percentage",
        "loss_rate",
        "porcentaje_perdidas",
        "pct_perdidas",
    },
    "margin": {"margin", "margen"},
}

NUMERIC_CANONICAL_FIELDS = set(REQUIRED_UPDATE_FIELDS) | set(OPTIONAL_UPDATE_FIELDS) | set(METRIC_FIELDS)
XMLNS_DECLARATION_RE = re.compile(rb'\s+xmlns(?::[A-Za-z0-9_.-]+)?="[^"]+"')


class SkillError(Exception):
    """Raised when the payload or the source file is invalid."""


@dataclass
class Payload:
    file_path: Path
    week: str
    updates: dict[str, Decimal]
    sheet_name: str | None = None
    summary_path: Path | None = None


@dataclass
class ColumnBindings:
    week: str
    revenue: str
    losses: str
    customers: str
    retention_rate: str
    loss_percentage: str
    margin: str
    previous_customers: str | None = None
    retained_customers: str | None = None


@dataclass
class XlsxContext:
    archive_infos: list[zipfile.ZipInfo]
    entries: dict[str, bytes]
    sheet_path: str
    sheet_name: str
    header_styles: dict[str, str | None]
    data_styles: dict[str, str | None]
    header_row_attrs: dict[str, str]
    data_row_attrs: dict[str, str]


@dataclass
class TableDocument:
    file_path: Path
    file_type: str
    columns: list[str]
    rows: list[dict[str, Any]]
    sheet_name: str | None = None
    xlsx_context: XlsxContext | None = None


def qname(tag: str) -> str:
    return f"{{{XLSX_NS}}}{tag}"


def strip_xml_declaration(xml_bytes: bytes) -> bytes:
    stripped = xml_bytes.lstrip()
    if stripped.startswith(b"<?xml"):
        declaration_end = stripped.find(b"?>")
        if declaration_end != -1:
            return stripped[declaration_end + 2 :]
    return stripped


def extract_root_namespace_declarations(xml_bytes: bytes) -> list[bytes]:
    content = strip_xml_declaration(xml_bytes)
    opening_end = content.find(b">")
    if opening_end == -1:
        return []
    opening_tag = content[: opening_end + 1]
    return XMLNS_DECLARATION_RE.findall(opening_tag)


def inject_root_namespace_declarations(xml_bytes: bytes, declarations: list[bytes]) -> bytes:
    if not declarations:
        return xml_bytes

    declaration_end = xml_bytes.find(b"?>")
    search_start = declaration_end + 2 if declaration_end != -1 else 0
    opening_start = xml_bytes.find(b"<", search_start)
    opening_end = xml_bytes.find(b">", opening_start)
    if opening_start == -1 or opening_end == -1:
        return xml_bytes

    opening_tag = xml_bytes[opening_start:opening_end]
    missing = [declaration for declaration in declarations if declaration not in opening_tag]
    if not missing:
        return xml_bytes

    return xml_bytes[:opening_end] + b"".join(missing) + xml_bytes[opening_end:]


def strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def normalize_field_name(value: str) -> str:
    ascii_value = strip_accents(str(value)).lower().strip()
    return re.sub(r"[^a-z0-9]+", "_", ascii_value).strip("_")


def sanitize_week_for_filename(week: str) -> str:
    cleaned = normalize_field_name(week)
    return cleaned or "week"


def value_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    return True


def parse_decimal(
    value: Any,
    field_name: str,
    *,
    allow_blank: bool = False,
    integer: bool = False,
    non_negative: bool = True,
) -> Decimal | None:
    if value is None:
        if allow_blank:
            return None
        raise SkillError(f"Missing required value for '{field_name}'.")

    text = str(value).strip()
    if text == "":
        if allow_blank:
            return None
        raise SkillError(f"Missing required value for '{field_name}'.")

    if text.startswith("="):
        raise SkillError(
            f"Field '{field_name}' contains a formula. Managed columns must contain materialized values."
        )

    normalized = text.replace(",", "")
    try:
        number = Decimal(normalized)
    except InvalidOperation as exc:
        raise SkillError(f"Field '{field_name}' must be numeric. Received: {value!r}") from exc

    if non_negative and number < 0:
        raise SkillError(f"Field '{field_name}' cannot be negative.")
    if integer and number != number.to_integral_value():
        raise SkillError(f"Field '{field_name}' must be an integer.")
    return number


def decimal_to_storage(value: Decimal | None) -> str:
    if value is None:
        return ""
    normalized = value.normalize()
    text = format(normalized, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def decimal_to_json(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value)


def round_ratio(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return value.quantize(Decimal("0.000001"))


def canonical_update_key(key: str) -> str:
    normalized = normalize_field_name(key)
    for canonical_name, aliases in FIELD_ALIASES.items():
        if normalized in aliases:
            return canonical_name
    return normalized


def canonical_column_name(column_name: str) -> str | None:
    normalized = normalize_field_name(column_name)
    for canonical_name, aliases in FIELD_ALIASES.items():
        if normalized in aliases:
            return canonical_name
    return None


def numeric_column(column_name: str) -> bool:
    canonical_name = canonical_column_name(column_name)
    return canonical_name in NUMERIC_CANONICAL_FIELDS


def unique_warning_list(warnings: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for warning in warnings:
        if warning not in seen:
            seen.add(warning)
            ordered.append(warning)
    return ordered


def build_backup_path(file_path: Path, week: str) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = file_path.suffix
    stem = f"{file_path.stem}_{sanitize_week_for_filename(week)}_backup"
    candidate = OUTPUT_DIR / f"{stem}{suffix}"
    counter = 2
    while candidate.exists():
        candidate = OUTPUT_DIR / f"{stem}_{counter}{suffix}"
        counter += 1
    return candidate


def seed_working_file_from_asset(target_path: Path, asset_path: Path) -> Path:
    if not asset_path.exists():
        raise SkillError(
            f"Default base file not found: {asset_path}. Add the workbook to assets/ or pass file_path explicitly."
        )
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if not target_path.exists():
        try:
            shutil.copyfile(asset_path, target_path)
        except PermissionError as exc:
            raise SkillError(
                f"Permission denied while creating the working file at {target_path}. "
                f"Approve writes inside actualizar-indicadores/output."
            ) from exc
    return target_path.resolve()


def resolve_source_file(raw_file_path: Any) -> Path:
    if raw_file_path in (None, ""):
        return seed_working_file_from_asset(DEFAULT_WORKING_FILE, DEFAULT_BASE_FILE)

    raw_path = Path(str(raw_file_path).strip()).expanduser()
    if raw_path.is_absolute():
        resolved = raw_path.resolve()
        if resolved.exists():
            return resolved
        raise SkillError(f"Source file not found: {resolved}")

    candidates = [
        (Path.cwd() / raw_path).resolve(),
        (SKILL_ROOT / raw_path).resolve(),
        (OUTPUT_DIR / raw_path).resolve(),
    ]
    if len(raw_path.parts) == 1:
        candidates.append((ASSETS_DIR / raw_path.name).resolve())

    for candidate in candidates:
        if candidate.exists():
            if candidate.parent == ASSETS_DIR.resolve():
                return seed_working_file_from_asset(OUTPUT_DIR / candidate.name, candidate)
            return candidate

    if len(raw_path.parts) == 1:
        asset_candidate = (ASSETS_DIR / raw_path.name).resolve()
        if asset_candidate.exists():
            return seed_working_file_from_asset(OUTPUT_DIR / asset_candidate.name, asset_candidate)

    raise SkillError(
        f"Source file not found: {raw_file_path}. Pass an existing file path or add the base workbook to assets/."
    )


def parse_json_payload(data: dict[str, Any]) -> Payload:
    if not isinstance(data, dict):
        raise SkillError("The input payload must be a JSON object.")

    raw_file_path = data.get("file_path")
    raw_week = data.get("week")
    raw_updates = data.get("updates")
    raw_sheet_name = data.get("sheet_name")
    raw_summary_path = data.get("summary_path")

    if not raw_week or not str(raw_week).strip():
        raise SkillError("The payload must include a non-empty 'week'.")
    if not isinstance(raw_updates, dict):
        raise SkillError("The payload must include an 'updates' object.")

    allowed_keys = set(REQUIRED_UPDATE_FIELDS) | set(OPTIONAL_UPDATE_FIELDS)
    normalized_updates: dict[str, Decimal] = {}
    for raw_key, raw_value in raw_updates.items():
        canonical_key = canonical_update_key(str(raw_key))
        if canonical_key not in allowed_keys:
            raise SkillError(
                f"Unsupported update field '{raw_key}'. Allowed fields: {sorted(allowed_keys)}"
            )
        if canonical_key in normalized_updates:
            raise SkillError(f"Duplicate update field detected for '{canonical_key}'.")
        normalized_updates[canonical_key] = parse_decimal(
            raw_value,
            canonical_key,
            integer=canonical_key in {"customers", "previous_customers", "retained_customers"},
        )

    missing_fields = [field for field in REQUIRED_UPDATE_FIELDS if field not in normalized_updates]
    if missing_fields:
        raise SkillError(f"Missing required update fields: {', '.join(missing_fields)}")

    file_path = resolve_source_file(raw_file_path)
    summary_path = None
    if raw_summary_path:
        summary_path = Path(raw_summary_path).expanduser()
        if not summary_path.is_absolute():
            summary_path = (OUTPUT_DIR / summary_path).resolve()

    return Payload(
        file_path=file_path,
        week=str(raw_week).strip(),
        updates=normalized_updates,
        sheet_name=str(raw_sheet_name).strip() if raw_sheet_name else None,
        summary_path=summary_path,
    )


def payload_from_args(args: argparse.Namespace) -> Payload:
    if args.input_json:
        raw = sys.stdin.read() if args.input_json == "-" else Path(args.input_json).read_text(encoding="utf-8")
        return parse_json_payload(json.loads(raw))

    if args.payload:
        return parse_json_payload(json.loads(args.payload))

    direct_updates: dict[str, Any] = {
        "revenue": args.revenue,
        "losses": args.losses,
        "customers": args.customers,
    }
    if args.previous_customers is not None:
        direct_updates["previous_customers"] = args.previous_customers
    if args.retained_customers is not None:
        direct_updates["retained_customers"] = args.retained_customers

    raw_payload = {
        "file_path": args.file_path,
        "sheet_name": args.sheet_name,
        "week": args.week,
        "summary_path": args.summary_output,
        "updates": direct_updates,
    }
    return parse_json_payload(raw_payload)


def parse_cli_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Update weekly financial indicators in CSV or Excel files in place using the skill output folder for backups and summaries."
    )
    parser.add_argument("--input-json", help="Path to a JSON payload file, or '-' to read JSON from stdin.")
    parser.add_argument("--payload", help="Inline JSON payload.")
    parser.add_argument(
        "--file-path",
        help="Path to the CSV/XLSX/XLSM source file. If omitted, the script uses assets/Datos_Financieros_Semanales.xlsx and works on actualizar-indicadores/output/.",
    )
    parser.add_argument("--sheet-name", help="Optional Excel sheet name. Defaults to the first sheet.")
    parser.add_argument("--week", help="Week identifier to update or append.")
    parser.add_argument("--summary-output", help="Optional path for a summary JSON file.")
    parser.add_argument("--revenue", help="Revenue value for the target week.")
    parser.add_argument("--losses", help="Losses value for the target week.")
    parser.add_argument("--customers", help="Customer count for the target week.")
    parser.add_argument("--previous-customers", help="Optional previous customer base.")
    parser.add_argument("--retained-customers", help="Optional retained customer count.")
    args = parser.parse_args()

    if args.input_json or args.payload:
        return args

    missing_direct = [name for name in ("week", "revenue", "losses", "customers") if getattr(args, name) in (None, "")]
    if missing_direct:
        parser.error(
            "When JSON input is not used, the following arguments are required: "
            + ", ".join(f"--{name.replace('_', '-')}" for name in missing_direct)
        )
    return args


def validate_supported_file(file_path: Path) -> None:
    if not file_path.exists():
        raise SkillError(f"Source file not found: {file_path}")
    if file_path.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise SkillError(
            f"Unsupported file type '{file_path.suffix}'. Supported extensions: {sorted(SUPPORTED_SUFFIXES)}"
        )


def column_index_from_ref(cell_ref: str) -> int:
    letters = "".join(char for char in cell_ref if char.isalpha())
    index = 0
    for char in letters:
        index = index * 26 + (ord(char.upper()) - 64)
    return index


def column_letter_from_index(index: int) -> str:
    letters: list[str] = []
    current = index
    while current > 0:
        current, remainder = divmod(current - 1, 26)
        letters.append(chr(65 + remainder))
    return "".join(reversed(letters))


def extract_shared_strings(entries: dict[str, bytes]) -> list[str]:
    shared_strings_path = "xl/sharedStrings.xml"
    if shared_strings_path not in entries:
        return []
    root = ET.fromstring(entries[shared_strings_path])
    values: list[str] = []
    for string_item in root.findall("x:si", NS):
        values.append("".join(node.text or "" for node in string_item.findall(".//x:t", NS)))
    return values


def read_xlsx_cell(cell: ET.Element, shared_strings: list[str]) -> str:
    cell_type = cell.get("t")
    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.findall(".//x:t", NS))

    value_node = cell.find("x:v", NS)
    if value_node is None or value_node.text is None:
        return ""
    if cell_type == "s":
        return shared_strings[int(value_node.text)]
    return value_node.text


def normalize_sheet_target(target: str) -> str:
    cleaned = target.lstrip("/")
    if cleaned.startswith("xl/"):
        return cleaned
    return f"xl/{cleaned}"


def resolve_sheet_path(entries: dict[str, bytes], requested_sheet_name: str | None) -> tuple[str, str]:
    workbook_root = ET.fromstring(entries["xl/workbook.xml"])
    rels_root = ET.fromstring(entries["xl/_rels/workbook.xml.rels"])
    targets_by_id = {
        relationship.get("Id"): normalize_sheet_target(relationship.get("Target", ""))
        for relationship in rels_root.findall("rel:Relationship", NS)
    }

    sheets = workbook_root.findall("x:sheets/x:sheet", NS)
    if not sheets:
        raise SkillError("The Excel workbook does not contain any sheets.")

    selected_sheet: ET.Element | None = None
    if requested_sheet_name:
        for sheet in sheets:
            if sheet.get("name") == requested_sheet_name:
                selected_sheet = sheet
                break
        if selected_sheet is None:
            raise SkillError(f"Sheet '{requested_sheet_name}' was not found in the workbook.")
    else:
        selected_sheet = sheets[0]

    rel_id = selected_sheet.get(f"{{{DOC_REL_NS}}}id")
    if not rel_id or rel_id not in targets_by_id:
        raise SkillError("Could not resolve the worksheet path from the workbook relationships.")

    sheet_path = targets_by_id[rel_id]
    if sheet_path not in entries:
        raise SkillError(f"Worksheet XML was not found in the archive: {sheet_path}")
    return selected_sheet.get("name", "Sheet1"), sheet_path


def load_csv_document(file_path: Path) -> TableDocument:
    with file_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise SkillError("The CSV file must include a header row.")
        columns = [str(name).strip() for name in reader.fieldnames]
        rows: list[dict[str, Any]] = []
        for raw_row in reader:
            row = {column: raw_row.get(column, "") for column in columns}
            if any(value_present(value) for value in row.values()):
                rows.append(row)
    return TableDocument(file_path=file_path, file_type="csv", columns=columns, rows=rows)


def load_xlsx_document(file_path: Path, requested_sheet_name: str | None) -> TableDocument:
    with zipfile.ZipFile(file_path, "r") as archive:
        archive_infos = archive.infolist()
        entries = {info.filename: archive.read(info.filename) for info in archive_infos}

    shared_strings = extract_shared_strings(entries)
    sheet_name, sheet_path = resolve_sheet_path(entries, requested_sheet_name)
    worksheet_root = ET.fromstring(entries[sheet_path])
    sheet_data = worksheet_root.find("x:sheetData", NS)
    if sheet_data is None:
        raise SkillError("The worksheet does not contain sheetData.")

    worksheet_rows = sheet_data.findall("x:row", NS)
    if not worksheet_rows:
        raise SkillError("The worksheet must include a header row in row 1.")

    header_row = worksheet_rows[0]
    header_styles: dict[str, str | None] = {}
    data_styles: dict[str, str | None] = {}
    header_cells: list[tuple[int, str]] = []
    for cell in header_row.findall("x:c", NS):
        header_value = read_xlsx_cell(cell, shared_strings).strip()
        if not header_value:
            continue
        column_index = column_index_from_ref(cell.get("r", ""))
        header_cells.append((column_index, header_value))
        header_styles[header_value] = cell.get("s")

    if not header_cells:
        raise SkillError("The worksheet header row is empty.")

    header_cells.sort(key=lambda item: item[0])
    columns = [header for _, header in header_cells]
    header_by_index = {index: header for index, header in header_cells}

    rows: list[dict[str, Any]] = []
    for row_elem in worksheet_rows[1:]:
        row = {column: "" for column in columns}
        for cell in row_elem.findall("x:c", NS):
            column_index = column_index_from_ref(cell.get("r", ""))
            header = header_by_index.get(column_index)
            if header is None:
                continue
            row[header] = read_xlsx_cell(cell, shared_strings)
            data_styles.setdefault(header, cell.get("s"))
        if any(value_present(value) for value in row.values()):
            rows.append(row)

    header_row_attrs = {
        key: value for key, value in header_row.attrib.items() if key not in {"r", "spans"}
    }
    first_data_row = worksheet_rows[1] if len(worksheet_rows) > 1 else None
    data_row_attrs: dict[str, str] = {}
    if first_data_row is not None:
        data_row_attrs = {
            key: value for key, value in first_data_row.attrib.items() if key not in {"r", "spans"}
        }

    context = XlsxContext(
        archive_infos=archive_infos,
        entries=entries,
        sheet_path=sheet_path,
        sheet_name=sheet_name,
        header_styles=header_styles,
        data_styles=data_styles,
        header_row_attrs=header_row_attrs,
        data_row_attrs=data_row_attrs,
    )
    return TableDocument(
        file_path=file_path,
        file_type="xlsx",
        columns=columns,
        rows=rows,
        sheet_name=sheet_name,
        xlsx_context=context,
    )


def load_document(file_path: Path, sheet_name: str | None) -> TableDocument:
    validate_supported_file(file_path)
    if file_path.suffix.lower() == ".csv":
        return load_csv_document(file_path)
    return load_xlsx_document(file_path, sheet_name)


def ensure_unique_headers(columns: list[str]) -> None:
    seen: dict[str, str] = {}
    for column in columns:
        normalized = normalize_field_name(column)
        if not normalized:
            raise SkillError("Header names cannot be empty.")
        if normalized in seen and seen[normalized] != column:
            raise SkillError(
                f"Duplicate headers detected after normalization: '{seen[normalized]}' and '{column}'."
            )
        seen[normalized] = column


def find_existing_column(columns: list[str], canonical_name: str) -> str | None:
    aliases = FIELD_ALIASES.get(canonical_name, {canonical_name})
    for column in columns:
        if normalize_field_name(column) in aliases:
            return column
    return None


def ensure_column(document: TableDocument, canonical_name: str) -> str:
    existing = find_existing_column(document.columns, canonical_name)
    if existing:
        return existing
    document.columns.append(canonical_name)
    for row in document.rows:
        row[canonical_name] = ""
    return canonical_name


def reorder_managed_columns(document: TableDocument) -> None:
    ordered_columns: list[str] = []
    seen: set[str] = set()

    for canonical_name in MANAGED_COLUMN_ORDER:
        column_name = find_existing_column(document.columns, canonical_name)
        if column_name and column_name not in seen:
            ordered_columns.append(column_name)
            seen.add(column_name)

    for column_name in document.columns:
        if column_name not in seen:
            ordered_columns.append(column_name)
            seen.add(column_name)

    document.columns = ordered_columns


def bind_columns(document: TableDocument, payload: Payload) -> ColumnBindings:
    ensure_unique_headers(document.columns)

    week_column = find_existing_column(document.columns, "week")
    if week_column is None:
        raise SkillError("The source file must include a week column such as 'week' or 'semana'.")

    revenue_column = ensure_column(document, "revenue")
    losses_column = ensure_column(document, "losses")
    customers_column = ensure_column(document, "customers")
    previous_customers_column = ensure_column(document, "previous_customers")
    retained_customers_column = ensure_column(document, "retained_customers")
    retention_rate_column = ensure_column(document, "retention_rate")
    loss_percentage_column = ensure_column(document, "loss_percentage")
    margin_column = ensure_column(document, "margin")

    reorder_managed_columns(document)

    return ColumnBindings(
        week=week_column,
        revenue=revenue_column,
        losses=losses_column,
        customers=customers_column,
        retention_rate=retention_rate_column,
        loss_percentage=loss_percentage_column,
        margin=margin_column,
        previous_customers=previous_customers_column,
        retained_customers=retained_customers_column,
    )


def get_week_value(row: dict[str, Any], week_column: str) -> str:
    return str(row.get(week_column, "")).strip()


def upsert_target_row(
    document: TableDocument,
    payload: Payload,
    bindings: ColumnBindings,
) -> tuple[str, dict[str, Any], int]:
    matches = [
        index
        for index, row in enumerate(document.rows)
        if get_week_value(row, bindings.week) == payload.week
    ]
    if len(matches) > 1:
        raise SkillError(f"Duplicate week rows found for '{payload.week}'.")

    if matches:
        row_index = matches[0]
        action = "updated"
        row = document.rows[row_index]
        before = {column: row.get(column, "") for column in document.columns}
    else:
        row_index = len(document.rows)
        action = "appended"
        row = {column: "" for column in document.columns}
        row[bindings.week] = payload.week
        document.rows.append(row)
        before = {}

    row[bindings.week] = payload.week
    row[bindings.revenue] = payload.updates["revenue"]
    row[bindings.losses] = payload.updates["losses"]
    row[bindings.customers] = payload.updates["customers"]

    if bindings.previous_customers and "previous_customers" in payload.updates:
        row[bindings.previous_customers] = payload.updates["previous_customers"]
    if bindings.retained_customers and "retained_customers" in payload.updates:
        row[bindings.retained_customers] = payload.updates["retained_customers"]

    return action, before, row_index


def parse_optional_row_number(
    row: dict[str, Any],
    column_name: str | None,
    field_name: str,
    *,
    integer: bool = False,
) -> Decimal | None:
    if column_name is None:
        return None
    return parse_decimal(row.get(column_name), field_name, allow_blank=True, integer=integer)


def recalculate_metrics(document: TableDocument, bindings: ColumnBindings) -> list[str]:
    warnings: list[str] = []
    previous_row_customers: Decimal | None = None

    for index, row in enumerate(document.rows, start=1):
        week_value = get_week_value(row, bindings.week) or f"row-{index + 1}"
        revenue = parse_decimal(row.get(bindings.revenue), f"{week_value}.revenue", allow_blank=True)
        losses = parse_decimal(row.get(bindings.losses), f"{week_value}.losses", allow_blank=True)
        customers = parse_decimal(
            row.get(bindings.customers),
            f"{week_value}.customers",
            allow_blank=True,
            integer=True,
        )

        explicit_previous = parse_optional_row_number(
            row,
            bindings.previous_customers,
            f"{week_value}.previous_customers",
            integer=True,
        )
        previous_customers = explicit_previous if explicit_previous is not None else previous_row_customers

        explicit_retained = parse_optional_row_number(
            row,
            bindings.retained_customers,
            f"{week_value}.retained_customers",
            integer=True,
        )

        retained_customers = explicit_retained
        if retained_customers is None and previous_customers is not None and customers is not None:
            retained_customers = customers if customers <= previous_customers else previous_customers
            if customers > previous_customers:
                warnings.append(
                    f"Week '{week_value}' had customers above the previous base. retention_rate used "
                    f"{decimal_to_storage(previous_customers)} retained customers."
                )

        if (
            explicit_retained is not None
            and previous_customers is not None
            and explicit_retained > previous_customers
        ):
            raise SkillError(
                f"Week '{week_value}' has retained_customers greater than previous_customers."
            )

        if revenue is None or losses is None or customers is None:
            if any(
                value_present(row.get(column))
                for column in (bindings.revenue, bindings.losses, bindings.customers)
            ):
                warnings.append(
                    f"Week '{week_value}' is missing at least one base metric. Calculated fields were left blank."
                )
            row[bindings.retention_rate] = ""
            row[bindings.loss_percentage] = ""
            row[bindings.margin] = ""
            previous_row_customers = customers
            continue

        if revenue == 0:
            warnings.append(
                f"Week '{week_value}' has revenue equal to zero. loss_percentage and margin were left blank."
            )
            loss_percentage = None
            margin = None
        else:
            loss_percentage = losses / revenue
            margin = (revenue - losses) / revenue

        retention_rate = None
        if previous_customers is None:
            warnings.append(
                f"Week '{week_value}' could not calculate retention_rate because previous_customers is missing."
            )
        elif previous_customers == 0:
            warnings.append(
                f"Week '{week_value}' could not calculate retention_rate because previous_customers is zero."
            )
        elif retained_customers is not None:
            retention_rate = retained_customers / previous_customers

        if bindings.previous_customers and previous_customers is not None and not value_present(row.get(bindings.previous_customers)):
            row[bindings.previous_customers] = previous_customers
        if bindings.retained_customers and retained_customers is not None and not value_present(row.get(bindings.retained_customers)):
            row[bindings.retained_customers] = retained_customers

        row[bindings.retention_rate] = round_ratio(retention_rate) if retention_rate is not None else ""
        row[bindings.loss_percentage] = round_ratio(loss_percentage) if loss_percentage is not None else ""
        row[bindings.margin] = round_ratio(margin) if margin is not None else ""
        previous_row_customers = customers

    return unique_warning_list(warnings)


def serialize_cell_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return decimal_to_storage(value)
    return str(value)


def write_csv_document(document: TableDocument, output_path: Path) -> None:
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=document.columns)
        writer.writeheader()
        for row in document.rows:
            writer.writerow({column: serialize_cell_value(row.get(column, "")) for column in document.columns})


def build_string_cell(reference: str, value: str, style: str | None) -> ET.Element:
    cell = ET.Element(qname("c"), {"r": reference})
    if style is not None:
        cell.set("s", style)
    cell.set("t", "inlineStr")
    inline_string = ET.SubElement(cell, qname("is"))
    text_node = ET.SubElement(inline_string, qname("t"))
    if value.startswith(" ") or value.endswith(" "):
        text_node.set(f"{{{XML_NS}}}space", "preserve")
    text_node.text = value
    return cell


def build_numeric_cell(reference: str, value: Decimal, style: str | None) -> ET.Element:
    cell = ET.Element(qname("c"), {"r": reference})
    if style is not None:
        cell.set("s", style)
    value_node = ET.SubElement(cell, qname("v"))
    value_node.text = decimal_to_storage(value)
    return cell


def build_worksheet_row(
    row_number: int,
    columns: list[str],
    row_data: dict[str, Any],
    row_attrs: dict[str, str],
    styles: dict[str, str | None],
    *,
    force_strings: bool = False,
) -> ET.Element:
    row = ET.Element(qname("row"), {"r": str(row_number), **row_attrs})
    for index, column in enumerate(columns, start=1):
        value = row_data.get(column, "")
        if not value_present(value):
            continue
        reference = f"{column_letter_from_index(index)}{row_number}"
        style = styles.get(column)
        if isinstance(value, Decimal):
            row.append(build_numeric_cell(reference, value, style))
            continue
        text = str(value)
        if not force_strings and numeric_column(column):
            decimal_value = parse_decimal(text, column, allow_blank=True)
            if decimal_value is not None:
                row.append(build_numeric_cell(reference, decimal_value, style))
                continue
        row.append(build_string_cell(reference, text, style))
    return row


def update_dimension(root: ET.Element, column_count: int, row_count: int) -> None:
    dimension = root.find("x:dimension", NS)
    last_ref = f"{column_letter_from_index(column_count)}{row_count}"
    if dimension is None:
        dimension = ET.Element(qname("dimension"))
        root.insert(0, dimension)
    dimension.set("ref", f"A1:{last_ref}")


def write_xlsx_document(document: TableDocument, output_path: Path) -> None:
    if document.xlsx_context is None:
        raise SkillError("Missing XLSX context for Excel output.")

    context = document.xlsx_context
    original_sheet_bytes = context.entries[context.sheet_path]
    worksheet_root = ET.fromstring(original_sheet_bytes)
    sheet_data = worksheet_root.find("x:sheetData", NS)
    if sheet_data is None:
        raise SkillError("The worksheet does not contain sheetData.")

    for child in list(sheet_data):
        sheet_data.remove(child)

    default_header_style = next((style for style in context.header_styles.values() if style is not None), None)
    default_data_style = next((style for style in context.data_styles.values() if style is not None), None)

    header_style_map = {
        column: context.header_styles.get(column, default_header_style) for column in document.columns
    }
    data_style_map = {
        column: context.data_styles.get(column, default_data_style) for column in document.columns
    }

    header_row_data = {column: column for column in document.columns}
    sheet_data.append(
        build_worksheet_row(
            1,
            document.columns,
            header_row_data,
            context.header_row_attrs,
            header_style_map,
            force_strings=True,
        )
    )

    for index, row in enumerate(document.rows, start=2):
        sheet_data.append(
            build_worksheet_row(
                index,
                document.columns,
                row,
                context.data_row_attrs,
                data_style_map,
            )
        )

    update_dimension(worksheet_root, len(document.columns), max(1, len(document.rows) + 1))
    updated_sheet_bytes = ET.tostring(worksheet_root, encoding="utf-8", xml_declaration=True)
    updated_sheet_bytes = inject_root_namespace_declarations(
        updated_sheet_bytes,
        extract_root_namespace_declarations(original_sheet_bytes),
    )

    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for info in context.archive_infos:
            data = updated_sheet_bytes if info.filename == context.sheet_path else context.entries[info.filename]
            archive.writestr(info, data)


def write_document(document: TableDocument, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if document.file_type == "csv":
        write_csv_document(document, output_path)
        return
    write_xlsx_document(document, output_path)


def persist_document(document: TableDocument, payload: Payload) -> tuple[Path, Path | None]:
    try:
        backup_path = build_backup_path(payload.file_path, payload.week)
        shutil.copyfile(payload.file_path, backup_path)

        temp_path = payload.file_path.with_name(
            f".{payload.file_path.stem}_{sanitize_week_for_filename(payload.week)}.tmp{payload.file_path.suffix}"
        )
        if temp_path.exists():
            temp_path.unlink()

        try:
            write_document(document, temp_path)
            temp_path.replace(payload.file_path)
        finally:
            if temp_path.exists():
                temp_path.unlink()

        return payload.file_path, backup_path
    except PermissionError as exc:
        raise SkillError(
            f"Permission denied while writing to {OUTPUT_DIR} or updating {payload.file_path}. "
            f"Approve writes inside actualizar-indicadores/output."
        ) from exc


def metric_value_from_row(row: dict[str, Any], column_name: str) -> Decimal | None:
    value = row.get(column_name)
    if isinstance(value, Decimal):
        return value
    return parse_decimal(value, column_name, allow_blank=True)


def build_summary(
    payload: Payload,
    document: TableDocument,
    bindings: ColumnBindings,
    action: str,
    before: dict[str, Any],
    after_row: dict[str, Any],
    output_path: Path,
    backup_path: Path | None,
    warnings: list[str],
) -> dict[str, Any]:
    tracked_columns: list[str] = [
        bindings.revenue,
        bindings.losses,
        bindings.customers,
    ]
    if bindings.previous_customers:
        tracked_columns.append(bindings.previous_customers)
    if bindings.retained_customers:
        tracked_columns.append(bindings.retained_customers)
    tracked_columns.extend([bindings.retention_rate, bindings.loss_percentage, bindings.margin])

    changed_fields: dict[str, dict[str, Any]] = {}
    for column in tracked_columns:
        before_value = serialize_cell_value(before.get(column, ""))
        after_value = serialize_cell_value(after_row.get(column, ""))
        if before_value != after_value:
            changed_fields[column] = {
                "before": before_value or None,
                "after": after_value or None,
            }

    return {
        "source_file": str(payload.file_path),
        "output_file": str(output_path),
        "backup_file": str(backup_path) if backup_path is not None else None,
        "sheet_name": document.sheet_name,
        "week": payload.week,
        "action": action,
        "changed_fields": changed_fields,
        "calculated_metrics": {
            "retention_rate": decimal_to_json(metric_value_from_row(after_row, bindings.retention_rate)),
            "loss_percentage": decimal_to_json(metric_value_from_row(after_row, bindings.loss_percentage)),
            "margin": decimal_to_json(metric_value_from_row(after_row, bindings.margin)),
        },
        "warnings": warnings,
    }


def save_summary(summary: dict[str, Any], summary_path: Path | None) -> None:
    if summary_path is None:
        return
    try:
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    except PermissionError as exc:
        raise SkillError(
            f"Permission denied while writing the summary file at {summary_path}. "
            f"Approve writes inside actualizar-indicadores/output or choose another summary path."
        ) from exc


def run(payload: Payload) -> dict[str, Any]:
    document = load_document(payload.file_path, payload.sheet_name)
    bindings = bind_columns(document, payload)
    action, before, row_index = upsert_target_row(document, payload, bindings)
    warnings = recalculate_metrics(document, bindings)
    output_path, backup_path = persist_document(document, payload)
    summary = build_summary(
        payload,
        document,
        bindings,
        action,
        before,
        document.rows[row_index],
        output_path,
        backup_path,
        warnings,
    )
    save_summary(summary, payload.summary_path)
    return summary


def main() -> int:
    try:
        args = parse_cli_args()
        payload = payload_from_args(args)
        summary = run(payload)
    except SkillError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"ERROR: Invalid JSON payload: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
