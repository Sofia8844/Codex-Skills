from __future__ import annotations

from copy import deepcopy
import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
import shutil
import sys
import textwrap
import unicodedata
import zipfile
import xml.etree.ElementTree as ET


P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
XML_NS = "http://www.w3.org/XML/1998/namespace"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"

NS = {"p": P_NS, "a": A_NS, "r": R_NS, "rel": REL_NS}
CT = {"ct": CT_NS}

ET.register_namespace("a", A_NS)
ET.register_namespace("p", P_NS)
ET.register_namespace("r", R_NS)

SCRIPT_PATH = Path(__file__).resolve()
SKILL_ROOT = SCRIPT_PATH.parent
REPO_ROOT = SCRIPT_PATH.parents[3]
OUTPUT_ROOT = REPO_ROOT / "output"
DEFAULT_TEMPLATE = SKILL_ROOT / "assets" / "plantillas" / "Industrias Ariova.pptx"
DEFAULT_OUTPUT = OUTPUT_ROOT / "propuesta-economica-final.pptx"
EMU_PER_PIXEL = 9525
EMU_PER_POINT = 12700
DEFAULT_CENTER_IMAGE_MAX_WIDTH_RATIO = 0.26
DEFAULT_CENTER_IMAGE_MAX_HEIGHT_RATIO = 0.18
DEFAULT_TEXT_INSET_EMU = 45720
AVERAGE_CHAR_WIDTH_RATIO = 0.52
MIN_CHARS_PER_LINE = 8
DEFAULT_FONT_SIZE_CENTIPOINTS = 1800
TEXT_STYLE_LIMITS = {
    "title": {"max_paragraphs": 1, "max_lines_per_paragraph": 4, "min_scale": 0.82},
    "subtitle": {"max_paragraphs": 2, "max_lines_per_paragraph": 4, "min_scale": 0.74},
    "bullets": {"max_paragraphs": 6, "max_lines_per_paragraph": 2, "min_scale": 0.76},
    "paragraph": {"max_paragraphs": 3, "max_lines_per_paragraph": 4, "min_scale": 0.74},
}
IMAGE_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
SLIDE_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide"
SLIDE_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.slide+xml"
IMAGE_CONTENT_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
}
PLACEHOLDERS = {
    "${skill_root}": str(SKILL_ROOT),
    "${repo_root}": str(REPO_ROOT),
    "${output_root}": str(OUTPUT_ROOT),
}
TEAM_SECTION_DEFAULT_SLIDE = 11
TEAM_CARDS_PER_SLIDE = 4
TEAM_DEFAULT_IMAGE_NAME = "Empleado Default"
TEAM_IMAGE_DIR_CANDIDATES = (
    SKILL_ROOT / "assets" / "Equipo",
    SKILL_ROOT / "assets" / "equipo",
)


@dataclass
class ImageTarget:
    kind: str
    element: ET.Element
    parent: ET.Element
    geometry: tuple[int, int, int, int]
    name: str
    has_text: bool


@dataclass
class TextShapeTarget:
    element: ET.Element
    geometry: tuple[int, int, int, int] | None


@dataclass
class TextShapePlan:
    target: TextShapeTarget
    replacement: list[str]
    shape_index: int
    style: str
    base_font_size: int


@dataclass
class TeamMember:
    name: str
    role: str
    image_path: Path | None = None


@dataclass
class TeamSectionSpec:
    members: list[TeamMember]
    template_slide: int
    title: str | None
    replace_title: bool
    image_dirs: list[Path]
    max_per_slide: int
    default_image_path: Path | None


@dataclass
class TeamCardSlot:
    slot_index: int
    container_group: ET.Element
    photo_group: ET.Element
    image_target: ImageTarget
    name_target: TextShapeTarget
    role_target: TextShapeTarget


def slide_number_from_path(path: str) -> int:
    match = re.search(r"slide(\d+)\.xml$", path)
    if not match:
        raise ValueError(f"Could not infer slide number from {path}")
    return int(match.group(1))


def sorted_slide_paths(zip_file: zipfile.ZipFile) -> list[str]:
    slide_paths = [
        name
        for name in zip_file.namelist()
        if name.startswith("ppt/slides/slide") and name.endswith(".xml")
    ]
    return sorted(slide_paths, key=slide_number_from_path)


def parse_int(value: object | None) -> int | None:
    if value is None:
        return None
    return int(value)


def parse_bool(value: object | None, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"true", "1", "yes", "y", "si", "sí"}:
            return True
        if normalized in {"false", "0", "no", "n"}:
            return False
    return bool(value)


def resolve_config_path(raw_path: str | None, spec_dir: Path) -> Path | None:
    if raw_path is None:
        return None

    expanded = raw_path.replace("${spec_dir}", str(spec_dir))
    for placeholder, value in PLACEHOLDERS.items():
        expanded = expanded.replace(placeholder, value)

    path = Path(expanded)
    if not path.is_absolute():
        path = spec_dir / path
    return path.resolve()


def path_within_output_root(path: Path) -> Path:
    candidate = path.resolve()
    output_root = OUTPUT_ROOT.resolve()
    try:
        candidate.relative_to(output_root)
        return candidate
    except ValueError:
        return (output_root / candidate.name).resolve()


def resolve_output_path(raw_path: str | None, spec_dir: Path, default_path: Path) -> Path:
    if raw_path is None:
        return default_path.resolve()

    expanded = raw_path.replace("${spec_dir}", str(spec_dir))
    for placeholder, value in PLACEHOLDERS.items():
        expanded = expanded.replace(placeholder, value)

    path = Path(expanded)
    if not path.is_absolute():
        path = OUTPUT_ROOT / path

    return path_within_output_root(path)


def resolve_output_path_list(raw_paths: list[object], spec_dir: Path) -> list[Path]:
    resolved_paths: list[Path] = []
    for raw_path in raw_paths:
        if not isinstance(raw_path, str):
            raise ValueError(f"extra_output_paths contains a non-string path: {raw_path!r}")
        resolved_paths.append(resolve_output_path(raw_path, spec_dir, DEFAULT_OUTPUT))
    return resolved_paths


def presentation_slide_size(presentation_xml: bytes) -> tuple[int, int]:
    root = ET.fromstring(presentation_xml)
    slide_size = root.find("p:sldSz", NS)
    if slide_size is None:
        raise ValueError("Presentation does not define slide dimensions")
    return int(slide_size.attrib["cx"]), int(slide_size.attrib["cy"])


def content_type_for_image_extension(extension: str) -> str:
    normalized = extension.lower()
    if normalized not in IMAGE_CONTENT_TYPES:
        raise ValueError(f"Unsupported image extension for PPTX insertion: {extension}")
    return IMAGE_CONTENT_TYPES[normalized]


def png_dimensions(data: bytes) -> tuple[int, int] | None:
    if len(data) < 24 or not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return None
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    return width, height


def gif_dimensions(data: bytes) -> tuple[int, int] | None:
    if len(data) < 10 or data[:6] not in {b"GIF87a", b"GIF89a"}:
        return None
    width = int.from_bytes(data[6:8], "little")
    height = int.from_bytes(data[8:10], "little")
    return width, height


def webp_dimensions(data: bytes) -> tuple[int, int] | None:
    if len(data) < 16 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return None

    chunk_header = data[12:16]
    chunk_data = data[20:]
    if chunk_header == b"VP8X" and len(chunk_data) >= 10:
        width = 1 + int.from_bytes(chunk_data[4:7], "little")
        height = 1 + int.from_bytes(chunk_data[7:10], "little")
        return width, height

    if chunk_header == b"VP8L" and len(chunk_data) >= 5 and chunk_data[0] == 0x2F:
        bits = int.from_bytes(chunk_data[1:5], "little")
        width = (bits & 0x3FFF) + 1
        height = ((bits >> 14) & 0x3FFF) + 1
        return width, height

    if chunk_header == b"VP8 " and len(chunk_data) >= 10 and chunk_data[3:6] == b"\x9d\x01\x2a":
        width = int.from_bytes(chunk_data[6:8], "little") & 0x3FFF
        height = int.from_bytes(chunk_data[8:10], "little") & 0x3FFF
        return width, height

    return None


def jpeg_dimensions(data: bytes) -> tuple[int, int] | None:
    if len(data) < 4 or data[:2] != b"\xff\xd8":
        return None

    index = 2
    while index + 1 < len(data):
        if data[index] != 0xFF:
            index += 1
            continue

        marker = data[index + 1]
        index += 2

        if marker in {0xD8, 0xD9}:
            continue

        if index + 2 > len(data):
            return None

        segment_length = int.from_bytes(data[index:index + 2], "big")
        if segment_length < 2 or index + segment_length > len(data):
            return None

        if marker in {
            0xC0,
            0xC1,
            0xC2,
            0xC3,
            0xC5,
            0xC6,
            0xC7,
            0xC9,
            0xCA,
            0xCB,
            0xCD,
            0xCE,
            0xCF,
        }:
            if segment_length < 7:
                return None
            height = int.from_bytes(data[index + 3:index + 5], "big")
            width = int.from_bytes(data[index + 5:index + 7], "big")
            return width, height

        index += segment_length

    return None


def image_pixel_dimensions(path: Path, data: bytes) -> tuple[int, int] | None:
    extension = path.suffix.lower()
    if extension == ".png":
        return png_dimensions(data)
    if extension in {".jpg", ".jpeg"}:
        return jpeg_dimensions(data)
    if extension == ".gif":
        return gif_dimensions(data)
    if extension == ".webp":
        return webp_dimensions(data)
    return None


def pixels_to_emu(pixels: int) -> int:
    return int(round(pixels * EMU_PER_PIXEL))


def emu_to_points(value: int) -> float:
    return value / EMU_PER_POINT


def image_native_emu_size(path: Path, data: bytes) -> tuple[int, int] | None:
    dimensions = image_pixel_dimensions(path, data)
    if dimensions is None:
        return None
    width_px, height_px = dimensions
    return pixels_to_emu(width_px), pixels_to_emu(height_px)


def fit_size_into_box(
    native_size: tuple[int, int] | None,
    box_width: int,
    box_height: int,
) -> tuple[int, int]:
    if native_size is None:
        return box_width, box_height

    native_width, native_height = native_size
    if native_width <= 0 or native_height <= 0:
        return box_width, box_height

    scale = min(box_width / native_width, box_height / native_height)
    return max(1, int(native_width * scale)), max(1, int(native_height * scale))


def parse_box(value: object) -> tuple[int, int, int, int]:
    if isinstance(value, list) and len(value) == 4:
        return tuple(int(item) for item in value)  # type: ignore[return-value]

    if isinstance(value, dict):
        return (
            int(value["x"]),
            int(value["y"]),
            int(value["cx"]),
            int(value["cy"]),
        )

    raise ValueError("Image box must be a list [x, y, cx, cy] or a dict with x/y/cx/cy")


def resolve_image_size(
    insertion: dict,
    native_size: tuple[int, int] | None,
    default_box: tuple[int, int],
) -> tuple[int, int]:
    cx = parse_int(insertion.get("cx"))
    cy = parse_int(insertion.get("cy"))
    max_width = parse_int(insertion.get("max_width"))
    max_height = parse_int(insertion.get("max_height"))

    if cx is not None and cy is not None:
        return cx, cy

    if native_size is not None:
        native_width, native_height = native_size
        if cx is not None:
            return cx, max(1, int(native_height * (cx / native_width)))
        if cy is not None:
            return max(1, int(native_width * (cy / native_height))), cy

    if max_width is None and max_height is None:
        max_width, max_height = default_box
    elif max_width is None:
        max_width = default_box[0]
    elif max_height is None:
        max_height = default_box[1]

    return fit_size_into_box(native_size, max_width, max_height)


