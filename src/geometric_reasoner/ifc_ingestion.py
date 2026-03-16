from __future__ import annotations

import math
import re
from collections import defaultdict
from pathlib import Path

from geometric_reasoner.bim_normalized_models import (
    NormalizedDerivedFact,
    NormalizedElement,
    NormalizedLevel,
    NormalizedPlacement,
    NormalizedProject,
    NormalizedSpace,
    NormalizedUnit,
)


SUPPORTED_PRODUCT_TYPES = {
    "IFCDOOR": ("door", "Doors"),
    "IFCWINDOW": ("window", "Windows"),
    "IFCWALLSTANDARDCASE": ("wall", "Walls"),
    "IFCSLAB": ("slab", "Floors"),
    "IFCSTAIR": ("stair", "Stairs"),
}

COMPLIANCE_ROOM_TYPE_MAP = {
    "bad": "Residential Bathroom",
    "bath": "Residential Bathroom",
    "schlafzimmer": "Residential Bedroom",
    "bedroom": "Residential Bedroom",
    "wohnen": "Residential Living Room",
    "living": "Residential Living Room",
    "küche": "Residential Kitchen",
    "kueche": "Residential Kitchen",
    "kuche": "Residential Kitchen",
    "kitchen": "Residential Kitchen",
    "flur": "Residential Corridor",
    "corridor": "Residential Corridor",
}


def _decode_ifc_string(value: str | None) -> str | None:
    if value is None:
        return None

    def replace_hex(match: re.Match[str]) -> str:
        payload = match.group(1)
        return bytes.fromhex(payload).decode("utf-16-be")

    value = re.sub(r"\\X2\\([0-9A-Fa-f]+)\\X0\\", replace_hex, value)
    return value.replace("\\'", "'")


