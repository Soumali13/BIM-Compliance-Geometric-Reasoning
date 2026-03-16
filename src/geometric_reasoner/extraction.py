from __future__ import annotations

from geometric_reasoner.bim_normalized_models import NormalizedSpace
from geometric_reasoner.shared_data_models import GeometricFact, Scene, SceneElement


FACT_MAPPINGS = {
    "door": {
        "side_clear_space_diameter_mm": ("door_side_clear_space_diameter", "Door-side clear space diameter"),
        "side_clear_space_perpendicular_swing_mm": (
            "door_side_clear_space_perpendicular_swing",
            "Door-side clear space perpendicular dimension for swinging door",
        ),
        "side_clear_space_perpendicular_sliding_mm": (
            "door_side_clear_space_perpendicular_sliding",
            "Door-side clear space perpendicular dimension for sliding door",
        ),
        "side_clear_space_perpendicular_other_mm": (
            "door_side_clear_space_perpendicular_other",
            "Door-side clear space perpendicular dimension for other door cases",
        ),
        "latch_clearance_perpendicular_mm": (
            "sliding_door_latch_clearance_perpendicular",
            "Sliding door latch-side clearance for perpendicular approach",
        ),
        "latch_clearance_lateral_mm": (
            "sliding_door_latch_clearance_lateral",
            "Sliding door latch-side clearance for lateral approach",
        ),
    },
    "floor_space": {
        "diameter_mm": ("turning_circle_diameter", "Turning diameter"),
        "length_mm": ("clear_floor_space_length", "Clear floor space length"),
        "width_mm": ("clear_floor_space_width", "Clear floor space width"),
        "kitchen_diameter_mm": ("kitchen_clear_floor_space_diameter", "Kitchen clear floor space diameter"),
        "balcony_diameter_mm": ("balcony_clear_floor_space_diameter", "Balcony clear floor space diameter"),
        "closet_front_diameter_mm": ("closet_front_clear_floor_space_diameter", "Closet front clear floor space diameter"),
    },
    "lavatory": {
        "rim_height_mm": ("lavatory_rim_height", "Lavatory rim height"),
        "side_wall_distance_mm": ("lavatory_side_wall_distance", "Lavatory side-wall clearance"),
        "trap_bottom_height_mm": ("lavatory_trap_bottom_height", "Lavatory trap bottom height"),
        "trap_entry_back_wall_distance_mm": (
            "lavatory_trap_entry_back_wall_distance",
            "Lavatory trap entry distance from back wall",
        ),
    },
    "water_closet": {
        "rear_wall_clearance_mm": ("water_closet_rear_wall_clearance", "Water closet rear-wall clearance"),
        "side_clearance_mm": ("water_closet_side_clearance", "Water closet side clearance"),
        "to_lavatory_trap_distance_mm": (
            "water_closet_to_lavatory_trap_distance",
            "Water closet to lavatory trap distance",
        ),
        "side_wall_or_equipment_distance_mm": (
            "water_closet_side_wall_or_equipment_distance",
            "Water closet to side wall or equipment distance",
        ),
        "clear_space_length_mm": ("water_closet_clear_space_length", "Water closet clear-space length"),
        "clear_space_width_mm": ("water_closet_clear_space_width", "Water closet clear-space width"),
        "rear_reinforcement_width_mm": (
            "water_closet_rear_reinforcement_width",
            "Water closet rear reinforcement width",
        ),
        "rear_reinforcement_height_mm": (
            "water_closet_rear_reinforcement_height",
            "Water closet rear reinforcement height",
        ),
    },
    "shower": {
        "floor_width_mm": ("shower_floor_width", "Shower floor width"),
        "floor_length_mm": ("shower_floor_length", "Shower floor length"),
        "front_clearance_width_mm": ("shower_front_clearance_width", "Shower front clearance width"),
        "front_clearance_length_mm": ("shower_front_clearance_length", "Shower front clearance length"),
        "wall_reinforcement_height_mm": (
            "bathtub_shower_reinforcement_height",
            "Shower wall reinforcement height",
        ),
    },
    "towel_rack": {
        "height_mm": ("towel_rack_height", "Towel rack height"),
    },
    "control": {
        "height_mm": ("control_height", "Control mounting height"),
        "inside_corner_distance_mm": ("control_inside_corner_distance", "Control distance from inside corner"),
    },
    "window": {
        "sill_height_mm": ("window_sill_height", "Window sill height"),
    },
    "bedroom": {
        "area_m2": ("bedroom_area", "Bedroom area", "m2"),
        "length_m": ("bedroom_length", "Bedroom length", "m"),
        "width_m": ("bedroom_width", "Bedroom width", "m"),
    },
    "kitchen_sink": {
        "trap_bottom_height_mm": ("kitchen_sink_trap_bottom_height", "Kitchen sink trap bottom height"),
    },
    "closet": {
        "rod_height_mm": ("closet_rod_height", "Closet rod height"),
    },
}