def resolve_image_geometry(
    insertion: dict,
    slide_size: tuple[int, int],
    native_size: tuple[int, int] | None,
) -> tuple[int, int, int, int]:
    slide_width, slide_height = slide_size
    x = parse_int(insertion.get("x"))
    y = parse_int(insertion.get("y"))

    if x is not None or y is not None:
        size = resolve_image_size(
            insertion,
            native_size,
            (
                int(slide_width * DEFAULT_CENTER_IMAGE_MAX_WIDTH_RATIO),
                int(slide_height * DEFAULT_CENTER_IMAGE_MAX_HEIGHT_RATIO),
            ),
        )
        return x or 0, y or 0, size[0], size[1]

    if "box" in insertion:
        box_x, box_y, box_width, box_height = parse_box(insertion["box"])
        size = resolve_image_size(insertion, native_size, (box_width, box_height))
        return (
            box_x + max(0, (box_width - size[0]) // 2),
            box_y + max(0, (box_height - size[1]) // 2),
            size[0],
            size[1],
        )

    placement = insertion.get("placement", "center")
    default_box = (
        int(slide_width * DEFAULT_CENTER_IMAGE_MAX_WIDTH_RATIO),
        int(slide_height * DEFAULT_CENTER_IMAGE_MAX_HEIGHT_RATIO),
    )
    size = resolve_image_size(insertion, native_size, default_box)

    if placement == "center":
        return (
            max(0, (slide_width - size[0]) // 2),
            max(0, (slide_height - size[1]) // 2),
            size[0],
            size[1],
        )

    raise ValueError(f"Unsupported image placement: {placement!r}")


def parse_transform_geometry(xfrm: ET.Element | None) -> tuple[int, int, int, int] | None:
    if xfrm is None:
        return None

    off = xfrm.find("a:off", NS)
    ext = xfrm.find("a:ext", NS)
    if off is None or ext is None:
        return None

    return (
        int(off.attrib.get("x", "0")),
        int(off.attrib.get("y", "0")),
        int(ext.attrib.get("cx", "0")),
        int(ext.attrib.get("cy", "0")),
    )


def compose_group_transform(
    parent_transform: tuple[float, float, float, float],
    group: ET.Element,
) -> tuple[float, float, float, float]:
    group_xfrm = group.find("./p:grpSpPr/a:xfrm", NS)
    if group_xfrm is None:
        return parent_transform

    group_geometry = parse_transform_geometry(group_xfrm)
    if group_geometry is None:
        return parent_transform

    group_x, group_y, group_cx, group_cy = group_geometry
    child_offset = group_xfrm.find("a:chOff", NS)
    child_extent = group_xfrm.find("a:chExt", NS)

    child_x = int(child_offset.attrib.get("x", "0")) if child_offset is not None else 0
    child_y = int(child_offset.attrib.get("y", "0")) if child_offset is not None else 0
    child_cx = int(child_extent.attrib.get("cx", str(group_cx))) if child_extent is not None else group_cx
    child_cy = int(child_extent.attrib.get("cy", str(group_cy))) if child_extent is not None else group_cy

    if child_cx == 0:
        child_cx = group_cx or 1
    if child_cy == 0:
        child_cy = group_cy or 1

    group_scale_x = group_cx / child_cx
    group_scale_y = group_cy / child_cy

    parent_offset_x, parent_offset_y, parent_scale_x, parent_scale_y = parent_transform
    return (
        parent_offset_x + parent_scale_x * (group_x - child_x * group_scale_x),
        parent_offset_y + parent_scale_y * (group_y - child_y * group_scale_y),
        parent_scale_x * group_scale_x,
        parent_scale_y * group_scale_y,
    )


def apply_transform_to_geometry(
    geometry: tuple[int, int, int, int],
    transform: tuple[float, float, float, float],
) -> tuple[int, int, int, int]:
    x, y, cx, cy = geometry
    offset_x, offset_y, scale_x, scale_y = transform
    return (
        int(round(offset_x + scale_x * x)),
        int(round(offset_y + scale_y * y)),
        int(round(scale_x * cx)),
        int(round(scale_y * cy)),
    )


def shape_has_text_content(shape: ET.Element) -> bool:
    for paragraph in shape.findall("./p:txBody/a:p", NS):
        text = "".join((node.text or "") for node in paragraph.findall(".//a:t", NS)).strip()
        if text:
            return True
    return False


def collect_image_targets(
    parent: ET.Element,
    transform: tuple[float, float, float, float],
) -> list[ImageTarget]:
    targets: list[ImageTarget] = []

    for child in list(parent):
        if child.tag == f"{{{P_NS}}}grpSp":
            group_transform = compose_group_transform(transform, child)
            targets.extend(collect_image_targets(child, group_transform))
            continue

        if child.tag == f"{{{P_NS}}}sp":
            blip = child.find("./p:spPr/a:blipFill/a:blip", NS)
            geometry = parse_transform_geometry(child.find("./p:spPr/a:xfrm", NS))
            if geometry is None:
                continue

            non_visual = child.find("./p:nvSpPr/p:cNvPr", NS)
            targets.append(
                ImageTarget(
                    kind="shape_fill" if blip is not None else "shape",
                    element=child,
                    parent=parent,
                    geometry=apply_transform_to_geometry(geometry, transform),
                    name=non_visual.attrib.get("name", "") if non_visual is not None else "",
                    has_text=shape_has_text_content(child),
                )
            )
            continue

        if child.tag == f"{{{P_NS}}}pic":
            blip = child.find("./p:blipFill/a:blip", NS)
            if blip is None:
                continue

            geometry = parse_transform_geometry(child.find("./p:spPr/a:xfrm", NS))
            if geometry is None:
                continue

            non_visual = child.find("./p:nvPicPr/p:cNvPr", NS)
            targets.append(
                ImageTarget(
                    kind="picture",
                    element=child,
                    parent=parent,
                    geometry=apply_transform_to_geometry(geometry, transform),
                    name=non_visual.attrib.get("name", "") if non_visual is not None else "",
                    has_text=False,
                )
            )

    return targets


def geometry_intersects_slide(
    geometry: tuple[int, int, int, int],
    slide_size: tuple[int, int],
) -> bool:
    x, y, cx, cy = geometry
    slide_width, slide_height = slide_size
    return x + cx > 0 and y + cy > 0 and x < slide_width and y < slide_height


def normalized_anchor_name(raw_anchor: str) -> str:
    return raw_anchor.strip().lower().replace("_", "-")


def geometry_area(geometry: tuple[int, int, int, int]) -> int:
    _, _, cx, cy = geometry
    return cx * cy


def geometry_center(geometry: tuple[int, int, int, int]) -> tuple[float, float]:
    x, y, cx, cy = geometry
    return x + cx / 2, y + cy / 2


def geometry_contains_point(
    geometry: tuple[int, int, int, int],
    point: tuple[float, float],
) -> bool:
    x, y, cx, cy = geometry
    point_x, point_y = point
    return x <= point_x <= x + cx and y <= point_y <= y + cy


def geometry_is_circle_like(
    geometry: tuple[int, int, int, int],
    tolerance: float = 0.08,
) -> bool:
    _, _, cx, cy = geometry
    if cx <= 0 or cy <= 0:
        return False
    largest = max(cx, cy)
    smallest = min(cx, cy)
    return (largest - smallest) / largest <= tolerance


def select_largest_circle_target(
    targets: list[ImageTarget],
    slide_size: tuple[int, int],
    anchor: str,
) -> ImageTarget | None:
    if normalized_anchor_name(anchor) != "center":
        return None

    visible_targets = [target for target in targets if geometry_intersects_slide(target.geometry, slide_size)]
    candidates = visible_targets or targets
    anchor_target = anchor_point(anchor, slide_size)
    circle_candidates = [
        target
        for target in candidates
        if not target.has_text
        and geometry_is_circle_like(target.geometry)
        and geometry_contains_point(target.geometry, anchor_target)
    ]
    if not circle_candidates:
        return None

    def circle_score(target: ImageTarget) -> tuple[int, int, float]:
        return (
            geometry_area(target.geometry),
            min(target.geometry[2], target.geometry[3]),
            -distance_to_anchor(target.geometry, anchor_target),
        )

    return max(circle_candidates, key=circle_score, default=None)


def anchor_point(anchor: str, slide_size: tuple[int, int]) -> tuple[float, float]:
    slide_width, slide_height = slide_size
    normalized = normalized_anchor_name(anchor)

    if normalized == "center":
        return slide_width / 2, slide_height / 2
    if normalized == "bottom-center":
        return slide_width / 2, float(slide_height)

    raise ValueError(f"Unsupported target_existing anchor: {anchor!r}")


def distance_to_anchor(
    geometry: tuple[int, int, int, int],
    target_point: tuple[float, float],
) -> float:
    center_x, center_y = geometry_center(geometry)
    target_x, target_y = target_point
    return (center_x - target_x) ** 2 + (center_y - target_y) ** 2


def select_image_target(
    targets: list[ImageTarget],
    slide_size: tuple[int, int],
    anchor: str,
) -> ImageTarget | None:
    if not targets:
        return None

    visible_targets = [target for target in targets if geometry_intersects_slide(target.geometry, slide_size)]
    candidates = visible_targets or targets
    circle_target = select_largest_circle_target(candidates, slide_size, anchor)
    if circle_target is not None:
        return circle_target

    image_candidates = [target for target in candidates if target.kind in {"shape_fill", "picture"}]
    ranked_candidates = image_candidates or candidates
    anchor_target = anchor_point(anchor, slide_size)
    return min(
        ranked_candidates,
        key=lambda target: distance_to_anchor(target.geometry, anchor_target),
        default=None,
    )


def remove_image_target(target: ImageTarget) -> None:
    if target.kind == "picture":
        target.parent.remove(target.element)
        return

    if target.kind == "shape_fill":
        shape_properties = target.element.find("./p:spPr", NS)
        blip_fill = target.element.find("./p:spPr/a:blipFill", NS)
        if shape_properties is not None and blip_fill is not None:
            shape_properties.remove(blip_fill)


def next_shape_id(root: ET.Element) -> int:
    max_id = 0
    for non_visual in root.findall(".//p:cNvPr", NS):
        max_id = max(max_id, int(non_visual.attrib.get("id", "0")))
    return max_id + 1


def next_relationship_id(rels_root: ET.Element) -> str:
    max_id = 0
    for relationship in rels_root.findall("rel:Relationship", NS):
        rel_id = relationship.attrib.get("Id", "")
        match = re.fullmatch(r"rId(\d+)", rel_id)
        if match:
            max_id = max(max_id, int(match.group(1)))
    return f"rId{max_id + 1}"


def build_picture_element(
    shape_id: int,
    name: str,
    relationship_id: str,
    geometry: tuple[int, int, int, int],
) -> ET.Element:
    x, y, cx, cy = geometry

    picture = ET.Element(f"{{{P_NS}}}pic")
    non_visual = ET.SubElement(picture, f"{{{P_NS}}}nvPicPr")

    c_nv_pr = ET.SubElement(non_visual, f"{{{P_NS}}}cNvPr")
    c_nv_pr.set("id", str(shape_id))
    c_nv_pr.set("name", name)

    c_nv_pic_pr = ET.SubElement(non_visual, f"{{{P_NS}}}cNvPicPr")
    pic_locks = ET.SubElement(c_nv_pic_pr, f"{{{A_NS}}}picLocks")
    pic_locks.set("noChangeAspect", "1")
    ET.SubElement(non_visual, f"{{{P_NS}}}nvPr")

    blip_fill = ET.SubElement(picture, f"{{{P_NS}}}blipFill")
    blip = ET.SubElement(blip_fill, f"{{{A_NS}}}blip")
    blip.set(f"{{{R_NS}}}embed", relationship_id)
    stretch = ET.SubElement(blip_fill, f"{{{A_NS}}}stretch")
    ET.SubElement(stretch, f"{{{A_NS}}}fillRect")

    shape_properties = ET.SubElement(picture, f"{{{P_NS}}}spPr")
    transform = ET.SubElement(shape_properties, f"{{{A_NS}}}xfrm")
    offset = ET.SubElement(transform, f"{{{A_NS}}}off")
    offset.set("x", str(x))
    offset.set("y", str(y))
    extent = ET.SubElement(transform, f"{{{A_NS}}}ext")
    extent.set("cx", str(cx))
    extent.set("cy", str(cy))
    geometry_el = ET.SubElement(shape_properties, f"{{{A_NS}}}prstGeom")
    geometry_el.set("prst", "rect")
    ET.SubElement(geometry_el, f"{{{A_NS}}}avLst")

    return picture


def insert_picture_into_root(
    root: ET.Element,
    relationship_id: str,
    geometry: tuple[int, int, int, int],
    picture_name: str,
) -> ET.Element:
    shape_tree = root.find("./p:cSld/p:spTree", NS)
    if shape_tree is None:
        raise ValueError("Slide does not contain a shape tree")

    picture = build_picture_element(
        shape_id=next_shape_id(root),
        name=picture_name,
        relationship_id=relationship_id,
        geometry=geometry,
    )

    ext_list = shape_tree.find("p:extLst", NS)
    if ext_list is None:
        shape_tree.append(picture)
    else:
        shape_tree.insert(list(shape_tree).index(ext_list), picture)

    return root


def insert_picture_into_slide(
    slide_xml: bytes,
    relationship_id: str,
    geometry: tuple[int, int, int, int],
    picture_name: str,
) -> bytes:
    root = ET.fromstring(slide_xml)
    insert_picture_into_root(
        root,
        relationship_id=relationship_id,
        geometry=geometry,
        picture_name=picture_name,
    )
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def resolve_target_geometry(
    slide_root: ET.Element,
    image_entry: dict,
    slide_number: int,
    slide_size: tuple[int, int],
    warnings: list[str],
) -> tuple[int, int, int, int] | None:
    target_anchor = image_entry.get("target_existing")
    if target_anchor is None:
        return None

    if not isinstance(target_anchor, str):
        raise ValueError(f"slide_images[{slide_number}] target_existing must be a string anchor")

    shape_tree = slide_root.find("./p:cSld/p:spTree", NS)
    if shape_tree is None:
        if image_entry.get("missing_ok", False):
            warnings.append(f"Slide {slide_number}: no shape tree found; skipping image.")
            return None
        raise ValueError(f"Slide {slide_number}: slide does not contain a shape tree.")

    targets = collect_image_targets(shape_tree, (0.0, 0.0, 1.0, 1.0))
    target = select_image_target(targets, slide_size, target_anchor)
    if target is None:
        if image_entry.get("missing_ok", False):
            warnings.append(
                f"Slide {slide_number}: no existing image matched anchor {target_anchor!r}; skipping image."
            )
            return None
        raise ValueError(
            f"Slide {slide_number}: no existing image matched anchor {target_anchor!r}."
        )

    if image_entry.get("remove_target_image", True) and target.kind in {"shape_fill", "picture"}:
        remove_image_target(target)

    return target.geometry


def create_relationships_root() -> ET.Element:
    return ET.Element(f"{{{REL_NS}}}Relationships")


def upsert_image_relationship(
    rels_xml: bytes | None,
    media_target: str,
) -> tuple[bytes, str]:
    rels_root = ET.fromstring(rels_xml) if rels_xml is not None else create_relationships_root()
    relationship_id = next_relationship_id(rels_root)
    relationship = ET.SubElement(rels_root, f"{{{REL_NS}}}Relationship")
    relationship.set("Id", relationship_id)
    relationship.set("Type", IMAGE_REL_TYPE)
    relationship.set("Target", media_target)
    return ET.tostring(rels_root, encoding="utf-8", xml_declaration=True), relationship_id


def ensure_image_content_types(
    content_types_xml: bytes,
    extensions: set[str],
) -> bytes:
    root = ET.fromstring(content_types_xml)
    existing_defaults = {
        element.attrib.get("Extension", "").lower()
        for element in root.findall("ct:Default", CT)
    }

    for extension in sorted(extensions):
        normalized = extension.lstrip(".").lower()
        if normalized in existing_defaults:
            continue
        default_el = ET.SubElement(root, f"{{{CT_NS}}}Default")
        default_el.set("Extension", normalized)
        default_el.set("ContentType", content_type_for_image_extension(extension))

    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def next_media_path(existing_paths: set[str], extension: str) -> str:
    index = 1
    while True:
        candidate = f"ppt/media/image{index}{extension.lower()}"
        if candidate not in existing_paths:
            existing_paths.add(candidate)
            return candidate
        index += 1


def normalize_slide_images(
    raw_slide_images: object,
    spec_dir: Path,
) -> dict[int, list[dict]]:
    if raw_slide_images in (None, {}):
        return {}

    if not isinstance(raw_slide_images, dict):
        raise ValueError("slide_images must be a mapping of slide numbers to image definitions")

    normalized: dict[int, list[dict]] = {}
    for slide_number_raw, raw_value in raw_slide_images.items():
        slide_number = int(slide_number_raw)
        entries = raw_value if isinstance(raw_value, list) else [raw_value]
        normalized_entries: list[dict] = []

        for entry in entries:
            if isinstance(entry, str):
                image_path = resolve_config_path(entry, spec_dir)
                normalized_entry = {"image_path": image_path, "placement": "center"}
            elif isinstance(entry, dict):
                image_path_value = entry.get("image_path") or entry.get("path")
                if not isinstance(image_path_value, str):
                    raise ValueError(
                        f"slide_images[{slide_number}] requires image_path/path for each entry"
                    )
                image_path = resolve_config_path(image_path_value, spec_dir)
                normalized_entry = {**entry, "image_path": image_path}
            else:
                raise ValueError(
                    f"slide_images[{slide_number}] contains an unsupported entry: {entry!r}"
                )

            if image_path is None or not image_path.exists():
                raise FileNotFoundError(f"Image not found for slide {slide_number}: {image_path}")

            normalized_entries.append(normalized_entry)

        normalized[slide_number] = normalized_entries

    return normalized


def unique_paths(paths: list[Path]) -> list[Path]:
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in paths:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(resolved)
    return unique


def resolve_directory_list(raw_value: object, spec_dir: Path) -> list[Path]:
    if raw_value in (None, "", []):
        return []

    raw_paths = raw_value if isinstance(raw_value, list) else [raw_value]
    resolved: list[Path] = []
    for raw_path in raw_paths:
        if not isinstance(raw_path, str):
            raise ValueError(f"Expected a string directory path, got {raw_path!r}")
        resolved_path = resolve_config_path(raw_path, spec_dir)
        if resolved_path is not None:
            resolved.append(resolved_path)
    return unique_paths(resolved)


def default_team_image_dirs(spec_dir: Path) -> list[Path]:
    return unique_paths(
        [
            spec_dir / "Equipo",
            spec_dir / "equipo",
            *TEAM_IMAGE_DIR_CANDIDATES,
        ]
    )


def normalize_match_key(text: str) -> str:
    without_accents = "".join(
        char
        for char in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(char)
    )
    return re.sub(r"[^a-z0-9]+", " ", without_accents.casefold()).strip()


def normalize_match_tokens(text: str) -> list[str]:
    return [token for token in normalize_match_key(text).split() if token]


def team_image_match_score(person_name: str, candidate_name: str) -> tuple[int, int, int, int, int] | None:
    person_key = normalize_match_key(person_name)
    candidate_key = normalize_match_key(candidate_name)
    if not person_key or not candidate_key:
        return None

    person_tokens = normalize_match_tokens(person_name)
    candidate_tokens = normalize_match_tokens(candidate_name)
    matched_tokens = sum(1 for token in person_tokens if token in candidate_tokens)
    ordered_prefix = candidate_tokens[: len(person_tokens)] == person_tokens
    contains_full_name = person_key in candidate_key or candidate_key in person_key

    if matched_tokens == 0 and not contains_full_name:
        return None

    exact_match = person_key == candidate_key
    coverage = matched_tokens / max(1, len(person_tokens))
    return (
        3 if exact_match else 2 if contains_full_name else 1,
        1 if ordered_prefix else 0,
        int(round(coverage * 100)),
        -abs(len(candidate_tokens) - len(person_tokens)),
        -abs(len(candidate_key) - len(person_key)),
    )


def local_image_candidates(search_dirs: list[Path]) -> list[Path]:
    candidates: list[Path] = []
    for directory in search_dirs:
        if not directory.exists() or not directory.is_dir():
            continue
        for path in sorted(directory.iterdir()):
            if not path.is_file():
                continue
            if path.suffix.lower() not in IMAGE_CONTENT_TYPES:
                continue
            candidates.append(path.resolve())
    return unique_paths(candidates)


def find_team_member_image(person_name: str, search_dirs: list[Path]) -> Path | None:
    best_match: Path | None = None
    best_score: tuple[int, int, int, int, int] | None = None

    for candidate in local_image_candidates(search_dirs):
        score = team_image_match_score(person_name, candidate.stem)
        if score is None:
            continue
        if best_score is None or score > best_score:
            best_match = candidate
            best_score = score

    return best_match


def find_team_default_image(search_dirs: list[Path]) -> Path | None:
    target_key = normalize_match_key(TEAM_DEFAULT_IMAGE_NAME)
    best_match: Path | None = None

    for candidate in local_image_candidates(search_dirs):
        candidate_key = normalize_match_key(candidate.stem)
        if candidate_key == target_key:
            return candidate
        if target_key in candidate_key or candidate_key in target_key:
            best_match = candidate

    return best_match


def normalize_team_member(raw_member: object, member_index: int, spec_dir: Path) -> TeamMember:
    if isinstance(raw_member, str):
        name = raw_member
        role = ""
        image_path = None
    elif isinstance(raw_member, list) and len(raw_member) <= 2:
        name = scalar_to_text(raw_member[0]) if raw_member else ""
        role = scalar_to_text(raw_member[1]) if len(raw_member) > 1 else ""
        image_path = None
    elif isinstance(raw_member, dict):
        name = scalar_to_text(
            raw_member.get("name")
            or raw_member.get("person")
            or raw_member.get("full_name")
            or raw_member.get("nombre")
        )
        role = scalar_to_text(
            raw_member.get("role")
            or raw_member.get("cargo")
            or raw_member.get("title")
            or raw_member.get("rol")
        )
        image_path_value = raw_member.get("image_path") or raw_member.get("path")
        image_path = None
        if image_path_value is not None:
            if not isinstance(image_path_value, str):
                raise ValueError(
                    f"team_section.members[{member_index}] image_path/path must be a string"
                )
            image_path = resolve_config_path(image_path_value, spec_dir)
    else:
        raise ValueError(f"Unsupported team member definition: {raw_member!r}")

    normalized_name = clean_replacement_text(name)
    normalized_role = clean_replacement_text(role)
    if not normalized_name:
        raise ValueError(f"team_section.members[{member_index}] requires a non-empty name")

    if image_path is not None and not image_path.exists():
        raise FileNotFoundError(
            f"Image not found for team_section.members[{member_index}]: {image_path}"
        )

    return TeamMember(
        name=normalized_name,
        role=normalized_role,
        image_path=image_path.resolve() if image_path is not None else None,
    )


def normalize_team_section(spec: dict, spec_dir: Path) -> TeamSectionSpec | None:
    raw_team_section = spec.get("team_section")
    if raw_team_section is None and spec.get("team_members") is None:
        return None

    if raw_team_section is None:
        raw_team_section = {
            "members": spec.get("team_members"),
            "template_slide": spec.get("team_slide"),
            "title": spec.get("team_title"),
            "images_dir": spec.get("team_images_dir") or spec.get("team_images_dirs"),
        }

    if isinstance(raw_team_section, list):
        raw_team_section = {"members": raw_team_section}

    if not isinstance(raw_team_section, dict):
        raise ValueError("team_section must be an object or a list of members")

    raw_members = (
        raw_team_section.get("members")
        or raw_team_section.get("people")
        or raw_team_section.get("team")
        or spec.get("team_members")
    )
    if raw_members in (None, []):
        return None
    if not isinstance(raw_members, list):
        raise ValueError("team_section.members must be a list")

    image_dirs = resolve_directory_list(
        raw_team_section.get("images_dir")
        or raw_team_section.get("image_dir")
        or spec.get("team_images_dir")
        or spec.get("team_images_dirs"),
        spec_dir,
    )
    if not image_dirs:
        image_dirs = default_team_image_dirs(spec_dir)

    template_slide_raw = (
        raw_team_section.get("template_slide")
        or raw_team_section.get("slide")
        or raw_team_section.get("slide_number")
        or spec.get("team_slide")
        or TEAM_SECTION_DEFAULT_SLIDE
    )
    max_per_slide_raw = raw_team_section.get("max_per_slide", TEAM_CARDS_PER_SLIDE)
    max_per_slide = min(TEAM_CARDS_PER_SLIDE, max(1, int(max_per_slide_raw)))
    default_image_raw = (
        raw_team_section.get("default_image_path")
        or raw_team_section.get("default_image")
        or spec.get("team_default_image_path")
    )
    default_image_path = None
    if default_image_raw is not None:
        if not isinstance(default_image_raw, str):
            raise ValueError("team_section.default_image_path must be a string path")
        default_image_path = resolve_config_path(default_image_raw, spec_dir)
        if default_image_path is None or not default_image_path.exists():
            raise FileNotFoundError(f"Default team image not found: {default_image_path}")

    members = [
        normalize_team_member(member, member_index, spec_dir)
        for member_index, member in enumerate(raw_members, start=1)
    ]
    if not members:
        return None

    title = raw_team_section.get("title") or spec.get("team_title")
    normalized_title = clean_replacement_text(str(title)) if title is not None else None
    replace_title_raw = None
    if "replace_title" in raw_team_section:
        replace_title_raw = raw_team_section.get("replace_title")
    elif "override_title" in raw_team_section:
        replace_title_raw = raw_team_section.get("override_title")
    else:
        replace_title_raw = spec.get("team_replace_title")
    replace_title = parse_bool(replace_title_raw, default=False)
    return TeamSectionSpec(
        members=members,
        template_slide=int(template_slide_raw),
        title=normalized_title or None,
        replace_title=replace_title,
        image_dirs=image_dirs,
        max_per_slide=max_per_slide,
        default_image_path=default_image_path.resolve() if default_image_path is not None else None,
    )


def geometry_enclosing_box(
    geometries: list[tuple[int, int, int, int]],
) -> tuple[int, int, int, int] | None:
    if not geometries:
        return None

    min_x = min(geometry[0] for geometry in geometries)
    min_y = min(geometry[1] for geometry in geometries)
    max_x = max(geometry[0] + geometry[2] for geometry in geometries)
    max_y = max(geometry[1] + geometry[3] for geometry in geometries)
    return min_x, min_y, max_x - min_x, max_y - min_y


def group_bounding_geometry(group: ET.Element) -> tuple[int, int, int, int] | None:
    transform = compose_group_transform((0.0, 0.0, 1.0, 1.0), group)
    targets = collect_image_targets(group, transform)
    return geometry_enclosing_box([target.geometry for target in targets])


def slide_path_for_number(slide_number: int) -> str:
    return f"ppt/slides/slide{slide_number}.xml"


def slide_relationships_path_for_number(slide_number: int) -> str:
    return f"ppt/slides/_rels/slide{slide_number}.xml.rels"


def entry_bytes(
    path: str,
    source_zip: zipfile.ZipFile,
    source_paths: set[str],
    modified_entries: dict[str, bytes],
    new_entries: dict[str, bytes],
) -> bytes | None:
    if path in modified_entries:
        return modified_entries[path]
    if path in new_entries:
        return new_entries[path]
    if path in source_paths:
        return source_zip.read(path)
    return None


def next_slide_number(existing_paths: set[str]) -> int:
    slide_numbers = [
        slide_number_from_path(path)
        for path in existing_paths
        if path.startswith("ppt/slides/slide") and path.endswith(".xml")
    ]
    return (max(slide_numbers) if slide_numbers else 0) + 1


def current_presentation_slide_order(
    presentation_xml: bytes,
    rels_xml: bytes,
) -> list[int]:
    presentation_root = ET.fromstring(presentation_xml)
    rels_root = ET.fromstring(rels_xml)

    slide_number_by_rel: dict[str, int] = {}
    for relationship in rels_root.findall("rel:Relationship", NS):
        rel_type = relationship.attrib.get("Type", "")
        if not rel_type.endswith("/slide"):
            continue
        target = relationship.attrib.get("Target", "")
        slide_number_by_rel[relationship.attrib["Id"]] = slide_number_from_path(target)

    slide_id_list = presentation_root.find("p:sldIdLst", NS)
    if slide_id_list is None:
        raise ValueError("Presentation does not contain a slide list")

    order: list[int] = []
    for slide_id in slide_id_list:
        rel_id = slide_id.attrib.get(f"{{{R_NS}}}id")
        if rel_id and rel_id in slide_number_by_rel:
            order.append(slide_number_by_rel[rel_id])
    return order


def next_presentation_slide_id(presentation_root: ET.Element) -> int:
    max_id = 255
    slide_id_list = presentation_root.find("p:sldIdLst", NS)
    if slide_id_list is None:
        raise ValueError("Presentation does not contain a slide list")
    for slide_id in slide_id_list:
        max_id = max(max_id, int(slide_id.attrib.get("id", "255")))
    return max_id + 1


def add_slide_relationship(
    rels_xml: bytes,
    slide_number: int,
) -> tuple[bytes, str]:
    rels_root = ET.fromstring(rels_xml)
    relationship_id = next_relationship_id(rels_root)
    relationship = ET.SubElement(rels_root, f"{{{REL_NS}}}Relationship")
    relationship.set("Id", relationship_id)
    relationship.set("Type", SLIDE_REL_TYPE)
    relationship.set("Target", f"slides/slide{slide_number}.xml")
    return ET.tostring(rels_root, encoding="utf-8", xml_declaration=True), relationship_id


def append_slide_reference(
    presentation_xml: bytes,
    relationship_id: str,
) -> bytes:
    presentation_root = ET.fromstring(presentation_xml)
    slide_id_list = presentation_root.find("p:sldIdLst", NS)
    if slide_id_list is None:
        raise ValueError("Presentation does not contain a slide list")

    slide_id = ET.Element(f"{{{P_NS}}}sldId")
    slide_id.set("id", str(next_presentation_slide_id(presentation_root)))
    slide_id.set(f"{{{R_NS}}}id", relationship_id)
    slide_id_list.append(slide_id)
    return ET.tostring(presentation_root, encoding="utf-8", xml_declaration=True)


def ensure_slide_content_type_overrides(
    content_types_xml: bytes,
    slide_numbers: list[int],
) -> bytes:
    root = ET.fromstring(content_types_xml)
    existing_part_names = {
        element.attrib.get("PartName", "")
        for element in root.findall("ct:Override", CT)
    }

    for slide_number in sorted(set(slide_numbers)):
        part_name = f"/ppt/slides/slide{slide_number}.xml"
        if part_name in existing_part_names:
            continue
        override = ET.SubElement(root, f"{{{CT_NS}}}Override")
        override.set("PartName", part_name)
        override.set("ContentType", SLIDE_CONTENT_TYPE)

    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def detect_team_card_slots(
    root: ET.Element,
    slide_size: tuple[int, int],
) -> tuple[list[TeamCardSlot], TextShapeTarget | None]:
    shape_tree = root.find("./p:cSld/p:spTree", NS)
    if shape_tree is None:
        raise ValueError("Slide does not contain a shape tree")

    slide_width, slide_height = slide_size
    photo_groups: list[tuple[ET.Element, tuple[int, int, int, int], ImageTarget]] = []
    container_groups: list[tuple[ET.Element, tuple[int, int, int, int]]] = []

    for child in list(shape_tree):
        if child.tag != f"{{{P_NS}}}grpSp":
            continue

        transform = compose_group_transform((0.0, 0.0, 1.0, 1.0), child)
        targets = collect_image_targets(child, transform)
        geometries = [target.geometry for target in targets if geometry_intersects_slide(target.geometry, slide_size)]
        group_geometry = geometry_enclosing_box(geometries)
        if group_geometry is None:
            continue

        _, group_y, group_cx, group_cy = group_geometry
        has_replaceable_image = any(target.kind in {"shape_fill", "picture"} for target in targets)
        if group_y <= int(slide_height * 0.22) or group_cx >= int(slide_width * 0.3):
            continue

        if has_replaceable_image and group_cy <= int(slide_height * 0.32):
            image_target = next(
                (
                    target
                    for target in targets
                    if target.kind in {"shape_fill", "picture"}
                    and geometry_intersects_slide(target.geometry, slide_size)
                ),
                None,
            )
            if image_target is not None:
                photo_groups.append((child, group_geometry, image_target))
            continue

        if not has_replaceable_image and group_cy >= int(slide_height * 0.24):
            container_groups.append((child, group_geometry))

    if not photo_groups or not container_groups:
        raise ValueError("Could not detect team card groups in the slide template")

    visible_text_targets = [
        target
        for target in text_shape_targets_from_slide(root)
        if target.geometry is not None and geometry_intersects_slide(target.geometry, slide_size)
    ]
    card_text_targets = [
        target
        for target in visible_text_targets
        if target.geometry is not None and target.geometry[1] >= int(slide_height * 0.45)
    ]
    if len(card_text_targets) < 2:
        raise ValueError("Could not detect team card text placeholders in the slide template")

    sorted_photos = sorted(photo_groups, key=lambda item: item[1][0])[:TEAM_CARDS_PER_SLIDE]
    remaining_containers = sorted(container_groups, key=lambda item: item[1][0])
    slot_assignments: dict[int, list[TextShapeTarget]] = {
        slot_index: [] for slot_index in range(len(sorted_photos))
    }
    slot_centers = [geometry_center(item[1]) for item in sorted_photos]

    for target in card_text_targets:
        assert target.geometry is not None
        target_center = geometry_center(target.geometry)
        slot_index = min(
            range(len(slot_centers)),
            key=lambda index: abs(slot_centers[index][0] - target_center[0]),
        )
        slot_assignments[slot_index].append(target)

    slots: list[TeamCardSlot] = []
    used_text_element_ids: set[int] = set()
    for slot_index, (photo_group, photo_geometry, image_target) in enumerate(sorted_photos, start=1):
        photo_center = geometry_center(photo_geometry)
        container_position = min(
            range(len(remaining_containers)),
            key=lambda index: abs(geometry_center(remaining_containers[index][1])[0] - photo_center[0]),
        )
        container_group, _ = remaining_containers.pop(container_position)

        slot_text_targets = sorted(
            slot_assignments[slot_index - 1],
            key=lambda target: (
                target.geometry[1] if target.geometry is not None else 10**9,
                target.geometry[0] if target.geometry is not None else 10**9,
            ),
        )
        if len(slot_text_targets) < 2:
            raise ValueError(f"Could not detect both text placeholders for team slot {slot_index}")

        name_target, role_target = slot_text_targets[:2]
        used_text_element_ids.add(id(name_target.element))
        used_text_element_ids.add(id(role_target.element))
        slots.append(
            TeamCardSlot(
                slot_index=slot_index,
                container_group=container_group,
                photo_group=photo_group,
                image_target=image_target,
                name_target=name_target,
                role_target=role_target,
            )
        )

    remaining_text_targets = [
        target for target in visible_text_targets if id(target.element) not in used_text_element_ids
    ]
    title_target = min(
        remaining_text_targets,
        key=lambda target: (
            target.geometry[1] if target.geometry is not None else 10**9,
            -(target.geometry[2] * target.geometry[3]) if target.geometry is not None else 0,
        ),
        default=None,
    )
    return slots, title_target


def fit_paragraphs_to_shape_exact(
    shape: ET.Element,
    geometry: tuple[int, int, int, int] | None,
    replacement: list[str],
    preferred_font_scale: float = 1.0,
    min_font_scale: float | None = None,
) -> tuple[list[str], float, bool]:
    cleaned_paragraphs = [clean_replacement_text(text) for text in replacement]
    style = detect_text_shape_style(shape, geometry)
    limits = TEXT_STYLE_LIMITS[style]
    max_paragraphs = min(len(shape_addressable_paragraphs(shape)), int(limits["max_paragraphs"]))
    max_lines_per_paragraph = int(limits["max_lines_per_paragraph"])
    min_scale = min_font_scale if min_font_scale is not None else float(limits["min_scale"])
    start_scale = min(preferred_font_scale, 1.0)

    if style == "title" and len(cleaned_paragraphs) > 1:
        cleaned_paragraphs = [" - ".join(text for text in cleaned_paragraphs if text).strip()]

    cleaned_paragraphs = cleaned_paragraphs[:max_paragraphs]
    addressable = shape_addressable_paragraphs(shape)
    effective_max_lines = effective_max_lines_for_replacement(
        shape,
        geometry,
        addressable,
        len(cleaned_paragraphs),
        style,
        max_lines_per_paragraph,
        start_scale,
    )

    candidate = list(cleaned_paragraphs)
    font_scale = start_scale
    while font_scale >= min_scale:
        if shape_text_fits(shape, geometry, candidate, font_scale, effective_max_lines):
            return candidate, font_scale, True
        font_scale = round(font_scale - 0.04, 2)

    return candidate, min_scale, shape_text_fits(
        shape,
        geometry,
        candidate,
        min_scale,
        effective_max_lines,
    )


def apply_uniform_text_plans(
    plans: list[TextShapePlan],
    slide_number: int,
    warnings: list[str],
    allow_summary: bool = True,
) -> None:
    if not plans:
        return

    common_font_size = min(plan.base_font_size for plan in plans)
    chosen_results: dict[int, tuple[list[str], float]] | None = None
    chosen_warnings: list[str] = []
    last_results: dict[int, tuple[list[str], float]] | None = None
    last_warnings: list[str] = []

    for group_factor in group_scale_factors(plans, common_font_size):
        candidate_results: dict[int, tuple[list[str], float]] = {}
        candidate_warnings: list[str] = []
        all_fit = True

        for plan in plans:
            normalized_scale = common_font_size / max(1, plan.base_font_size)
            target_scale = min(1.0, normalized_scale * group_factor)
            if allow_summary:
                fitted_replacement, font_scale, fits = fit_paragraphs_to_shape(
                    plan.target.element,
                    plan.target.geometry,
                    plan.replacement,
                    slide_number,
                    plan.shape_index,
                    candidate_warnings,
                    preferred_font_scale=target_scale,
                    min_font_scale=target_scale,
                )
            else:
                fitted_replacement, font_scale, fits = fit_paragraphs_to_shape_exact(
                    plan.target.element,
                    plan.target.geometry,
                    plan.replacement,
                    preferred_font_scale=target_scale,
                    min_font_scale=target_scale,
                )
            candidate_results[plan.shape_index] = (fitted_replacement, font_scale)
            if not fits:
                all_fit = False

        last_results = candidate_results
        last_warnings = candidate_warnings
        if all_fit:
            chosen_results = candidate_results
            chosen_warnings = candidate_warnings
            break

    if chosen_results is None:
        chosen_results = last_results or {}
        chosen_warnings = last_warnings
        warnings.append(
            f"Slide {slide_number}: kept uniform typography for the team section and preserved full text."
        )

    warnings.extend(chosen_warnings)
    for plan in plans:
        fitted_replacement, font_scale = chosen_results[plan.shape_index]
        replace_shape_paragraphs(plan.target.element, fitted_replacement, font_scale)


def ensure_media_entry(
    image_path: Path,
    reserved_paths: set[str],
    media_targets_by_source: dict[Path, str],
    new_entries: dict[str, bytes],
    used_image_extensions: set[str],
) -> tuple[str, bytes]:
    resolved_path = image_path.resolve()
    media_target = media_targets_by_source.get(resolved_path)
    if media_target is None:
        media_target = next_media_path(reserved_paths, resolved_path.suffix)
        media_targets_by_source[resolved_path] = media_target
        new_entries[media_target] = resolved_path.read_bytes()
        used_image_extensions.add(resolved_path.suffix.lower())
    return media_target, new_entries[media_target]


def replace_image_target_embed(target: ImageTarget, relationship_id: str) -> bool:
    if target.kind == "picture":
        blip = target.element.find("./p:blipFill/a:blip", NS)
    elif target.kind == "shape_fill":
        blip = target.element.find("./p:spPr/a:blipFill/a:blip", NS)
    else:
        blip = None

    if blip is None:
        return False

    blip.set(f"{{{R_NS}}}embed", relationship_id)
    return True


def populate_team_slide(
    slide_xml: bytes,
    rels_xml: bytes | None,
    slide_number: int,
    slide_size: tuple[int, int],
    members: list[TeamMember],
    team_title: str | None,
    replace_team_title: bool,
    warnings: list[str],
    reserved_paths: set[str],
    media_targets_by_source: dict[Path, str],
    new_entries: dict[str, bytes],
    used_image_extensions: set[str],
) -> tuple[bytes, bytes | None]:
    root = ET.fromstring(slide_xml)
    shape_tree = root.find("./p:cSld/p:spTree", NS)
    if shape_tree is None:
        raise ValueError(f"Slide {slide_number}: slide does not contain a shape tree.")

    slots, title_target = detect_team_card_slots(root, slide_size)
    if not slots:
        raise ValueError(f"Slide {slide_number}: could not detect reusable team slots.")
    if len(members) > len(slots):
        raise ValueError(
            f"Slide {slide_number}: received {len(members)} team members for {len(slots)} slots."
        )

    name_plans: list[TextShapePlan] = []
    role_plans: list[TextShapePlan] = []
    for slot in slots[: len(members)]:
        member = members[slot.slot_index - 1]
        name_plans.append(
            TextShapePlan(
                target=slot.name_target,
                replacement=[member.name],
                shape_index=slot.slot_index * 10 + 1,
                style=detect_text_shape_style(slot.name_target.element, slot.name_target.geometry),
                base_font_size=shape_primary_font_size_centipoints(slot.name_target.element),
            )
        )
        role_plans.append(
            TextShapePlan(
                target=slot.role_target,
                replacement=[member.role],
                shape_index=slot.slot_index * 10 + 2,
                style=detect_text_shape_style(slot.role_target.element, slot.role_target.geometry),
                base_font_size=shape_primary_font_size_centipoints(slot.role_target.element),
            )
        )

        image_path = member.image_path
        if image_path is None:
            raise ValueError(
                f"Slide {slide_number}: team member '{member.name}' did not resolve to an image."
            )

        media_target, _ = ensure_media_entry(
            image_path,
            reserved_paths,
            media_targets_by_source,
            new_entries,
            used_image_extensions,
        )
        rels_xml, relationship_id = upsert_image_relationship(
            rels_xml,
            f"../media/{Path(media_target).name}",
        )
        if not replace_image_target_embed(slot.image_target, relationship_id):
            remove_image_target(slot.image_target)
            insert_picture_into_root(
                root,
                relationship_id=relationship_id,
                geometry=slot.image_target.geometry,
                picture_name=f"Team Photo {slide_number}-{slot.slot_index}",
            )

    # Preserve the template's title by default so cloned team slides stay visually
    # identical to the protected corporate section unless the caller opts in.
    if team_title and replace_team_title and title_target is not None:
        apply_uniform_text_plans(
            [
                TextShapePlan(
                    target=title_target,
                    replacement=[team_title],
                    shape_index=1,
                    style=detect_text_shape_style(title_target.element, title_target.geometry),
                    base_font_size=shape_primary_font_size_centipoints(title_target.element),
                )
            ],
            slide_number,
            warnings,
            allow_summary=False,
        )

    apply_uniform_text_plans(name_plans, slide_number, warnings, allow_summary=False)
    apply_uniform_text_plans(role_plans, slide_number, warnings, allow_summary=False)

    unused_slots = slots[len(members):]
    for slot in unused_slots:
        for element in (
            slot.container_group,
            slot.photo_group,
            slot.name_target.element,
            slot.role_target.element,
        ):
            if element in list(shape_tree):
                shape_tree.remove(element)

    return ET.tostring(root, encoding="utf-8", xml_declaration=True), rels_xml


def expand_slide_order_for_generated_slides(
    base_order: list[int],
    template_slide: int,
    generated_slide_numbers: list[int],
    warnings: list[str],
) -> list[int]:
    if not generated_slide_numbers:
        return base_order

    generated_tail = set(generated_slide_numbers)
    expanded_order: list[int] = []
    inserted = False
    for slide_number in base_order:
        if slide_number == template_slide and not inserted:
            expanded_order.append(slide_number)
            expanded_order.extend(generated_slide_numbers)
            inserted = True
            continue
        if slide_number in generated_tail:
            continue
        expanded_order.append(slide_number)

    if not inserted:
        warnings.append(
            f"Team section template slide {template_slide} was not present in the requested order; appended team slides at the end."
        )
        expanded_order.extend(generated_slide_numbers)

    return expanded_order


def paragraph_text_content(paragraph: ET.Element) -> str:
    return "".join((node.text or "") for node in paragraph.findall(".//a:t", NS)).strip()


def paragraph_has_visible_text(paragraph: ET.Element) -> bool:
    return bool(paragraph_text_content(paragraph))


def shape_paragraph_elements(shape: ET.Element) -> list[ET.Element]:
    return shape.findall("./p:txBody/a:p", NS)


def shape_addressable_paragraphs(shape: ET.Element) -> list[ET.Element]:
    paragraphs = shape_paragraph_elements(shape)
    if not paragraphs:
        return []
    non_empty = [paragraph for paragraph in paragraphs if paragraph_has_visible_text(paragraph)]
    return non_empty or paragraphs


def shape_paragraph_texts(shape: ET.Element) -> list[str]:
    texts: list[str] = []
    for paragraph in shape_addressable_paragraphs(shape):
        text = paragraph_text_content(paragraph)
        if text:
            texts.append(text)
    return texts


def collect_text_shape_targets(
    parent: ET.Element,
    transform: tuple[float, float, float, float],
) -> list[TextShapeTarget]:
    targets: list[TextShapeTarget] = []

    for child in list(parent):
        if child.tag == f"{{{P_NS}}}grpSp":
            group_transform = compose_group_transform(transform, child)
            targets.extend(collect_text_shape_targets(child, group_transform))
            continue

        if child.tag != f"{{{P_NS}}}sp":
            continue

        if not shape_paragraph_texts(child):
            continue

        geometry = parse_transform_geometry(child.find("./p:spPr/a:xfrm", NS))
        absolute_geometry = apply_transform_to_geometry(geometry, transform) if geometry is not None else None
        targets.append(TextShapeTarget(element=child, geometry=absolute_geometry))

    return targets


def text_shape_targets_from_slide(root: ET.Element) -> list[TextShapeTarget]:
    shape_tree = root.find("./p:cSld/p:spTree", NS)
    if shape_tree is None:
        return []
    return collect_text_shape_targets(shape_tree, (0.0, 0.0, 1.0, 1.0))


def text_shapes_from_slide(root: ET.Element) -> list[ET.Element]:
    return [target.element for target in text_shape_targets_from_slide(root)]


def scalar_to_text(value: object) -> str:
    return "" if value is None else str(value)


def is_scalar_replacement(value: object) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def normalize_paragraph_group(value: object) -> list[str]:
    if is_scalar_replacement(value):
        return [scalar_to_text(value)]

    if isinstance(value, list):
        paragraphs: list[str] = []
        for item in value:
            if isinstance(item, list):
                paragraphs.extend(normalize_paragraph_group(item))
            elif is_scalar_replacement(item):
                paragraphs.append(scalar_to_text(item))
            else:
                raise ValueError(f"Unsupported paragraph value: {item!r}")
        return paragraphs

    raise ValueError(f"Unsupported paragraph group: {value!r}")


def normalize_slide_replacements(
    replacements: object,
    expected_shapes: int,
    slide_number: int,
) -> list[list[str]]:
    if is_scalar_replacement(replacements):
        if expected_shapes != 1:
            raise ValueError(
                f"Slide {slide_number} received a scalar replacement, but the template expects "
                f"{expected_shapes} text shapes."
            )
        return [[scalar_to_text(replacements)]]

    if not isinstance(replacements, list):
        raise ValueError(
            f"Slide {slide_number} replacements must be a list, got {type(replacements).__name__}."
        )

    if expected_shapes == 1:
        return [normalize_paragraph_group(replacements)]

    if len(replacements) == expected_shapes:
        return [normalize_paragraph_group(item) for item in replacements]

    if all(is_scalar_replacement(item) for item in replacements):
        raise ValueError(
            f"Slide {slide_number} got a flat list with {len(replacements)} items, but the template "
            f"expects {expected_shapes} text shapes. If this JSON came from PowerShell, keep the "
            f"outer array per shape and the inner array per paragraph."
        )

    raise ValueError(
        f"Slide {slide_number} expected {expected_shapes} text shapes but received "
        f"{len(replacements)} replacement groups."
    )


def clean_replacement_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return "\n".join(line.strip() for line in normalized.split("\n")).strip()


def paragraph_has_bullet(paragraph: ET.Element) -> bool:
    paragraph_props = paragraph.find("a:pPr", NS)
    if paragraph_props is None:
        return False
    return (
        paragraph_props.find("a:buChar", NS) is not None
        or paragraph_props.find("a:buAutoNum", NS) is not None
        or paragraph_props.find("a:buBlip", NS) is not None
    )


def paragraph_font_size_centipoints(paragraph: ET.Element) -> int:
    run_props = paragraph.find("a:r/a:rPr", NS)
    end_props = paragraph.find("a:endParaRPr", NS)
    for node in (run_props, end_props):
        if node is not None and node.attrib.get("sz"):
            return int(node.attrib["sz"])
    return DEFAULT_FONT_SIZE_CENTIPOINTS


def paragraph_line_height_points(paragraph: ET.Element, font_scale: float = 1.0) -> float:
    base_font_points = paragraph_font_size_centipoints(paragraph) / 100.0
    paragraph_props = paragraph.find("a:pPr", NS)
    if paragraph_props is not None:
        line_spacing = paragraph_props.find("a:lnSpc", NS)
        if line_spacing is not None:
            spacing_points = line_spacing.find("a:spcPts", NS)
            if spacing_points is not None and spacing_points.attrib.get("val"):
                return max(1.0, (int(spacing_points.attrib["val"]) / 100.0) * font_scale)
            spacing_percent = line_spacing.find("a:spcPct", NS)
            if spacing_percent is not None and spacing_percent.attrib.get("val"):
                ratio = int(spacing_percent.attrib["val"]) / 100000
                return max(1.0, base_font_points * ratio * font_scale)
    return max(1.0, base_font_points * 1.2 * font_scale)


def paragraph_left_indent_points(paragraph: ET.Element) -> float:
    paragraph_props = paragraph.find("a:pPr", NS)
    if paragraph_props is None:
        return 0.0
    margin_left = int(paragraph_props.attrib.get("marL", "0"))
    return emu_to_points(max(0, margin_left))


def shape_content_box_points(
    shape: ET.Element,
    geometry: tuple[int, int, int, int] | None,
) -> tuple[float, float]:
    if geometry is None:
        paragraph_count = max(1, len(shape_paragraph_elements(shape)))
        return 260.0, max(60.0, paragraph_count * 28.0)

    _, _, cx, cy = geometry
    body_props = shape.find("./p:txBody/a:bodyPr", NS)
    left_inset = int(body_props.attrib.get("lIns", str(DEFAULT_TEXT_INSET_EMU))) if body_props is not None else DEFAULT_TEXT_INSET_EMU
    right_inset = int(body_props.attrib.get("rIns", str(DEFAULT_TEXT_INSET_EMU))) if body_props is not None else DEFAULT_TEXT_INSET_EMU
    top_inset = int(body_props.attrib.get("tIns", str(DEFAULT_TEXT_INSET_EMU))) if body_props is not None else DEFAULT_TEXT_INSET_EMU
    bottom_inset = int(body_props.attrib.get("bIns", str(DEFAULT_TEXT_INSET_EMU))) if body_props is not None else DEFAULT_TEXT_INSET_EMU

    usable_width = max(1, cx - left_inset - right_inset - DEFAULT_TEXT_INSET_EMU)
    usable_height = max(1, cy - top_inset - bottom_inset - DEFAULT_TEXT_INSET_EMU)
    return emu_to_points(usable_width), emu_to_points(usable_height)


def detect_text_shape_style(shape: ET.Element, geometry: tuple[int, int, int, int] | None) -> str:
    paragraphs = shape_addressable_paragraphs(shape)
    if not paragraphs:
        return "paragraph"

    font_points = max(paragraph_font_size_centipoints(paragraph) / 100.0 for paragraph in paragraphs)
    bullet_count = sum(1 for paragraph in paragraphs if paragraph_has_bullet(paragraph))
    _, usable_height_points = shape_content_box_points(shape, geometry)

    if len(paragraphs) == 1 and font_points >= 34:
        return "title"
    if len(paragraphs) <= 2 and bullet_count == 0 and font_points >= 18 and usable_height_points <= 120:
        return "subtitle"
    if bullet_count > 0 or len(paragraphs) > 1:
        return "bullets"
    return "paragraph"


def shape_primary_font_size_centipoints(shape: ET.Element) -> int:
    paragraphs = shape_addressable_paragraphs(shape)
    if not paragraphs:
        return DEFAULT_FONT_SIZE_CENTIPOINTS
    return max(paragraph_font_size_centipoints(paragraph) for paragraph in paragraphs)


def title_plan_priority(plan: TextShapePlan) -> tuple[int, int, int, int]:
    if plan.target.geometry is None:
        return (10**9, -plan.base_font_size, 0, plan.shape_index)
    x, y, cx, cy = plan.target.geometry
    return (y, -plan.base_font_size, -(cx * cy), x)


def primary_title_shape_index(plans: list[TextShapePlan]) -> int | None:
    title_plans = [plan for plan in plans if plan.style == "title"]
    if not title_plans:
        return None
    return min(title_plans, key=title_plan_priority).shape_index


def typography_group_key(plan: TextShapePlan, primary_title_index: int | None) -> str:
    if plan.style != "title":
        return plan.style
    if primary_title_index == plan.shape_index:
        return f"title-primary:{plan.shape_index}"
    return f"title-secondary:{plan.shape_index}"


def estimate_wrapped_line_count(text: str, chars_per_line: int) -> int:
    if not text:
        return 1

    total_lines = 0
    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line:
            total_lines += 1
            continue
        wrapped = textwrap.wrap(
            line,
            width=max(MIN_CHARS_PER_LINE, chars_per_line),
            break_long_words=True,
            break_on_hyphens=False,
        )
        total_lines += max(1, len(wrapped))
    return max(1, total_lines)


def paragraph_char_capacity(
    shape: ET.Element,
    paragraph: ET.Element,
    geometry: tuple[int, int, int, int] | None,
    font_scale: float,
    max_lines: int,
) -> int:
    content_width_points, _ = shape_content_box_points(shape, geometry)
    font_points = max(8.0, (paragraph_font_size_centipoints(paragraph) / 100.0) * font_scale)
    available_width = max(24.0, content_width_points - paragraph_left_indent_points(paragraph))
    chars_per_line = max(
        MIN_CHARS_PER_LINE,
        int(available_width / max(1.0, font_points * AVERAGE_CHAR_WIDTH_RATIO)),
    )
    if paragraph_has_bullet(paragraph):
        chars_per_line = max(MIN_CHARS_PER_LINE, chars_per_line - 3)
    return chars_per_line * max(1, max_lines)


SUMMARY_REPLACEMENTS = (
    (re.compile(r"\bpor ciento\b", re.IGNORECASE), "%"),
    (re.compile(r"\s+/\s+"), "/"),
    (re.compile(r"\s{2,}"), " "),
)

SUMMARY_CONNECTOR_PATTERNS = (
    re.compile(r"\s+con\b", re.IGNORECASE),
    re.compile(r"\s+para\b", re.IGNORECASE),
    re.compile(r"\s+mediante\b", re.IGNORECASE),
    re.compile(r"\s+incluyendo\b", re.IGNORECASE),
    re.compile(r"\s+durante\b", re.IGNORECASE),
    re.compile(r"\s+seg[uú]n\b", re.IGNORECASE),
    re.compile(r"\s+previa\b", re.IGNORECASE),
    re.compile(r"\s+bajo\b", re.IGNORECASE),
    re.compile(r"\s+usando\b", re.IGNORECASE),
    re.compile(r"\s+through\b", re.IGNORECASE),
    re.compile(r"\s+with\b", re.IGNORECASE),
    re.compile(r"\s+including\b", re.IGNORECASE),
    re.compile(r"\s+using\b", re.IGNORECASE),
    re.compile(r"\s+for\b", re.IGNORECASE),
)

SUMMARY_PARTICIPLE_PATTERNS = (
    re.compile(
        r"\s+(?:ajustad[oa]s?|aplicables?|alinead[oa]s?|orientad[oa]s?|"
        r"definid[oa]s?|basad[oa]s?|destinad[oa]s?|relacionad[oa]s?)\s+"
        r"(?:a|al|para|con|en|seg[uú]n)\b",
        re.IGNORECASE,
    ),
)

PAYMENT_STAGE_PATTERN = re.compile(r"^(?P<percent>\d+%)\s+(?P<body>.+)$", re.IGNORECASE)
SUMMARY_BODY_SKIP_WORDS = {
    "de",
    "del",
    "el",
    "la",
    "los",
    "las",
    "un",
    "una",
    "unos",
    "unas",
}
BULLET_MIN_WORDS = 10
BULLET_MAX_WORDS = 18
BULLET_TARGET_WORDS = 10
BULLET_MIN_FALLBACK_WORDS = 6
BULLET_EXPANSION_SUFFIXES = (
    "del proyecto",
    "segun el alcance definido",
    "para la ejecucion propuesta",
)
INFINITIVE_TO_NOUN = {
    "acompanar": "Acompanamiento",
    "acompañar": "Acompanamiento",
    "asegurar": "Aseguramiento",
    "configurar": "Configuracion",
    "definir": "Definicion",
    "diagnosticar": "Diagnostico",
    "disenar": "Diseno",
    "diseñar": "Diseno",
    "fortalecer": "Fortalecimiento",
    "gestionar": "Gestion",
    "habilitar": "Habilitacion",
    "implementar": "Implementacion",
    "integrar": "Integracion",
    "mejorar": "Mejora",
    "modernizar": "Modernizacion",
    "monitorear": "Monitoreo",
    "optimizar": "Optimizacion",
}

TRAILING_INCOMPLETE_PATTERN = re.compile(
    r"(?:\s+(?:y|e|o|u|con|para|de|del|la|el|los|las|en|por|al|a|seg[uú]n|"
    r"mediante|incluyendo|durante|with|for|to|of|and|or))+$",
    re.IGNORECASE,
)


def apply_summary_replacements(text: str) -> str:
    updated = text
    for pattern, replacement in SUMMARY_REPLACEMENTS:
        updated = pattern.sub(replacement, updated)
    return clean_replacement_text(updated)


def finalize_summary_candidate(text: str) -> str:
    candidate = clean_replacement_text(text)
    previous = None
    while candidate and candidate != previous:
        previous = candidate
        candidate = candidate.rstrip(" ,;:-")
        candidate = TRAILING_INCOMPLETE_PATTERN.sub("", candidate).strip()
    return candidate.rstrip(" ,;:-")


def is_meaningful_summary(text: str) -> bool:
    return len(text.split()) >= 2


def word_count(text: str) -> int:
    return len(re.findall(r"[\w%$+-]+", text, re.UNICODE))


def capitalize_sentence(text: str) -> str:
    if not text:
        return text
    return text[0].upper() + text[1:]


def bullet_word_score(text: str) -> tuple[int, int, int]:
    words = word_count(text)
    in_range = BULLET_MIN_WORDS <= words <= BULLET_MAX_WORDS
    short_gap = max(0, BULLET_MIN_WORDS - words)
    long_gap = max(0, words - BULLET_MAX_WORDS)
    distance_to_target = abs(BULLET_TARGET_WORDS - words)
    return (
        1 if in_range else 0,
        -(short_gap + long_gap),
        -distance_to_target,
    )


def best_bullet_candidate(candidates: list[str], max_chars: int) -> str | None:
    fitting = [
        capitalize_sentence(candidate)
        for candidate in unique_summary_candidates(candidates)
        if len(candidate) <= max_chars and is_meaningful_summary(candidate)
    ]
    if not fitting:
        return None
    return max(
        fitting,
        key=lambda candidate: (
            bullet_word_score(candidate),
            len(candidate),
        ),
    )


def professionalize_infinitive_lead(text: str) -> str:
    words = text.split()
    if len(words) < 2:
        return text

    mapped = INFINITIVE_TO_NOUN.get(words[0].lower())
    if mapped is None:
        return text

    remainder = " ".join(words[1:]).strip()
    lowered = remainder.lower()
    if lowered.startswith("el "):
        return f"{mapped} del {remainder[3:]}"
    if lowered.startswith("la "):
        return f"{mapped} de la {remainder[3:]}"
    if lowered.startswith("los "):
        return f"{mapped} de los {remainder[4:]}"
    if lowered.startswith("las "):
        return f"{mapped} de las {remainder[4:]}"
    return f"{mapped} de {remainder}"


def professional_bullet_variants(text: str) -> list[str]:
    base = finalize_summary_candidate(text)
    if not base:
        return []

    variants = [base]
    lowered = base.lower()
    transformed = professionalize_infinitive_lead(base)
    if transformed != base:
        variants.append(transformed)
    if lowered.startswith("seguimiento semanal") and "del proyecto" not in lowered:
        variants.append(re.sub(r"^seguimiento semanal", "Seguimiento semanal del proyecto", base, count=1, flags=re.IGNORECASE))
    if lowered.startswith("soporte inicial") and "del servicio" not in lowered:
        variants.append(re.sub(r"^soporte inicial", "Soporte inicial del servicio", base, count=1, flags=re.IGNORECASE))
    return unique_summary_candidates(variants)


def unique_summary_candidates(candidates: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for candidate in candidates:
        finalized = finalize_summary_candidate(candidate)
        if not finalized or finalized in seen:
            continue
        seen.add(finalized)
        unique.append(finalized)
    return unique


def money_or_metric_tail(text: str) -> bool:
    return bool(re.search(r"[$€£]|\bCOP\b|\bUSD\b|\bEUR\b|\b\d+[%]?\b", text, re.IGNORECASE))


def ordered_word_window_sizes(min_words: int, max_words: int, target_words: int) -> list[int]:
    return sorted(
        range(min_words, max_words + 1),
        key=lambda size: (abs(target_words - size), abs(BULLET_TARGET_WORDS - size), -size),
    )


def bullet_word_window_candidates(
    text: str,
    min_words: int = BULLET_MIN_WORDS,
    max_words: int = BULLET_MAX_WORDS,
) -> list[str]:
    words = text.split()
    if len(words) < min_words:
        return []

    candidates: list[str] = []
    for size in ordered_word_window_sizes(min_words, min(max_words, len(words)), BULLET_TARGET_WORDS):
        candidate = finalize_summary_candidate(" ".join(words[:size]))
        if candidate and is_meaningful_summary(candidate):
            candidates.append(candidate)
    return candidates


def expand_short_bullet_candidates(text: str, max_chars: int) -> list[str]:
    base = finalize_summary_candidate(text)
    if not base:
        return []

    candidates: list[str] = []
    current = base
    for suffix in BULLET_EXPANSION_SUFFIXES:
        if word_count(current) >= BULLET_MIN_WORDS:
            break
        expanded = finalize_summary_candidate(f"{current} {suffix}")
        if len(expanded) > max_chars:
            continue
        current = expanded
        candidates.append(current)
    return candidates


def candidate_from_colon(text: str, max_chars: int, content_style: str = "generic") -> list[str]:
    if ":" not in text:
        return []

    head, tail = text.split(":", 1)
    head = finalize_summary_candidate(head)
    tail = finalize_summary_candidate(tail)
    if not head or not tail or not money_or_metric_tail(tail):
        return []

    available_for_head = max(8, max_chars - len(tail) - 2)
    head_summary = summarize_text_to_limit(head, available_for_head, content_style=content_style)
    combined = finalize_summary_candidate(f"{head_summary}: {tail}")
    return [combined]


def comma_summary_candidates(text: str) -> list[str]:
    segments = [finalize_summary_candidate(segment) for segment in re.split(r",\s*", text) if segment.strip()]
    segments = [segment for segment in segments if segment]
    if len(segments) <= 1:
        return []

    candidates: list[str] = []
    candidates.append(segments[0])
    if len(segments) >= 2:
        second = segments[1]
        if second.lower().startswith(("y ", "e ", "and ")):
            candidates.append(f"{segments[0]} {second}")
        else:
            candidates.append(f"{segments[0]} y {second}")
    return candidates


def payment_stage_summary_candidates(text: str, max_chars: int) -> list[str]:
    match = PAYMENT_STAGE_PATTERN.match(text.strip())
    if match is None:
        return []

    percent = match.group("percent")
    body = clean_replacement_text(match.group("body"))
    body_words = [word for word in body.split() if word.strip()]
    if not body_words:
        return []

    explicit_candidates: list[str] = []
    normalized_body = body.lower()
    if normalized_body.startswith("al inicio"):
        explicit_candidates.extend(
            [
                f"Pago inicial del {percent} con arranque formal y alcance validado",
                f"Pago inicial del {percent} con alcance validado y arranque formal",
            ]
        )
    if "implementacion" in normalized_body:
        explicit_candidates.extend(
            [
                f"Pago del {percent} con avance de implementacion y control semanal",
                f"Pago del {percent} con implementacion activa y control semanal",
            ]
        )
    if "entrega" in normalized_body:
        explicit_candidates.extend(
            [
                f"Pago del {percent} por entrega validada y cierre tecnico final",
                f"Pago del {percent} por entrega validada y cierre tecnico formal",
            ]
        )
    if normalized_body.startswith("al cierre") or "documentacion" in normalized_body or "aceptacion" in normalized_body:
        explicit_candidates.extend(
            [
                f"Pago final del {percent} con documentos y aceptacion del servicio",
                f"Pago final del {percent} con cierre formal y aceptacion del servicio",
            ]
        )

    selected: list[str] = []
    for word in body_words:
        normalized = re.sub(r"[^\w%+-]", "", word, flags=re.UNICODE).lower()
        if normalized in SUMMARY_BODY_SKIP_WORDS and selected:
            continue
        selected.append(word)
        if len(selected) >= 3:
            break

    generic_candidates: list[str] = []
    if selected:
        generic_candidates.append(f"Pago del {percent} {' '.join(selected)}")

    expanded_candidates: list[str] = []
    for candidate in explicit_candidates + generic_candidates:
        expanded_candidates.extend(expand_short_bullet_candidates(candidate, max_chars))

    return unique_summary_candidates(explicit_candidates + generic_candidates + expanded_candidates)


def connector_summary_candidates(text: str) -> list[str]:
    candidates: list[str] = []
    for pattern in SUMMARY_CONNECTOR_PATTERNS + SUMMARY_PARTICIPLE_PATTERNS:
        for match in pattern.finditer(text):
            prefix = finalize_summary_candidate(text[: match.start()])
            if is_meaningful_summary(prefix):
                candidates.append(prefix)
    return candidates


def sentence_summary_candidates(text: str) -> list[str]:
    pieces = [piece.strip() for piece in re.split(r"(?<=[.!?;])\s+", text) if piece.strip()]
    candidates: list[str] = []
    if pieces:
        candidates.append(pieces[0].rstrip(".;"))
    return candidates


def fallback_phrase_summary(text: str, max_chars: int) -> str:
    words = text.split()
    if not words:
        return ""

    best = ""
    for index in range(1, len(words) + 1):
        candidate = finalize_summary_candidate(" ".join(words[:index]))
        if not candidate:
            continue
        if len(candidate) <= max_chars:
            best = candidate
        else:
            break

    if best and is_meaningful_summary(best):
        return best

    for boundary_match in re.finditer(r"[,:;]", text):
        candidate = finalize_summary_candidate(text[: boundary_match.start()])
        if candidate and len(candidate) <= max_chars and is_meaningful_summary(candidate):
            best = candidate

    return best or finalize_summary_candidate(words[0])


def fallback_bullet_summary(text: str, max_chars: int) -> str:
    candidates: list[str] = []
    for variant in professional_bullet_variants(text):
        candidates.extend(bullet_word_window_candidates(variant, min_words=BULLET_MIN_FALLBACK_WORDS, max_words=BULLET_MAX_WORDS))
        candidates.extend(expand_short_bullet_candidates(variant, max_chars))

    best_candidate = best_bullet_candidate(candidates, max_chars)
    if best_candidate is not None:
        return best_candidate

    fallback = fallback_phrase_summary(text, max_chars)
    return capitalize_sentence(fallback)


def summarize_text_to_limit(text: str, max_chars: int, content_style: str = "generic") -> str:
    cleaned = apply_summary_replacements(text)
    if max_chars <= 0:
        return ""

    if content_style != "bullets" and len(cleaned) <= max_chars:
        return cleaned

    if (
        content_style == "bullets"
        and len(cleaned) <= max_chars
        and BULLET_MIN_WORDS <= word_count(cleaned) <= BULLET_MAX_WORDS
    ):
        return capitalize_sentence(cleaned)

    without_parentheses = finalize_summary_candidate(re.sub(r"\s*\([^)]{8,}\)", "", cleaned).strip())
    candidates = [cleaned]
    if without_parentheses and without_parentheses != cleaned:
        candidates.append(without_parentheses)

    source_text = without_parentheses or cleaned
    if content_style == "bullets":
        candidates.extend(candidate_from_colon(source_text, max_chars, content_style=content_style))
        candidates.extend(payment_stage_summary_candidates(source_text, max_chars))
        for variant in professional_bullet_variants(source_text):
            candidates.append(variant)
            candidates.extend(sentence_summary_candidates(variant))
            candidates.extend(comma_summary_candidates(variant))
            candidates.extend(bullet_word_window_candidates(variant))
            candidates.extend(expand_short_bullet_candidates(variant, max_chars))

        best_candidate = best_bullet_candidate(candidates, max_chars)
        if best_candidate is not None:
            return best_candidate

        return fallback_bullet_summary(source_text, max_chars)

    candidates.extend(candidate_from_colon(source_text, max_chars, content_style=content_style))
    candidates.extend(payment_stage_summary_candidates(source_text, max_chars))
    candidates.extend(sentence_summary_candidates(source_text))
    candidates.extend(comma_summary_candidates(source_text))
    candidates.extend(connector_summary_candidates(source_text))

    for candidate in unique_summary_candidates(candidates):
        if len(candidate) <= max_chars and is_meaningful_summary(candidate):
            return candidate

    fallback = fallback_phrase_summary(source_text, max_chars)
    if fallback and len(fallback) <= max_chars:
        return fallback

    single_word_candidates = [
        finalize_summary_candidate(word)
        for word in re.split(r"\s+", source_text)
        if word.strip()
    ]
    fitting_words = [
        candidate
        for candidate in unique_summary_candidates(single_word_candidates)
        if len(candidate) <= max_chars
    ]
    if fitting_words:
        return max(fitting_words, key=len)

    return finalize_summary_candidate(source_text)


def estimate_shape_text_height_points(
    shape: ET.Element,
    geometry: tuple[int, int, int, int] | None,
    paragraphs_by_index: dict[int, str],
    font_scale: float,
) -> float:
    total = 0.0
    for index, paragraph in enumerate(shape_paragraph_elements(shape)):
        text = paragraphs_by_index.get(index, "")
        if not text.strip():
            continue
        max_lines_for_estimate = max(1, estimate_wrapped_line_count(text, 9999))
        line_capacity = paragraph_char_capacity(shape, paragraph, geometry, font_scale, max_lines_for_estimate)
        chars_per_line = max(MIN_CHARS_PER_LINE, line_capacity // max(1, max_lines_for_estimate))
        lines = estimate_wrapped_line_count(text, chars_per_line)
        total += paragraph_line_height_points(paragraph, font_scale) * max(1, lines)
    return total


def line_budget_for_shape(
    shape: ET.Element,
    geometry: tuple[int, int, int, int] | None,
    paragraphs: list[ET.Element],
    font_scale: float = 1.0,
) -> int:
    if not paragraphs:
        return 1

    _, usable_height_points = shape_content_box_points(shape, geometry)
    avg_line_height = sum(
        paragraph_line_height_points(paragraph, font_scale) for paragraph in paragraphs
    ) / max(1, len(paragraphs))
    return max(1, int(usable_height_points / max(1.0, avg_line_height)))


def effective_max_lines_for_replacement(
    shape: ET.Element,
    geometry: tuple[int, int, int, int] | None,
    addressable: list[ET.Element],
    replacement_count: int,
    style: str,
    max_lines_per_paragraph: int,
    font_scale: float,
) -> int:
    effective_max_lines = max_lines_per_paragraph
    if replacement_count <= 0:
        return effective_max_lines

    relevant_paragraphs = addressable[:replacement_count]
    line_budget = line_budget_for_shape(shape, geometry, relevant_paragraphs, font_scale=font_scale)
    per_paragraph_budget = max(1, line_budget // max(1, replacement_count))
    if style in {"title", "subtitle", "bullets"}:
        effective_max_lines = max(1, min(max_lines_per_paragraph, per_paragraph_budget))
    return effective_max_lines


def bullets_meet_word_policy(paragraphs: list[str], minimum_words: int) -> bool:
    visible = [paragraph for paragraph in paragraphs if paragraph.strip()]
    if not visible:
        return False
    return all(minimum_words <= word_count(paragraph) <= BULLET_MAX_WORDS for paragraph in visible)


def shape_text_fits(
    shape: ET.Element,
    geometry: tuple[int, int, int, int] | None,
    paragraphs: list[str],
    font_scale: float,
    max_lines_per_paragraph: int,
) -> bool:
    all_paragraphs = shape_paragraph_elements(shape)
    addressable = shape_addressable_paragraphs(shape)
    addressable_indices = [all_paragraphs.index(paragraph) for paragraph in addressable]
    paragraphs_by_index: dict[int, str] = {
        paragraph_index: paragraphs[position] if position < len(paragraphs) else ""
        for position, paragraph_index in enumerate(addressable_indices)
    }

    for position, paragraph_index in enumerate(addressable_indices):
        text = paragraphs[position] if position < len(paragraphs) else ""
        if not text.strip():
            continue
        paragraph = all_paragraphs[paragraph_index]
        capacity = paragraph_char_capacity(
            shape,
            paragraph,
            geometry,
            font_scale,
            max_lines_per_paragraph,
        )
        chars_per_line = max(MIN_CHARS_PER_LINE, capacity // max(1, max_lines_per_paragraph))
        if estimate_wrapped_line_count(text, chars_per_line) > max_lines_per_paragraph:
            return False

    _, usable_height_points = shape_content_box_points(shape, geometry)
    return estimate_shape_text_height_points(shape, geometry, paragraphs_by_index, font_scale) <= usable_height_points


def fit_paragraphs_to_shape(
    shape: ET.Element,
    geometry: tuple[int, int, int, int] | None,
    replacement: list[str],
    slide_number: int,
    shape_index: int,
    warnings: list[str],
    preferred_font_scale: float = 1.0,
    min_font_scale: float | None = None,
) -> tuple[list[str], float, bool]:
    cleaned_paragraphs = [clean_replacement_text(text) for text in replacement]
    style = detect_text_shape_style(shape, geometry)
    limits = TEXT_STYLE_LIMITS[style]
    max_paragraphs = min(len(shape_addressable_paragraphs(shape)), int(limits["max_paragraphs"]))
    max_lines_per_paragraph = int(limits["max_lines_per_paragraph"])
    min_scale = min_font_scale if min_font_scale is not None else float(limits["min_scale"])
    start_scale = min(preferred_font_scale, 1.0)

    if style == "title" and len(cleaned_paragraphs) > 1:
        cleaned_paragraphs = [" - ".join(text for text in cleaned_paragraphs if text).strip()]

    if len(cleaned_paragraphs) > max_paragraphs:
        warnings.append(
            f"Slide {slide_number} shape {shape_index}: condensed {len(cleaned_paragraphs)} paragraphs "
            f"to {max_paragraphs} to preserve the layout."
        )
        cleaned_paragraphs = cleaned_paragraphs[:max_paragraphs]

    addressable = shape_addressable_paragraphs(shape)
    effective_max_lines = effective_max_lines_for_replacement(
        shape,
        geometry,
        addressable,
        len(cleaned_paragraphs),
        style,
        max_lines_per_paragraph,
        start_scale,
    )

    candidate = list(cleaned_paragraphs)

    font_scale = start_scale
    while font_scale >= min_scale:
        if shape_text_fits(shape, geometry, candidate, font_scale, effective_max_lines):
            return candidate, font_scale, True
        font_scale = round(font_scale - 0.04, 2)

    tightened = list(candidate)
    shortened_to_min_scale = False
    for paragraph_index, paragraph in enumerate(addressable[: len(tightened)]):
        char_limit = paragraph_char_capacity(
            shape,
            paragraph,
            geometry,
            min_scale,
            effective_max_lines,
        )
        summarized = summarize_text_to_limit(
            tightened[paragraph_index],
            char_limit,
            content_style=style,
        )
        if summarized != tightened[paragraph_index]:
            tightened[paragraph_index] = summarized
            shortened_to_min_scale = True

    if (
        style != "bullets"
        and shortened_to_min_scale
        and shape_text_fits(shape, geometry, tightened, min_scale, effective_max_lines)
    ):
        warnings.append(
            f"Slide {slide_number} shape {shape_index}: summarized text to keep it inside the placeholder."
        )
        return tightened, min_scale, True

    if style == "bullets":
        for minimum_words in (BULLET_MIN_WORDS, BULLET_MIN_FALLBACK_WORDS):
            for keep_count in range(len(cleaned_paragraphs), 0, -1):
                current = list(cleaned_paragraphs[:keep_count])
                current_max_lines = effective_max_lines_for_replacement(
                    shape,
                    geometry,
                    addressable,
                    len(current),
                    style,
                    max_lines_per_paragraph,
                    min_scale,
                )

                if (
                    bullets_meet_word_policy(current, minimum_words)
                    and shape_text_fits(shape, geometry, current, min_scale, current_max_lines)
                ):
                    if keep_count < len(cleaned_paragraphs):
                        warnings.append(
                            f"Slide {slide_number} shape {shape_index}: reduced bullet count to preserve complete phrasing."
                        )
                    return current, min_scale, True

                summarized_current = list(current)
                changed = False
                for paragraph_index, paragraph in enumerate(addressable[: len(summarized_current)]):
                    char_limit = paragraph_char_capacity(
                        shape,
                        paragraph,
                        geometry,
                        min_scale,
                        current_max_lines,
                    )
                    summarized = summarize_text_to_limit(
                        summarized_current[paragraph_index],
                        char_limit,
                        content_style=style,
                    )
                    if summarized != summarized_current[paragraph_index]:
                        summarized_current[paragraph_index] = summarized
                        changed = True

                if not bullets_meet_word_policy(summarized_current, minimum_words):
                    continue

                if shape_text_fits(shape, geometry, summarized_current, min_scale, current_max_lines):
                    if keep_count < len(cleaned_paragraphs):
                        warnings.append(
                            f"Slide {slide_number} shape {shape_index}: reduced bullet count to preserve complete phrasing."
                        )
                    if changed:
                        warnings.append(
                            f"Slide {slide_number} shape {shape_index}: summarized text to keep it inside the placeholder."
                        )
                    return summarized_current, min_scale, True

        if shortened_to_min_scale and shape_text_fits(shape, geometry, tightened, min_scale, effective_max_lines):
            warnings.append(
                f"Slide {slide_number} shape {shape_index}: summarized text to keep it inside the placeholder."
            )
            return tightened, min_scale, True

    while tightened:
        changed = False
        for paragraph_index, paragraph in enumerate(addressable[: len(tightened)]):
            char_limit = paragraph_char_capacity(
                shape,
                paragraph,
                geometry,
                min_scale,
                effective_max_lines,
            )
            tighter_limit = max(MIN_CHARS_PER_LINE, int(char_limit * 0.82))
            summarized = summarize_text_to_limit(
                tightened[paragraph_index],
                tighter_limit,
                content_style=style,
            )
            if summarized != tightened[paragraph_index]:
                tightened[paragraph_index] = summarized
                changed = True

        if shape_text_fits(shape, geometry, tightened, min_scale, effective_max_lines):
            warnings.append(
                f"Slide {slide_number} shape {shape_index}: summarized text to keep it inside the placeholder."
            )
            return tightened, min_scale, True

        if not changed:
            break

    while len(tightened) > 1:
        tightened = tightened[:-1]
        warnings.append(
            f"Slide {slide_number} shape {shape_index}: dropped excess paragraph content to avoid overflow."
        )
        if shape_text_fits(shape, geometry, tightened, min_scale, effective_max_lines):
            return tightened, min_scale, True

    if tightened:
        paragraph = addressable[0] if addressable else shape_paragraph_elements(shape)[0]
        hard_limit = max(
            MIN_CHARS_PER_LINE,
            int(
                paragraph_char_capacity(
                    shape,
                    paragraph,
                    geometry,
                    min_scale,
                    effective_max_lines,
                )
                * 0.72
            ),
        )
        summarized = summarize_text_to_limit(
            tightened[0],
            hard_limit,
            content_style=style,
        )
        if summarized != tightened[0]:
            tightened[0] = summarized
            warnings.append(
                f"Slide {slide_number} shape {shape_index}: condensed text to protect the design."
            )

    fits = shape_text_fits(shape, geometry, tightened, min_scale, effective_max_lines)
    return tightened, min_scale, fits


def scale_run_properties(node: ET.Element | None, font_scale: float) -> ET.Element | None:
    if node is None:
        return None
    scaled = deepcopy(node)
    if scaled.attrib.get("sz"):
        scaled.attrib["sz"] = str(max(900, int(round(int(scaled.attrib["sz"]) * font_scale))))
    return scaled


def set_body_autofit(shape: ET.Element, font_scale: float) -> None:
    body_props = shape.find("./p:txBody/a:bodyPr", NS)
    if body_props is None:
        text_body = shape.find("./p:txBody", NS)
        if text_body is None:
            return
        body_props = ET.Element(f"{{{A_NS}}}bodyPr")
        text_body.insert(0, body_props)

    body_props.attrib["wrap"] = "square"
    body_props.attrib["vertOverflow"] = "clip"
    for tag_name in ("spAutoFit", "noAutofit", "normAutofit"):
        existing = body_props.find(f"a:{tag_name}", NS)
        if existing is not None:
            body_props.remove(existing)

    norm_autofit = ET.SubElement(body_props, f"{{{A_NS}}}normAutofit")
    norm_autofit.set("fontScale", str(max(60000, int(round(font_scale * 100000)))))
    line_reduction = max(0, min(20000, int(round((1.0 - font_scale) * 50000))))
    norm_autofit.set("lnSpcReduction", str(line_reduction))


def set_paragraph_text(paragraph: ET.Element, text: str, font_scale: float = 1.0) -> None:
    paragraph_props = deepcopy(paragraph.find("a:pPr", NS))
    first_run = paragraph.find("a:r", NS)
    run_props = scale_run_properties(first_run.find("a:rPr", NS) if first_run is not None else None, font_scale)
    end_props = scale_run_properties(paragraph.find("a:endParaRPr", NS), font_scale)

    for child in list(paragraph):
        paragraph.remove(child)

    if paragraph_props is not None:
        line_spacing = paragraph_props.find("a:lnSpc", NS)
        if line_spacing is not None:
            spacing_points = line_spacing.find("a:spcPts", NS)
            if spacing_points is not None and spacing_points.attrib.get("val"):
                spacing_points.attrib["val"] = str(max(800, int(round(int(spacing_points.attrib["val"]) * font_scale))))
        paragraph.append(paragraph_props)

    if text:
        for line_index, line in enumerate(text.split("\n")):
            if line_index > 0:
                paragraph.append(ET.Element(f"{{{A_NS}}}br"))
            run = ET.Element(f"{{{A_NS}}}r")
            if run_props is not None:
                run.append(deepcopy(run_props))
            text_node = ET.SubElement(run, f"{{{A_NS}}}t")
            if line.startswith(" ") or line.endswith(" "):
                text_node.set(f"{{{XML_NS}}}space", "preserve")
            text_node.text = line
            paragraph.append(run)

    if end_props is not None:
        paragraph.append(end_props)


def replace_shape_paragraphs(shape: ET.Element, replacement: list[str], font_scale: float) -> None:
    paragraphs = shape_paragraph_elements(shape)
    if not paragraphs:
        raise ValueError("Text shape without paragraphs")

    addressable = shape_addressable_paragraphs(shape)
    addressable_indices = [paragraphs.index(paragraph) for paragraph in addressable]

    for position, paragraph_index in enumerate(addressable_indices):
        paragraph = paragraphs[paragraph_index]
        new_text = replacement[position] if position < len(replacement) else ""
        set_paragraph_text(paragraph, new_text, font_scale=font_scale)

    set_body_autofit(shape, font_scale)


def group_scale_factors(plans: list[TextShapePlan], common_font_size: int) -> list[float]:
    if not plans:
        return [1.0]

    min_group_factor = 0.0
    for plan in plans:
        base_scale = common_font_size / max(1, plan.base_font_size)
        style_min_scale = float(TEXT_STYLE_LIMITS[plan.style]["min_scale"])
        min_group_factor = max(min_group_factor, style_min_scale / base_scale)

    min_group_factor = min(1.0, max(0.6, min_group_factor))
    factors: list[float] = []
    current = 1.0
    while current > min_group_factor:
        factors.append(round(current, 2))
        current = round(current - 0.04, 2)
    if not factors or abs(factors[-1] - min_group_factor) > 1e-6:
        factors.append(round(min_group_factor, 2))
    return factors


def replacement_quality_score(style: str, replacement: list[str]) -> tuple[int, int, int, int]:
    if style != "bullets":
        return (0, 0, 0, 0)

    visible = [paragraph for paragraph in replacement if paragraph.strip()]
    if not visible:
        return (0, 0, 0, 0)

    strict_matches = sum(
        1 for paragraph in visible if BULLET_MIN_WORDS <= word_count(paragraph) <= BULLET_MAX_WORDS
    )
    relaxed_matches = sum(
        1 for paragraph in visible if BULLET_MIN_FALLBACK_WORDS <= word_count(paragraph) <= BULLET_MAX_WORDS
    )
    total_words = sum(word_count(paragraph) for paragraph in visible)
    return (strict_matches, relaxed_matches, len(visible), total_words)


def group_candidate_quality(
    group_plans: list[TextShapePlan],
    candidate_results: dict[int, tuple[list[str], float]],
) -> tuple[int, int, int, int, int, int, int, int]:
    per_plan_qualities: list[tuple[int, int, int, int]] = []
    strict_total = 0
    relaxed_total = 0
    bullet_count_total = 0
    word_total = 0
    for plan in group_plans:
        replacement, _ = candidate_results[plan.shape_index]
        strict, relaxed, bullet_count, total_words = replacement_quality_score(plan.style, replacement)
        per_plan_qualities.append((strict, relaxed, bullet_count, total_words))
        strict_total += strict
        relaxed_total += relaxed
        bullet_count_total += bullet_count
        word_total += total_words

    if not per_plan_qualities:
        return (0, 0, 0, 0, strict_total, relaxed_total, bullet_count_total, word_total)

    min_strict = min(item[0] for item in per_plan_qualities)
    min_relaxed = min(item[1] for item in per_plan_qualities)
    min_bullet_count = min(item[2] for item in per_plan_qualities)
    min_word_total = min(item[3] for item in per_plan_qualities)
    return (
        min_strict,
        min_relaxed,
        min_bullet_count,
        min_word_total,
        strict_total,
        relaxed_total,
        bullet_count_total,
        word_total,
    )


def rewrite_slide(
    xml_bytes: bytes,
    replacements: list[list[str]],
    slide_number: int,
    warnings: list[str],
) -> bytes:
    root = ET.fromstring(xml_bytes)
    text_shape_targets = text_shape_targets_from_slide(root)
    text_shapes = [target.element for target in text_shape_targets]
    normalized_replacements = normalize_slide_replacements(
        replacements,
        len(text_shapes),
        slide_number,
    )

    plans: list[TextShapePlan] = []
    for shape_index, (target, replacement) in enumerate(
        zip(text_shape_targets, normalized_replacements, strict=True),
        start=1,
    ):
        plans.append(
            TextShapePlan(
                target=target,
                replacement=replacement,
                shape_index=shape_index,
                style=detect_text_shape_style(target.element, target.geometry),
                base_font_size=shape_primary_font_size_centipoints(target.element),
            )
        )

    applied_by_shape_index: dict[int, tuple[list[str], float]] = {}
    primary_title_index = primary_title_shape_index(plans)
    groups: dict[str, list[TextShapePlan]] = {}
    for plan in plans:
        groups.setdefault(typography_group_key(plan, primary_title_index), []).append(plan)

    for style, group_plans in groups.items():
        common_font_size = min(plan.base_font_size for plan in group_plans)
        chosen_results: dict[int, tuple[list[str], float]] | None = None
        chosen_warnings: list[str] = []
        chosen_quality: tuple[int, int, int, int, int, int, int, int] | None = None
        chosen_factor = 0.0
        last_results: dict[int, tuple[list[str], float]] | None = None
        last_warnings: list[str] = []

        for group_factor in group_scale_factors(group_plans, common_font_size):
            candidate_results: dict[int, tuple[list[str], float]] = {}
            candidate_warnings: list[str] = []
            all_fit = True

            for plan in group_plans:
                normalized_scale = common_font_size / max(1, plan.base_font_size)
                target_scale = min(1.0, normalized_scale * group_factor)
                fitted_replacement, font_scale, fits = fit_paragraphs_to_shape(
                    plan.target.element,
                    plan.target.geometry,
                    plan.replacement,
                    slide_number,
                    plan.shape_index,
                    candidate_warnings,
                    preferred_font_scale=target_scale,
                    min_font_scale=target_scale,
                )
                candidate_results[plan.shape_index] = (fitted_replacement, font_scale)
                if not fits:
                    all_fit = False

            last_results = candidate_results
            last_warnings = candidate_warnings
            if all_fit:
                if style != "bullets":
                    chosen_results = candidate_results
                    chosen_warnings = candidate_warnings
                    break

                candidate_quality = group_candidate_quality(group_plans, candidate_results)
                if (
                    chosen_results is None
                    or chosen_quality is None
                    or candidate_quality > chosen_quality
                    or (candidate_quality == chosen_quality and group_factor > chosen_factor)
                ):
                    chosen_results = candidate_results
                    chosen_warnings = candidate_warnings
                    chosen_quality = candidate_quality
                    chosen_factor = group_factor

        if chosen_results is None:
            if last_results is not None:
                chosen_results = last_results
                chosen_warnings = last_warnings
            warnings.append(
                f"Slide {slide_number}: kept uniform typography for {style} shapes and trimmed content to preserve layout."
            )

        warnings.extend(chosen_warnings)
        applied_by_shape_index.update(chosen_results)

    for plan in plans:
        fitted_replacement, font_scale = applied_by_shape_index[plan.shape_index]
        replace_shape_paragraphs(plan.target.element, fitted_replacement, font_scale)

    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def reordered_presentation_xml(
    presentation_xml: bytes,
    rels_xml: bytes,
    slide_order: list[int],
) -> bytes:
    presentation_root = ET.fromstring(presentation_xml)
    rels_root = ET.fromstring(rels_xml)

    slide_number_by_rel: dict[str, int] = {}
    for rel in rels_root.findall("rel:Relationship", NS):
        rel_type = rel.attrib.get("Type", "")
        if not rel_type.endswith("/slide"):
            continue
        target = rel.attrib.get("Target", "")
        slide_number_by_rel[rel.attrib["Id"]] = slide_number_from_path(target)

    slide_id_list = presentation_root.find("p:sldIdLst", NS)
    if slide_id_list is None:
        raise ValueError("Presentation does not contain a slide list")

    original_elements = list(slide_id_list)
    slide_element_by_number: dict[int, ET.Element] = {}
    for element in original_elements:
        rel_id = element.attrib.get(f"{{{R_NS}}}id")
        if not rel_id:
            continue
        slide_number = slide_number_by_rel.get(rel_id)
        if slide_number is not None:
            slide_element_by_number[slide_number] = deepcopy(element)

    missing = [slide_number for slide_number in slide_order if slide_number not in slide_element_by_number]
    if missing:
        raise ValueError(f"Slides not found in presentation order map: {missing}")

    for element in original_elements:
        slide_id_list.remove(element)

    for slide_number in slide_order:
        slide_id_list.append(slide_element_by_number[slide_number])

    return ET.tostring(presentation_root, encoding="utf-8", xml_declaration=True)


def load_spec(spec_path: Path) -> dict:
    return json.loads(spec_path.read_text(encoding="utf-8"))


def build_from_spec_data(
    spec: dict,
    spec_dir: Path,
) -> dict[str, list[Path] | list[str] | Path | None]:
    template_path = resolve_config_path(spec.get("template_path"), spec_dir) or DEFAULT_TEMPLATE
    output_pptx = resolve_output_path(spec.get("output_pptx"), spec_dir, DEFAULT_OUTPUT)
    output_notes = None
    if spec.get("output_notes") is not None:
        output_notes = resolve_output_path(
            str(spec["output_notes"]),
            spec_dir,
            OUTPUT_ROOT / "propuesta-economica-notes.md",
        )
    extra_output_paths = resolve_output_path_list(spec.get("extra_output_paths", []) or [], spec_dir)
    notes_markdown_path = resolve_config_path(spec.get("notes_markdown_path"), spec_dir)
    notes_markdown = spec.get("notes_markdown")

    if template_path is None or not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")
    if output_notes is not None and notes_markdown is None and notes_markdown_path is None:
        raise ValueError("output_notes requires notes_markdown or notes_markdown_path")

    if notes_markdown_path is not None:
        notes_markdown = notes_markdown_path.read_text(encoding="utf-8")

    slide_replacements = {
        int(slide_number): replacements
        for slide_number, replacements in spec.get("slide_replacements", {}).items()
    }
    slide_order = [int(slide_number) for slide_number in spec.get("slide_order", [])]
    slide_images = normalize_slide_images(spec.get("slide_images", {}), spec_dir)
    team_section = normalize_team_section(spec, spec_dir)

    output_pptx.parent.mkdir(parents=True, exist_ok=True)
    if output_notes is not None:
        output_notes.parent.mkdir(parents=True, exist_ok=True)

    modified_entries: dict[str, bytes] = {}
    new_entries: dict[str, bytes] = {}
    warnings: list[str] = []
    with zipfile.ZipFile(template_path, "r") as source_zip:
        source_presentation_xml = source_zip.read("ppt/presentation.xml")
        source_presentation_rels_xml = source_zip.read("ppt/_rels/presentation.xml.rels")
        source_content_types_xml = source_zip.read("[Content_Types].xml")
        presentation_xml = source_presentation_xml
        presentation_rels_xml = source_presentation_rels_xml
        content_types_xml = source_content_types_xml
        existing_slide_numbers = {slide_number_from_path(path) for path in sorted_slide_paths(source_zip)}
        slide_size = presentation_slide_size(presentation_xml)
        source_paths = set(source_zip.namelist())
        reserved_paths = set(source_paths)
        missing_replacement_slides = [
            slide_number for slide_number in slide_replacements if slide_number not in existing_slide_numbers
        ]
        if missing_replacement_slides:
            raise ValueError(f"Slides not present in template for replacements: {missing_replacement_slides}")

        missing_image_slides = [
            slide_number for slide_number in slide_images if slide_number not in existing_slide_numbers
        ]
        if missing_image_slides:
            raise ValueError(f"Slides not present in template for image insertion: {missing_image_slides}")

        if team_section is not None and team_section.template_slide not in existing_slide_numbers:
            raise ValueError(
                f"Slide {team_section.template_slide} is not present in the template for the team section."
            )

        if slide_order:
            missing_order_slides = [
                slide_number for slide_number in slide_order if slide_number not in existing_slide_numbers
            ]
            if missing_order_slides:
                raise ValueError(f"Slides not present in template for ordering: {missing_order_slides}")

        for slide_number, replacements in slide_replacements.items():
            slide_path = f"ppt/slides/slide{slide_number}.xml"
            modified_entries[slide_path] = rewrite_slide(
                source_zip.read(slide_path),
                replacements,
                slide_number,
                warnings,
            )

        used_image_extensions: set[str] = set()
        media_targets_by_source: dict[Path, str] = {}
        for slide_number, image_entries in slide_images.items():
            slide_path = slide_path_for_number(slide_number)
            slide_xml = entry_bytes(
                slide_path,
                source_zip,
                source_paths,
                modified_entries,
                new_entries,
            )
            if slide_xml is None:
                raise ValueError(f"Slide XML not found for slide {slide_number}")
            rels_path = slide_relationships_path_for_number(slide_number)
            rels_xml = entry_bytes(
                rels_path,
                source_zip,
                source_paths,
                modified_entries,
                new_entries,
            )

            for image_index, image_entry in enumerate(image_entries, start=1):
                image_path = image_entry["image_path"]
                if not isinstance(image_path, Path):
                    raise ValueError(f"Unexpected image path value: {image_path!r}")

                media_target, image_bytes = ensure_media_entry(
                    image_path,
                    reserved_paths,
                    media_targets_by_source,
                    new_entries,
                    used_image_extensions,
                )
                native_size = image_native_emu_size(image_path, image_bytes)
                slide_root = ET.fromstring(slide_xml)
                target_geometry = resolve_target_geometry(
                    slide_root,
                    image_entry,
                    slide_number,
                    slide_size,
                    warnings,
                )
                if image_entry.get("target_existing") is not None and target_geometry is None:
                    slide_xml = ET.tostring(slide_root, encoding="utf-8", xml_declaration=True)
                    continue

                geometry_input = dict(image_entry)
                if target_geometry is not None and image_entry.get("use_target_geometry", True):
                    target_x, target_y, target_cx, target_cy = target_geometry
                    geometry_input["box"] = {
                        "x": target_x,
                        "y": target_y,
                        "cx": target_cx,
                        "cy": target_cy,
                    }

                geometry = resolve_image_geometry(geometry_input, slide_size, native_size)
                rels_xml, relationship_id = upsert_image_relationship(
                    rels_xml,
                    f"../media/{Path(media_target).name}",
                )
                slide_root = insert_picture_into_root(
                    slide_root,
                    relationship_id=relationship_id,
                    geometry=geometry,
                    picture_name=image_entry.get("name", f"Inserted Image {slide_number}-{image_index}"),
                )
                slide_xml = ET.tostring(slide_root, encoding="utf-8", xml_declaration=True)

            modified_entries[slide_path] = slide_xml
            if rels_path in source_paths:
                modified_entries[rels_path] = rels_xml
            else:
                new_entries[rels_path] = rels_xml

        generated_team_slide_numbers: list[int] = []
        if team_section is not None:
            template_slide_path = slide_path_for_number(team_section.template_slide)
            template_rels_path = slide_relationships_path_for_number(team_section.template_slide)
            template_slide_xml = entry_bytes(
                template_slide_path,
                source_zip,
                source_paths,
                modified_entries,
                new_entries,
            )
            if template_slide_xml is None:
                raise ValueError(
                    f"Slide XML not found for the team section template slide {team_section.template_slide}"
                )
            template_rels_xml = entry_bytes(
                template_rels_path,
                source_zip,
                source_paths,
                modified_entries,
                new_entries,
            )

            default_team_image = team_section.default_image_path or find_team_default_image(
                team_section.image_dirs
            )
            if default_team_image is None:
                raise FileNotFoundError(
                    f"Default team image '{TEAM_DEFAULT_IMAGE_NAME}' was not found in the configured team image directories."
                )

            resolved_members: list[TeamMember] = []
            for member in team_section.members:
                matched_image = member.image_path
                if matched_image is None:
                    matched_image = find_team_member_image(member.name, team_section.image_dirs)
                if matched_image is None:
                    matched_image = default_team_image
                    warnings.append(
                        f"Team member '{member.name}': no specific photo matched in Equipo; used '{default_team_image.name}'."
                    )

                resolved_members.append(
                    TeamMember(
                        name=member.name,
                        role=member.role,
                        image_path=matched_image,
                    )
                )

            member_chunks = [
                resolved_members[index:index + team_section.max_per_slide]
                for index in range(0, len(resolved_members), team_section.max_per_slide)
            ]

            for chunk_index, member_chunk in enumerate(member_chunks):
                slide_number = next_slide_number(reserved_paths)
                generated_team_slide_numbers.append(slide_number)
                slide_path = slide_path_for_number(slide_number)
                rels_path = slide_relationships_path_for_number(slide_number)
                reserved_paths.add(slide_path)
                new_entries[slide_path] = template_slide_xml
                if template_rels_xml is not None:
                    new_entries[rels_path] = template_rels_xml
                presentation_rels_xml, relationship_id = add_slide_relationship(
                    presentation_rels_xml,
                    slide_number,
                )
                presentation_xml = append_slide_reference(
                    presentation_xml,
                    relationship_id,
                )
                content_types_xml = ensure_slide_content_type_overrides(
                    content_types_xml,
                    [slide_number],
                )

                populated_slide_xml, populated_rels_xml = populate_team_slide(
                    template_slide_xml,
                    template_rels_xml,
                    slide_number,
                    slide_size,
                    member_chunk,
                    team_section.title,
                    team_section.replace_title,
                    warnings,
                    reserved_paths,
                    media_targets_by_source,
                    new_entries,
                    used_image_extensions,
                )
                new_entries[slide_path] = populated_slide_xml

                if populated_rels_xml is not None:
                    new_entries[rels_path] = populated_rels_xml

        final_slide_order: list[int] | None = None
        if generated_team_slide_numbers:
            base_order = slide_order or current_presentation_slide_order(
                presentation_xml,
                presentation_rels_xml,
            )
            final_slide_order = expand_slide_order_for_generated_slides(
                base_order,
                team_section.template_slide if team_section is not None else TEAM_SECTION_DEFAULT_SLIDE,
                generated_team_slide_numbers,
                warnings,
            )
        elif slide_order:
            final_slide_order = slide_order

        if final_slide_order:
            presentation_xml = reordered_presentation_xml(
                presentation_xml,
                presentation_rels_xml,
                final_slide_order,
            )

        if used_image_extensions:
            content_types_xml = ensure_image_content_types(
                content_types_xml,
                used_image_extensions,
            )

        if presentation_xml != source_presentation_xml:
            modified_entries["ppt/presentation.xml"] = presentation_xml
        if presentation_rels_xml != source_presentation_rels_xml:
            modified_entries["ppt/_rels/presentation.xml.rels"] = presentation_rels_xml
        if content_types_xml != source_content_types_xml:
            modified_entries["[Content_Types].xml"] = content_types_xml

        with zipfile.ZipFile(output_pptx, "w", compression=zipfile.ZIP_DEFLATED) as output_zip:
            for info in source_zip.infolist():
                data = modified_entries.get(info.filename, source_zip.read(info.filename))
                output_zip.writestr(info.filename, data)
            for filename, data in new_entries.items():
                if filename not in source_paths:
                    output_zip.writestr(filename, data)

    if output_notes is not None and notes_markdown is not None:
        output_notes.write_text(notes_markdown, encoding="utf-8")

    copied_outputs: list[Path] = []
    for extra_path in extra_output_paths:
        if extra_path is None:
            continue
        extra_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copyfile(output_pptx, extra_path)
            copied_outputs.append(extra_path)
        except PermissionError:
            warnings.append(
                f"Could not overwrite locked copy: {extra_path}"
            )

    return {
        "output_pptx": output_pptx,
        "output_notes": output_notes,
        "extra_output_paths": copied_outputs,
        "warnings": warnings,
    }


def build_from_spec(spec_path: Path) -> dict[str, list[Path] | list[str] | Path | None]:
    spec_path = spec_path.resolve()
    return build_from_spec_data(load_spec(spec_path), spec_path.parent)


def inspect_template(template_path: Path, slide_numbers: list[int] | None = None) -> str:
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    lines: list[str] = []
    with zipfile.ZipFile(template_path, "r") as source_zip:
        slides = sorted_slide_paths(source_zip)
        selected_numbers = set(slide_numbers or [])

        for slide_path in slides:
            slide_number = slide_number_from_path(slide_path)
            if selected_numbers and slide_number not in selected_numbers:
                continue

            root = ET.fromstring(source_zip.read(slide_path))
            text_shape_targets = text_shape_targets_from_slide(root)
            text_shapes = [target.element for target in text_shape_targets]
            inspect_plans = [
                TextShapePlan(
                    target=target,
                    replacement=[],
                    shape_index=index,
                    style=detect_text_shape_style(target.element, target.geometry),
                    base_font_size=shape_primary_font_size_centipoints(target.element),
                )
                for index, target in enumerate(text_shape_targets, start=1)
            ]
            primary_title_index = primary_title_shape_index(inspect_plans)
            all_texts = [
                text
                for shape in text_shapes
                for text in shape_paragraph_texts(shape)
            ]
            preview = " | ".join(all_texts[:8])
            lines.append(
                f"SLIDE {slide_number} | text_shapes={len(text_shapes)} | preview={preview}"
            )

            for index, shape in enumerate(text_shapes, start=1):
                paragraphs = shape_paragraph_texts(shape)
                joined = " || ".join(paragraphs)
                role = typography_group_key(inspect_plans[index - 1], primary_title_index)
                lines.append(f"  SHAPE {index} [{role}]: {joined}")

    return "\n".join(lines)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect and build PPTX presentations using the creacion-propuesta skill."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="Print text-shape mappings from a template.")
    inspect_parser.add_argument(
        "--template",
        default=str(DEFAULT_TEMPLATE),
        help="Path to the template PPTX. Defaults to the official Ariova template.",
    )
    inspect_parser.add_argument(
        "--slides",
        nargs="*",
        type=int,
        help="Optional slide numbers to inspect.",
    )

    build_parser = subparsers.add_parser(
        "build",
        help="Generate a PPTX from a JSON spec. Prefer stdin for transient requests.",
    )
    build_parser.add_argument(
        "--spec",
        required=True,
        help="Path to the JSON specification file, or '-' to read JSON from stdin.",
    )
    build_parser.add_argument(
        "--base-dir",
        help="Base directory used to resolve relative paths when --spec - is used.",
    )

    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    if args.command == "inspect":
        template_path = Path(args.template).resolve()
        print(inspect_template(template_path, args.slides))
        return 0

    if args.command == "build":
        if args.spec == "-":
            spec_dir = Path(args.base_dir).resolve() if args.base_dir else Path.cwd()
            result = build_from_spec_data(json.load(sys.stdin), spec_dir)
        else:
            result = build_from_spec(Path(args.spec))
        print(f"PPTX: {result['output_pptx']}")
        if result["output_notes"] is not None:
            print(f"NOTES: {result['output_notes']}")
        for copied_path in result["extra_output_paths"]:
            print(f"COPY: {copied_path}")
        for warning in result["warnings"]:
            print(f"WARNING: {warning}")
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