def _split_top_level(payload: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    in_string = False
    i = 0

    while i < len(payload):
        char = payload[i]
        if char == "'" and (i == 0 or payload[i - 1] != "\\"):
            in_string = not in_string
            current.append(char)
        elif not in_string and char == "(":
            depth += 1
            current.append(char)
        elif not in_string and char == ")":
            depth -= 1
            current.append(char)
        elif not in_string and depth == 0 and char == ",":
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(char)
        i += 1

    if current:
        parts.append("".join(current).strip())
    return parts


def _parse_scalar(token: str):
    token = token.strip()
    if token == "$":
        return None
    if token.startswith("#"):
        return token
    if token.startswith("'") and token.endswith("'"):
        return _decode_ifc_string(token[1:-1])
    if token.startswith(".") and token.endswith("."):
        return token.strip(".")
    if token.startswith("(") and token.endswith(")"):
        inner = token[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(part) for part in _split_top_level(inner)]
    try:
        return float(token)
    except ValueError:
        return token


def _parse_step_entities(ifc_path: Path) -> dict[str, tuple[str, list]]:
    text = ifc_path.read_text(encoding="utf-8", errors="ignore")
    data_section = text.split("DATA;", 1)[1].split("ENDSEC;", 1)[0]
    entities: dict[str, tuple[str, list]] = {}

    for line in data_section.splitlines():
        line = line.strip()
        if not line.startswith("#"):
            continue
        match = re.match(r"^(#\d+)\s*=\s*([A-Z0-9_]+)\((.*)\);$", line)
        if not match:
            continue
        entity_id, entity_type, raw_args = match.groups()
        entities[entity_id] = (entity_type, [_parse_scalar(arg) for arg in _split_top_level(raw_args)])

    return entities


def _entity_name(args: list) -> str | None:
    for index in (2, 7, 8):
        if index < len(args) and isinstance(args[index], str) and args[index]:
            return args[index]
    return None


def _build_local_placement_map(entities: dict[str, tuple[str, list]]) -> dict[str, NormalizedPlacement]:
    axis_locations: dict[str, tuple[float, float, float, float]] = {}
    local_placements_raw: dict[str, tuple[str | None, str | None]] = {}

    for entity_id, (entity_type, args) in entities.items():
        if entity_type == "IFCCARTESIANPOINT":
            coords = tuple(float(value) for value in args[0])  # type: ignore[arg-type]
            if len(coords) == 2:
                axis_locations[entity_id] = (coords[0], coords[1], 0.0, 0.0)
            else:
                axis_locations[entity_id] = (coords[0], coords[1], coords[2], 0.0)
        elif entity_type in {"IFCAXIS2PLACEMENT3D", "IFCAXIS2PLACEMENT2D"}:
            location_ref = args[0]
            x_mm = y_mm = z_mm = rotation_deg = 0.0
            if isinstance(location_ref, str) and location_ref in axis_locations:
                x_mm, y_mm, z_mm, _ = axis_locations[location_ref]
            if len(args) > 2 and isinstance(args[2], str):
                ref_dir = entities.get(args[2])
                if ref_dir and ref_dir[0] == "IFCDIRECTION":
                    direction = ref_dir[1][0]
                    if isinstance(direction, list) and len(direction) >= 2:
                        rotation_deg = math.degrees(math.atan2(direction[1], direction[0]))
            axis_locations[entity_id] = (x_mm * 1000.0, y_mm * 1000.0, z_mm * 1000.0, rotation_deg)
        elif entity_type == "IFCLOCALPLACEMENT":
            parent_placement = args[0] if isinstance(args[0], str) else None
            relative_axis = args[1] if isinstance(args[1], str) else None
            local_placements_raw[entity_id] = (parent_placement, relative_axis)

    resolved: dict[str, NormalizedPlacement] = {}

    def resolve(entity_id: str) -> NormalizedPlacement:
        if entity_id in resolved:
            return resolved[entity_id]

        parent_ref, axis_ref = local_placements_raw.get(entity_id, (None, None))
        base = resolve(parent_ref) if parent_ref else NormalizedPlacement(level_id="", level_name="", x_mm=0.0, y_mm=0.0, z_mm=0.0)
        axis_x, axis_y, axis_z, rotation_deg = axis_locations.get(axis_ref or "", (0.0, 0.0, 0.0, 0.0))
        resolved[entity_id] = NormalizedPlacement(
            level_id="",
            level_name="",
            x_mm=base.x_mm + axis_x,
            y_mm=base.y_mm + axis_y,
            z_mm=base.z_mm + axis_z,
            rotation_deg=base.rotation_deg + rotation_deg,
        )
        return resolved[entity_id]

    for placement_id in local_placements_raw:
        resolve(placement_id)

    return resolved


def _build_ifc_project_name(entities: dict[str, tuple[str, list]]) -> tuple[str, str]:
    for entity_id, (entity_type, args) in entities.items():
        if entity_type == "IFCPROJECT":
            guid = args[0] if isinstance(args[0], str) else entity_id.replace("#", "Project_")
            name = _entity_name(args) or "IFC Project"
            return guid, name
    return "ifc_project", "IFC Project"


def _classify_compliance_room_type(name: str | None) -> str | None:
    if not name:
        return None
    lowered = name.lower()
    for keyword, room_type in COMPLIANCE_ROOM_TYPE_MAP.items():
        if keyword in lowered:
            return room_type
    return None


def _build_storeys(entities: dict[str, tuple[str, list]], placements: dict[str, NormalizedPlacement]) -> dict[str, NormalizedLevel]:
    levels: dict[str, NormalizedLevel] = {}
    for entity_id, (entity_type, args) in entities.items():
        if entity_type != "IFCBUILDINGSTOREY":
            continue
        placement = placements.get(args[5], NormalizedPlacement(level_id="", level_name="", x_mm=0.0, y_mm=0.0, z_mm=0.0)) if len(args) > 5 and isinstance(args[5], str) else NormalizedPlacement(level_id="", level_name="", x_mm=0.0, y_mm=0.0, z_mm=0.0)
        name = _entity_name(args) or entity_id
        level_id = entity_id.replace("#", "Storey_")
        elevation = float(args[9]) * 1000.0 if len(args) > 9 and isinstance(args[9], float) else placement.z_mm
        levels[entity_id] = NormalizedLevel(level_id=level_id, name=name, elevation_mm=elevation)
    return levels


def _refs_from_list(value) -> list[str]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []


def ingest_ifc_to_normalized_project(ifc_path: Path) -> NormalizedProject:
    entities = _parse_step_entities(ifc_path)
    project_id, project_name = _build_ifc_project_name(entities)
    placements = _build_local_placement_map(entities)
    storeys = _build_storeys(entities, placements)

    space_to_storey: dict[str, str] = {}
    storey_space_refs: dict[str, list[str]] = defaultdict(list)
    storey_element_refs: dict[str, list[str]] = defaultdict(list)
    element_to_spaces: dict[str, set[str]] = defaultdict(set)

    for _, (entity_type, args) in entities.items():
        if entity_type == "IFCRELAGGREGATES":
            relating = args[4]
            related = _refs_from_list(args[5])
            if isinstance(relating, str) and relating in storeys:
                for space_ref in related:
                    if entities.get(space_ref, ("", []))[0] == "IFCSPACE":
                        space_to_storey[space_ref] = relating
                        storey_space_refs[relating].append(space_ref)
        elif entity_type == "IFCRELCONTAINEDINSPATIALSTRUCTURE":
            related_elements = _refs_from_list(args[4])
            container = args[5] if isinstance(args[5], str) else None
            if container in storeys:
                storey_element_refs[container].extend(related_elements)
        elif entity_type == "IFCRELSPACEBOUNDARY":
            space_ref = args[4] if isinstance(args[4], str) else None
            element_ref = args[5] if isinstance(args[5], str) else None
            if space_ref and element_ref:
                element_to_spaces[element_ref].add(space_ref)

    placement_owner: dict[str, str] = {}
    placement_parent: dict[str, str | None] = {}
    for entity_id, (entity_type, args) in entities.items():
        if entity_type in {"IFCDOOR", "IFCWINDOW", "IFCWALLSTANDARDCASE", "IFCSLAB", "IFCSTAIR", "IFCSPACE", "IFCBUILDINGSTOREY"}:
            placement_ref = args[5] if len(args) > 5 and isinstance(args[5], str) else None
            if placement_ref:
                placement_owner[placement_ref] = entity_id
        if entity_type == "IFCLOCALPLACEMENT":
            placement_parent[entity_id] = args[0] if args and isinstance(args[0], str) else None

    def resolve_host_from_placement(placement_ref: str | None) -> str | None:
        current = placement_ref
        while current:
            owner = placement_owner.get(current)
            if owner:
                return owner
            current = placement_parent.get(current)
        return None

    units: list[NormalizedUnit] = []
    normalized_levels = list(storeys.values())

    for storey_ref, level in storeys.items():
        storey_name = level.name
        unit_id = re.sub(r"[^A-Za-z0-9]+", "_", storey_name).strip("_") or level.level_id

        spaces: list[NormalizedSpace] = []
        normalized_space_ids: dict[str, str] = {}
        for space_ref in storey_space_refs.get(storey_ref, []):
            _, args = entities[space_ref]
            space_number = args[2] if len(args) > 2 and isinstance(args[2], str) and args[2] else space_ref
            long_name = args[7] if len(args) > 7 and isinstance(args[7], str) and args[7] else None
            space_name = long_name or space_number
            placement_ref = args[5] if len(args) > 5 and isinstance(args[5], str) else None
            placement = placements.get(placement_ref or "", NormalizedPlacement(level_id="", level_name="", x_mm=0.0, y_mm=0.0, z_mm=level.elevation_mm))
            normalized_space_id = f"{unit_id}_{space_ref.replace('#', 'space_')}"
            normalized_space_ids[space_ref] = normalized_space_id
            spaces.append(
                NormalizedSpace(
                    space_id=normalized_space_id,
                    unit_id=unit_id,
                    name=long_name,
                    room_type=space_name,
                    level_id=level.level_id,
                    contained_in_unit=unit_id,
                    placement=NormalizedPlacement(
                        level_id=level.level_id,
                        level_name=level.name,
                        x_mm=placement.x_mm,
                        y_mm=placement.y_mm,
                        z_mm=placement.z_mm or level.elevation_mm,
                        rotation_deg=placement.rotation_deg,
                    ),
                    source_scene=space_ref,
                    source_room_id=space_number,
                    raw_properties={
                        "ifc_entity_id": space_ref,
                        "ifc_name": space_number,
                        "ifc_long_name": long_name,
                        "ifc_composition_type": args[8] if len(args) > 8 else None,
                        "compliance_room_type": _classify_compliance_room_type(space_name),
                    },
                )
            )

        shared_space_pairs: dict[str, set[str]] = defaultdict(set)
        space_by_id = {space.space_id: space for space in spaces}

        elements_by_space: dict[str, list[NormalizedElement]] = defaultdict(list)
        derived_facts_by_space: dict[str, list[NormalizedDerivedFact]] = defaultdict(list)

        for element_ref in storey_element_refs.get(storey_ref, []):
            entity_type, args = entities.get(element_ref, ("", []))
            if entity_type not in SUPPORTED_PRODUCT_TYPES:
                continue

            semantic_type, revit_category = SUPPORTED_PRODUCT_TYPES[entity_type]
            display_name = _entity_name(args) or element_ref
            placement_ref = args[5] if len(args) > 5 and isinstance(args[5], str) else None
            placement = placements.get(placement_ref or "", NormalizedPlacement(level_id=level.level_id, level_name=level.name, x_mm=0.0, y_mm=0.0, z_mm=level.elevation_mm))
            related_spaces = sorted(element_to_spaces.get(element_ref, set()))
            normalized_related_spaces = [normalized_space_ids[space_ref] for space_ref in related_spaces if space_ref in normalized_space_ids]

            host_ref = resolve_host_from_placement(placement_parent.get(placement_ref or ""))

            raw_properties = {
                "ifc_entity_id": element_ref,
                "ifc_guid": args[0] if args else None,
                "overall_height_m": args[8] if len(args) > 8 and isinstance(args[8], float) else None,
                "overall_width_m": args[9] if len(args) > 9 and isinstance(args[9], float) else None,
                "tag": args[7] if len(args) > 7 and isinstance(args[7], str) else None,
            }
            if entity_type == "IFCSLAB" and len(args) > 9:
                raw_properties["predefined_type"] = args[9]

            contained_space = normalized_related_spaces[0] if normalized_related_spaces else None
            element = NormalizedElement(
                element_id=element_ref.replace("#", "ifc_"),
                source_label=display_name,
                semantic_type=semantic_type,
                ifc_type=entity_type,
                revit_category=revit_category,
                contained_in_space=contained_space,
                hosted_by=host_ref.replace("#", "ifc_") if host_ref else None,
                adjacent_to=[space_id for space_id in normalized_related_spaces if space_id != contained_space],
                placement=NormalizedPlacement(
                    level_id=level.level_id,
                    level_name=level.name,
                    x_mm=placement.x_mm,
                    y_mm=placement.y_mm,
                    z_mm=placement.z_mm or level.elevation_mm,
                    rotation_deg=placement.rotation_deg,
                ),
                raw_properties={key: value for key, value in raw_properties.items() if value is not None},
            )

            if contained_space:
                elements_by_space[contained_space].append(element)
            elif spaces:
                elements_by_space[spaces[0].space_id].append(element)

            fact_index = len(derived_facts_by_space[contained_space or spaces[0].space_id]) + 1 if spaces else 1
            if isinstance(raw_properties.get("overall_width_m"), float):
                derived_facts_by_space[contained_space or spaces[0].space_id].append(
                    NormalizedDerivedFact(
                        fact_id=f"{element.element_id}_fact_{fact_index:02d}",
                        parameter="ifc_overall_width",
                        value=raw_properties["overall_width_m"] * 1000.0,
                        unit="mm",
                        source_element_id=element.element_id,
                        source_element_label=display_name,
                        source_property="overall_width_m",
                        description=f"{entity_type} overall width",
                    )
                )
                fact_index += 1
            if isinstance(raw_properties.get("overall_height_m"), float):
                derived_facts_by_space[contained_space or spaces[0].space_id].append(
                    NormalizedDerivedFact(
                        fact_id=f"{element.element_id}_fact_{fact_index:02d}",
                        parameter="ifc_overall_height",
                        value=raw_properties["overall_height_m"] * 1000.0,
                        unit="mm",
                        source_element_id=element.element_id,
                        source_element_label=display_name,
                        source_property="overall_height_m",
                        description=f"{entity_type} overall height",
                    )
                )

            for first_space in normalized_related_spaces:
                for second_space in normalized_related_spaces:
                    if first_space != second_space:
                        shared_space_pairs[first_space].add(second_space)

        for space in spaces:
            space.adjacent_to = sorted(shared_space_pairs.get(space.space_id, set()))
            space.elements = sorted(elements_by_space.get(space.space_id, []), key=lambda element: element.element_id)
            space.derived_facts = derived_facts_by_space.get(space.space_id, [])

        units.append(
            NormalizedUnit(
                unit_id=unit_id,
                name=storey_name,
                level_id=level.level_id,
                contained_in_project=project_id,
                source_manifest=ifc_path.name,
                spaces=spaces,
                metadata={
                    "source_scope": "ifc_storey",
                    "ifc_entity_id": storey_ref,
                    "contained_element_count": len(storey_element_refs.get(storey_ref, [])),
                    "space_count": len(spaces),
                },
            )
        )

    return NormalizedProject(
        project_id=project_id,
        name=project_name,
        source_format="ifc_step_ingestion",
        levels=normalized_levels,
        units=units,
        metadata={
            "source_ifc": str(ifc_path),
            "ingestion_method": "lightweight_step_parser",
            "supported_ifc_entities": sorted(SUPPORTED_PRODUCT_TYPES),
            "notes": [
                "This ingestion path parses a subset of IFC STEP entities without ifcopenshell.",
                "Contained space assignment is derived from IfcRelSpaceBoundary when available.",
            ],
        },
    )


def _ifcopenshell_required():
    try:
        import ifcopenshell  # type: ignore
    except ImportError as exc:
        raise ImportError("ifcopenshell is not installed. Install it to use the full IFC parser path.") from exc
    return ifcopenshell


def _geometry_bbox_from_ifcopenshell(entity, geom_settings) -> dict[str, float] | None:
    try:
        import ifcopenshell.geom  # type: ignore
    except ImportError:
        return None

    try:
        shape = ifcopenshell.geom.create_shape(geom_settings, entity)
    except Exception:
        return None

    verts = list(getattr(getattr(shape, "geometry", None), "verts", []) or [])
    if len(verts) < 3:
        return None

    xs = verts[0::3]
    ys = verts[1::3]
    zs = verts[2::3]
    min_x = min(xs) * 1000.0
    max_x = max(xs) * 1000.0
    min_y = min(ys) * 1000.0
    max_y = max(ys) * 1000.0
    min_z = min(zs) * 1000.0
    max_z = max(zs) * 1000.0

    return {
        "geometry_bbox_min_x_mm": min_x,
        "geometry_bbox_max_x_mm": max_x,
        "geometry_bbox_min_y_mm": min_y,
        "geometry_bbox_max_y_mm": max_y,
        "geometry_bbox_min_z_mm": min_z,
        "geometry_bbox_max_z_mm": max_z,
        "geometry_bbox_width_mm": max_x - min_x,
        "geometry_bbox_depth_mm": max_y - min_y,
        "geometry_bbox_height_mm": max_z - min_z,
    }


def _append_derived_fact(
    target: list[NormalizedDerivedFact],
    *,
    fact_id: str,
    parameter: str,
    value: float,
    unit: str,
    source_property: str,
    description: str,
    source_element_id: str | None = None,
    source_element_label: str | None = None,
) -> None:
    target.append(
        NormalizedDerivedFact(
            fact_id=fact_id,
            parameter=parameter,
            value=value,
            unit=unit,
            source_element_id=source_element_id,
            source_element_label=source_element_label,
            source_property=source_property,
            description=description,
        )
    )


def _placement_from_ifcopenshell(local_placement, level: NormalizedLevel) -> NormalizedPlacement:
    def axis_coords(axis_placement):
        if axis_placement is None:
            return 0.0, 0.0, 0.0, 0.0
        coords = list(axis_placement.Location.Coordinates)
        if len(coords) == 2:
            coords.append(0.0)
        rotation_deg = 0.0
        ref_direction = getattr(axis_placement, "RefDirection", None)
        if ref_direction:
            direction = list(ref_direction.DirectionRatios)
            rotation_deg = math.degrees(math.atan2(direction[1], direction[0]))
        return coords[0] * 1000.0, coords[1] * 1000.0, coords[2] * 1000.0, rotation_deg

    if local_placement is None:
        return NormalizedPlacement(level_id=level.level_id, level_name=level.name, x_mm=0.0, y_mm=0.0, z_mm=level.elevation_mm)

    parent = _placement_from_ifcopenshell(local_placement.PlacementRelTo, level) if local_placement.PlacementRelTo else NormalizedPlacement(level_id=level.level_id, level_name=level.name, x_mm=0.0, y_mm=0.0, z_mm=0.0)
    axis_x, axis_y, axis_z, rotation_deg = axis_coords(local_placement.RelativePlacement)
    return NormalizedPlacement(
        level_id=level.level_id,
        level_name=level.name,
        x_mm=parent.x_mm + axis_x,
        y_mm=parent.y_mm + axis_y,
        z_mm=parent.z_mm + axis_z,
        rotation_deg=parent.rotation_deg + rotation_deg,
    )


def ingest_ifc_to_normalized_project_full(ifc_path: Path) -> NormalizedProject:
    ifcopenshell = _ifcopenshell_required()
    import ifcopenshell.geom  # type: ignore

    model = ifcopenshell.open(str(ifc_path))
    geom_settings = ifcopenshell.geom.settings()
    geom_settings.set(geom_settings.USE_WORLD_COORDS, True)

    project = model.by_type("IfcProject")[0]
    project_id = project.GlobalId
    project_name = project.Name or "IFC Project"

    storey_levels: dict[object, NormalizedLevel] = {}
    for storey in model.by_type("IfcBuildingStorey"):
        level_id = f"Storey_{storey.id()}"
        elevation_mm = float(storey.Elevation or 0.0) * 1000.0
        storey_levels[storey] = NormalizedLevel(level_id=level_id, name=storey.Name or level_id, elevation_mm=elevation_mm)

    storey_space_refs: dict[object, list[object]] = defaultdict(list)
    for rel in model.by_type("IfcRelAggregates"):
        relating = rel.RelatingObject
        if relating and relating.is_a("IfcBuildingStorey"):
            for obj in rel.RelatedObjects or []:
                if obj.is_a("IfcSpace"):
                    storey_space_refs[relating].append(obj)

    storey_element_refs: dict[object, list[object]] = defaultdict(list)
    for rel in model.by_type("IfcRelContainedInSpatialStructure"):
        container = rel.RelatingStructure
        if container and container.is_a("IfcBuildingStorey"):
            storey_element_refs[container].extend(rel.RelatedElements or [])

    element_to_spaces: dict[int, set[int]] = defaultdict(set)
    for rel in model.by_type("IfcRelSpaceBoundary"):
        space = rel.RelatingSpace
        element = rel.RelatedBuildingElement
        if space and element:
            element_to_spaces[element.id()].add(space.id())

    placement_owner: dict[int, object] = {}
    for entity in model.by_type("IfcProduct"):
        if getattr(entity, "ObjectPlacement", None):
            placement_owner[entity.ObjectPlacement.id()] = entity

    def resolve_host_from_product(entity) -> str | None:
        placement = getattr(entity, "ObjectPlacement", None)
        current = getattr(placement, "PlacementRelTo", None)
        while current:
            owner = placement_owner.get(current.id())
            if owner:
                return f"ifc_{owner.id()}"
            current = getattr(current, "PlacementRelTo", None)
        return None

    units: list[NormalizedUnit] = []
    for storey, level in storey_levels.items():
        unit_id = re.sub(r"[^A-Za-z0-9]+", "_", level.name).strip("_") or level.level_id
        normalized_space_ids: dict[int, str] = {}
        spaces: list[NormalizedSpace] = []

        for space in storey_space_refs.get(storey, []):
            placement = _placement_from_ifcopenshell(space.ObjectPlacement, level)
            long_name = getattr(space, "LongName", None)
            space_name = long_name or space.Name or f"Space_{space.id()}"
            normalized_space_id = f"{unit_id}_space_{space.id()}"
            normalized_space_ids[space.id()] = normalized_space_id
            geometry_bbox = _geometry_bbox_from_ifcopenshell(space, geom_settings) or {}
            spaces.append(
                NormalizedSpace(
                    space_id=normalized_space_id,
                    unit_id=unit_id,
                    name=space_name,
                    room_type=space_name,
                    level_id=level.level_id,
                    contained_in_unit=unit_id,
                    placement=placement,
                    source_scene=f"#{space.id()}",
                    source_room_id=space.Name or f"#{space.id()}",
                    raw_properties={
                        "ifc_entity_id": f"#{space.id()}",
                        "ifc_name": space.Name,
                        "ifc_long_name": long_name,
                        "ifc_composition_type": str(getattr(space, "CompositionType", "")) or None,
                        "compliance_room_type": _classify_compliance_room_type(space_name),
                        **geometry_bbox,
                    },
                )
            )

        shared_space_pairs: dict[str, set[str]] = defaultdict(set)
        elements_by_space: dict[str, list[NormalizedElement]] = defaultdict(list)
        derived_facts_by_space: dict[str, list[NormalizedDerivedFact]] = defaultdict(list)

        for element in storey_element_refs.get(storey, []):
            ifc_type = element.is_a().upper()
            if ifc_type not in SUPPORTED_PRODUCT_TYPES:
                continue
            semantic_type, revit_category = SUPPORTED_PRODUCT_TYPES[ifc_type]
            placement = _placement_from_ifcopenshell(getattr(element, "ObjectPlacement", None), level)
            related_space_ids = sorted(element_to_spaces.get(element.id(), set()))
            normalized_related_spaces = [normalized_space_ids[space_id] for space_id in related_space_ids if space_id in normalized_space_ids]
            contained_space = normalized_related_spaces[0] if normalized_related_spaces else None
            geometry_bbox = _geometry_bbox_from_ifcopenshell(element, geom_settings) or {}
            raw_properties = {
                "ifc_entity_id": f"#{element.id()}",
                "ifc_guid": getattr(element, "GlobalId", None),
                "overall_height_m": getattr(element, "OverallHeight", None),
                "overall_width_m": getattr(element, "OverallWidth", None),
                "tag": getattr(element, "Tag", None),
                **geometry_bbox,
            }
            if ifc_type == "IFCDOOR" and "geometry_bbox_width_mm" in geometry_bbox:
                raw_properties.setdefault("width_mm", geometry_bbox["geometry_bbox_width_mm"])
                raw_properties.setdefault("height_mm", geometry_bbox["geometry_bbox_height_mm"])
            if ifc_type == "IFCWINDOW" and "geometry_bbox_min_z_mm" in geometry_bbox:
                raw_properties.setdefault("sill_height_mm", geometry_bbox["geometry_bbox_min_z_mm"])
                raw_properties.setdefault("height_mm", geometry_bbox["geometry_bbox_height_mm"])
            predefined_type = getattr(element, "PredefinedType", None)
            if predefined_type is not None:
                raw_properties["predefined_type"] = str(predefined_type)

            normalized_element = NormalizedElement(
                element_id=f"ifc_{element.id()}",
                source_label=element.Name or f"{ifc_type}_{element.id()}",
                semantic_type=semantic_type,
                ifc_type=ifc_type,
                revit_category=revit_category,
                contained_in_space=contained_space,
                hosted_by=resolve_host_from_product(element),
                adjacent_to=[space_id for space_id in normalized_related_spaces if space_id != contained_space],
                placement=placement,
                raw_properties={key: value for key, value in raw_properties.items() if value is not None},
            )
            target_space = contained_space or (spaces[0].space_id if spaces else None)
            if not target_space:
                continue
            elements_by_space[target_space].append(normalized_element)

            fact_index = len(derived_facts_by_space[target_space]) + 1
            if raw_properties.get("overall_width_m") is not None:
                _append_derived_fact(
                    derived_facts_by_space[target_space],
                    fact_id=f"{normalized_element.element_id}_fact_{fact_index:02d}",
                    parameter="ifc_overall_width",
                    value=float(raw_properties["overall_width_m"]) * 1000.0,
                    unit="mm",
                    source_element_id=normalized_element.element_id,
                    source_element_label=normalized_element.source_label,
                    source_property="overall_width_m",
                    description=f"{ifc_type} overall width",
                )
                fact_index += 1
            if raw_properties.get("overall_height_m") is not None:
                _append_derived_fact(
                    derived_facts_by_space[target_space],
                    fact_id=f"{normalized_element.element_id}_fact_{fact_index:02d}",
                    parameter="ifc_overall_height",
                    value=float(raw_properties["overall_height_m"]) * 1000.0,
                    unit="mm",
                    source_element_id=normalized_element.element_id,
                    source_element_label=normalized_element.source_label,
                    source_property="overall_height_m",
                    description=f"{ifc_type} overall height",
                )
                fact_index += 1
            if "geometry_bbox_width_mm" in geometry_bbox:
                _append_derived_fact(
                    derived_facts_by_space[target_space],
                    fact_id=f"{normalized_element.element_id}_fact_{fact_index:02d}",
                    parameter="ifc_geometry_bbox_width",
                    value=geometry_bbox["geometry_bbox_width_mm"],
                    unit="mm",
                    source_element_id=normalized_element.element_id,
                    source_element_label=normalized_element.source_label,
                    source_property="geometry_bbox_width_mm",
                    description=f"{ifc_type} geometry bounding-box width",
                )
                fact_index += 1
            if "geometry_bbox_height_mm" in geometry_bbox:
                _append_derived_fact(
                    derived_facts_by_space[target_space],
                    fact_id=f"{normalized_element.element_id}_fact_{fact_index:02d}",
                    parameter="ifc_geometry_bbox_height",
                    value=geometry_bbox["geometry_bbox_height_mm"],
                    unit="mm",
                    source_element_id=normalized_element.element_id,
                    source_element_label=normalized_element.source_label,
                    source_property="geometry_bbox_height_mm",
                    description=f"{ifc_type} geometry bounding-box height",
                )
                fact_index += 1
            if ifc_type == "IFCWINDOW" and "geometry_bbox_min_z_mm" in geometry_bbox:
                _append_derived_fact(
                    derived_facts_by_space[target_space],
                    fact_id=f"{normalized_element.element_id}_fact_{fact_index:02d}",
                    parameter="window_sill_height",
                    value=geometry_bbox["geometry_bbox_min_z_mm"],
                    unit="mm",
                    source_element_id=normalized_element.element_id,
                    source_element_label=normalized_element.source_label,
                    source_property="geometry_bbox_min_z_mm",
                    description="Window sill height derived from IFC shape bounding box",
                )
                fact_index += 1

            for first_space in normalized_related_spaces:
                for second_space in normalized_related_spaces:
                    if first_space != second_space:
                        shared_space_pairs[first_space].add(second_space)

        for space in spaces:
            space.adjacent_to = sorted(shared_space_pairs.get(space.space_id, set()))
            space.elements = sorted(elements_by_space.get(space.space_id, []), key=lambda e: e.element_id)
            space.derived_facts = derived_facts_by_space.get(space.space_id, [])
            geometry_bbox = space.raw_properties
            width_mm = geometry_bbox.get("geometry_bbox_width_mm")
            depth_mm = geometry_bbox.get("geometry_bbox_depth_mm")
            height_mm = geometry_bbox.get("geometry_bbox_height_mm")
            if isinstance(width_mm, (int, float)) and isinstance(depth_mm, (int, float)):
                longer_mm = max(float(width_mm), float(depth_mm))
                shorter_mm = min(float(width_mm), float(depth_mm))
                approx_area_m2 = (float(width_mm) * float(depth_mm)) / 1_000_000.0
                fact_index = len(space.derived_facts) + 1
                _append_derived_fact(
                    space.derived_facts,
                    fact_id=f"{space.space_id}_fact_{fact_index:02d}",
                    parameter="ifc_space_bbox_length",
                    value=longer_mm,
                    unit="mm",
                    source_property="geometry_bbox_width_depth_mm",
                    description="Space long dimension derived from IFC shape bounding box",
                )
                fact_index += 1
                _append_derived_fact(
                    space.derived_facts,
                    fact_id=f"{space.space_id}_fact_{fact_index:02d}",
                    parameter="ifc_space_bbox_width",
                    value=shorter_mm,
                    unit="mm",
                    source_property="geometry_bbox_width_depth_mm",
                    description="Space short dimension derived from IFC shape bounding box",
                )
                fact_index += 1
                _append_derived_fact(
                    space.derived_facts,
                    fact_id=f"{space.space_id}_fact_{fact_index:02d}",
                    parameter="ifc_space_bbox_area",
                    value=approx_area_m2,
                    unit="m2",
                    source_property="geometry_bbox_width_depth_mm",
                    description="Approximate space footprint area derived from IFC shape bounding box",
                )
                fact_index += 1
                if space.raw_properties.get("compliance_room_type") == "Residential Bedroom":
                    _append_derived_fact(
                        space.derived_facts,
                        fact_id=f"{space.space_id}_fact_{fact_index:02d}",
                        parameter="bedroom_length",
                        value=longer_mm / 1000.0,
                        unit="m",
                        source_property="geometry_bbox_width_depth_mm",
                        description="Bedroom length derived from IFC shape bounding box",
                    )
                    fact_index += 1
                    _append_derived_fact(
                        space.derived_facts,
                        fact_id=f"{space.space_id}_fact_{fact_index:02d}",
                        parameter="bedroom_width",
                        value=shorter_mm / 1000.0,
                        unit="m",
                        source_property="geometry_bbox_width_depth_mm",
                        description="Bedroom width derived from IFC shape bounding box",
                    )
                    fact_index += 1
                    _append_derived_fact(
                        space.derived_facts,
                        fact_id=f"{space.space_id}_fact_{fact_index:02d}",
                        parameter="bedroom_area",
                        value=approx_area_m2,
                        unit="m2",
                        source_property="geometry_bbox_width_depth_mm",
                        description="Bedroom area derived from IFC shape bounding box",
                    )
                    fact_index += 1
            if isinstance(height_mm, (int, float)):
                _append_derived_fact(
                    space.derived_facts,
                    fact_id=f"{space.space_id}_fact_{len(space.derived_facts) + 1:02d}",
                    parameter="ifc_space_bbox_height",
                    value=float(height_mm),
                    unit="mm",
                    source_property="geometry_bbox_height_mm",
                    description="Space height derived from IFC shape bounding box",
                )

        units.append(
            NormalizedUnit(
                unit_id=unit_id,
                name=level.name,
                level_id=level.level_id,
                contained_in_project=project_id,
                source_manifest=ifc_path.name,
                spaces=spaces,
                metadata={
                    "source_scope": "ifc_storey",
                    "ifc_entity_id": f"#{storey.id()}",
                    "contained_element_count": len(storey_element_refs.get(storey, [])),
                    "space_count": len(spaces),
                    "parser": "ifcopenshell",
                },
            )
        )

    return NormalizedProject(
        project_id=project_id,
        name=project_name,
        source_format="ifc_ifcopenshell_ingestion",
        levels=list(storey_levels.values()),
        units=units,
        metadata={
            "source_ifc": str(ifc_path),
            "ingestion_method": "ifcopenshell",
            "supported_ifc_entities": sorted(SUPPORTED_PRODUCT_TYPES),
            "notes": [
                "This ingestion path uses ifcopenshell for IFC entity access and placement traversal.",
                "Contained space assignment is derived from IfcRelSpaceBoundary when available.",
            ],
        },
    )