EXPECTED_ELEMENT_TYPES_BY_ROOM_TYPE = {
    "Residential Bathroom": {"floor_space", "lavatory", "water_closet", "shower"},
    "Residential Washroom": {"floor_space", "lavatory", "water_closet"},
    "Residential Corridor": {"floor_space"},
    "Residential Door Area": {"door"},
    "Residential Controls": {"control"},
    "Residential Bedroom": {"bedroom", "window"},
    "Residential Kitchen": {"floor_space", "kitchen_sink"},
    "Residential Balcony": {"floor_space"},
    "Residential Living Room": {"window"},
    "Residential Dining Room": {"window"},
    "Hotel Bathroom": {"towel_rack"},
    "Hotel Closet": {"floor_space", "closet"},
    "Hotel Suite Entrance": {"door"},
}

PARAMETER_TO_ELEMENT_TYPES: dict[str, set[str]] = {}
for element_type, mappings in FACT_MAPPINGS.items():
    for mapping in mappings.values():
        parameter = mapping[0]
        PARAMETER_TO_ELEMENT_TYPES.setdefault(parameter, set()).add(element_type)


def extract_geometric_facts(scene: Scene) -> list[GeometricFact]:
    facts: list[GeometricFact] = []

    for element in scene.elements:
        mappings = FACT_MAPPINGS.get(element.type, {})
        for measurement, mapping in mappings.items():
            if len(mapping) == 2:
                parameter, description = mapping
                unit = "mm"
            else:
                parameter, description, unit = mapping
            raw_value = getattr(element, measurement, None)
            if raw_value is None:
                continue

            facts.append(
                GeometricFact(
                    parameter=parameter,
                    value=float(raw_value),
                    unit=unit,
                    source_element=element.label,
                    source_measurement=measurement,
                    description=description,
                )
            )

    return facts


def compliance_room_type_for_normalized_space(space: NormalizedSpace) -> str | None:
    compliance_room_type = space.raw_properties.get("compliance_room_type")
    if isinstance(compliance_room_type, str) and compliance_room_type:
        return compliance_room_type
    return space.room_type if space.room_type in EXPECTED_ELEMENT_TYPES_BY_ROOM_TYPE else None


def normalized_space_to_scene(space: NormalizedSpace) -> Scene:
    room_type = compliance_room_type_for_normalized_space(space) or space.room_type
    elements: list[SceneElement] = []

    for element in space.elements:
        payload = {
            "type": element.semantic_type,
            "label": element.source_label,
            **element.raw_properties,
        }
        if element.semantic_type == "window" and "sill_height_mm" not in payload:
            payload["sill_height_mm"] = element.placement.z_mm
        if element.semantic_type == "door" and "width_mm" not in payload:
            width_m = element.raw_properties.get("overall_width_m")
            if isinstance(width_m, (int, float)):
                payload["width_mm"] = float(width_m) * 1000.0

        elements.append(SceneElement.model_validate(payload))

    return Scene(room_id=space.space_id, room_type=room_type, elements=elements)


def extract_geometric_facts_from_normalized_space(space: NormalizedSpace) -> list[GeometricFact]:
    facts: list[GeometricFact] = []
    seen: set[tuple[str, str, str]] = set()
    seen_parameter_sources: set[tuple[str, str]] = set()

    for derived_fact in space.derived_facts:
        source_element = derived_fact.source_element_label or derived_fact.source_element_id or "derived_space_fact"
        key = (derived_fact.parameter, source_element, derived_fact.source_property)
        seen.add(key)
        seen_parameter_sources.add((derived_fact.parameter, source_element))
        facts.append(
            GeometricFact(
                parameter=derived_fact.parameter,
                value=derived_fact.value,
                unit=derived_fact.unit,
                source_element=source_element,
                source_measurement=derived_fact.source_property,
                description=derived_fact.description,
            )
        )

    for scene_fact in extract_geometric_facts(normalized_space_to_scene(space)):
        key = (scene_fact.parameter, scene_fact.source_element, scene_fact.source_measurement)
        if key in seen or (scene_fact.parameter, scene_fact.source_element) in seen_parameter_sources:
            continue
        seen.add(key)
        seen_parameter_sources.add((scene_fact.parameter, scene_fact.source_element))
        facts.append(scene_fact)

    return facts


def expected_element_types_for_room(room_type: str) -> set[str]:
    return EXPECTED_ELEMENT_TYPES_BY_ROOM_TYPE.get(room_type, set())


def element_types_for_parameter(parameter: str) -> set[str]:
    return PARAMETER_TO_ELEMENT_TYPES.get(parameter, set())
