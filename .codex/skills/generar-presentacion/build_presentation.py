from __future__ import annotations

from copy import deepcopy
import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
import shutil
import sys
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
DEFAULT_TEMPLATE = SKILL_ROOT / "assets" / "default-template.pptx"
EMU_PER_PIXEL = 9525
DEFAULT_CENTER_IMAGE_MAX_WIDTH_RATIO = 0.26
DEFAULT_CENTER_IMAGE_MAX_HEIGHT_RATIO = 0.18
IMAGE_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
IMAGE_CONTENT_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".svg": "image/svg+xml",
}
PLACEHOLDERS = {
    "${skill_root}": str(SKILL_ROOT),
    "${repo_root}": str(REPO_ROOT),
}


@dataclass
class ImageTarget:
    kind: str
    element: ET.Element
    parent: ET.Element
    geometry: tuple[int, int, int, int]
    name: str
    has_text: bool


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
    return None


def pixels_to_emu(pixels: int) -> int:
    return int(round(pixels * EMU_PER_PIXEL))


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


def shape_paragraph_texts(shape: ET.Element) -> list[str]:
    paragraphs = shape.findall("./p:txBody/a:p", NS)
    texts: list[str] = []
    for paragraph in paragraphs:
        text = "".join((node.text or "") for node in paragraph.findall(".//a:t", NS)).strip()
        if text:
            texts.append(text)
    return texts


def text_shapes_from_slide(root: ET.Element) -> list[ET.Element]:
    text_shapes: list[ET.Element] = []
    for shape in root.findall(".//p:sp", NS):
        if shape_paragraph_texts(shape):
            text_shapes.append(shape)
    return text_shapes


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


def set_paragraph_text(paragraph: ET.Element, text: str) -> None:
    paragraph_props = deepcopy(paragraph.find("a:pPr", NS))
    first_run = paragraph.find("a:r", NS)
    run_props = deepcopy(first_run.find("a:rPr", NS)) if first_run is not None else None
    end_props = deepcopy(paragraph.find("a:endParaRPr", NS))

    for child in list(paragraph):
        paragraph.remove(child)

    if paragraph_props is not None:
        paragraph.append(paragraph_props)

    if text:
        run = ET.Element(f"{{{A_NS}}}r")
        if run_props is not None:
            run.append(run_props)
        text_node = ET.SubElement(run, f"{{{A_NS}}}t")
        if text.startswith(" ") or text.endswith(" "):
            text_node.set(f"{{{XML_NS}}}space", "preserve")
        text_node.text = text
        paragraph.append(run)

    if end_props is not None:
        paragraph.append(end_props)


def replace_shape_paragraphs(shape: ET.Element, replacement: list[str]) -> None:
    paragraphs = shape.findall("./p:txBody/a:p", NS)
    if not paragraphs:
        raise ValueError("Text shape without paragraphs")

    for index, paragraph in enumerate(paragraphs):
        new_text = replacement[index] if index < len(replacement) else ""
        set_paragraph_text(paragraph, new_text)


def rewrite_slide(xml_bytes: bytes, replacements: list[list[str]], slide_number: int) -> bytes:
    root = ET.fromstring(xml_bytes)
    text_shapes = text_shapes_from_slide(root)
    normalized_replacements = normalize_slide_replacements(
        replacements,
        len(text_shapes),
        slide_number,
    )

    for shape, replacement in zip(text_shapes, normalized_replacements, strict=True):
        replace_shape_paragraphs(shape, replacement)

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
    output_pptx = resolve_config_path(spec["output_pptx"], spec_dir)
    output_notes = resolve_config_path(spec.get("output_notes"), spec_dir)
    extra_output_paths = [
        resolve_config_path(path_value, spec_dir) for path_value in spec.get("extra_output_paths", [])
    ]
    notes_markdown_path = resolve_config_path(spec.get("notes_markdown_path"), spec_dir)
    notes_markdown = spec.get("notes_markdown")

    if output_pptx is None:
        raise ValueError("The spec must define output_pptx")
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

    output_pptx.parent.mkdir(parents=True, exist_ok=True)
    if output_notes is not None:
        output_notes.parent.mkdir(parents=True, exist_ok=True)

    modified_entries: dict[str, bytes] = {}
    new_entries: dict[str, bytes] = {}
    warnings: list[str] = []
    with zipfile.ZipFile(template_path, "r") as source_zip:
        existing_slide_numbers = {slide_number_from_path(path) for path in sorted_slide_paths(source_zip)}
        slide_size = presentation_slide_size(source_zip.read("ppt/presentation.xml"))
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
            )

        used_image_extensions: set[str] = set()
        media_targets_by_source: dict[Path, str] = {}
        for slide_number, image_entries in slide_images.items():
            slide_path = f"ppt/slides/slide{slide_number}.xml"
            slide_xml = modified_entries.get(slide_path, source_zip.read(slide_path))
            rels_path = f"ppt/slides/_rels/slide{slide_number}.xml.rels"
            rels_xml = modified_entries.get(rels_path)
            if rels_xml is None:
                rels_xml = new_entries.get(rels_path)
            if rels_xml is None and rels_path in source_paths:
                rels_xml = source_zip.read(rels_path)

            for image_index, image_entry in enumerate(image_entries, start=1):
                image_path = image_entry["image_path"]
                if not isinstance(image_path, Path):
                    raise ValueError(f"Unexpected image path value: {image_path!r}")

                media_target = media_targets_by_source.get(image_path)
                if media_target is None:
                    media_target = next_media_path(reserved_paths, image_path.suffix)
                    media_targets_by_source[image_path] = media_target
                    new_entries[media_target] = image_path.read_bytes()
                    used_image_extensions.add(image_path.suffix.lower())

                image_bytes = new_entries[media_target]
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

        if slide_order:
            modified_entries["ppt/presentation.xml"] = reordered_presentation_xml(
                source_zip.read("ppt/presentation.xml"),
                source_zip.read("ppt/_rels/presentation.xml.rels"),
                slide_order,
            )

        if used_image_extensions:
            modified_entries["[Content_Types].xml"] = ensure_image_content_types(
                source_zip.read("[Content_Types].xml"),
                used_image_extensions,
            )

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
            text_shapes = text_shapes_from_slide(root)
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
                lines.append(f"  SHAPE {index}: {joined}")

    return "\n".join(lines)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect and build PPTX presentations using the generar-presentacion skill."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="Print text-shape mappings from a template.")
    inspect_parser.add_argument(
        "--template",
        default=str(DEFAULT_TEMPLATE),
        help="Path to the template PPTX. Defaults to the skill template.",
    )
    inspect_parser.add_argument(
        "--slides",
        nargs="*",
        type=int,
        help="Optional slide numbers to inspect.",
    )

    build_parser = subparsers.add_parser("build", help="Generate a PPTX from a JSON spec.")
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
