from __future__ import annotations

import json
import re
from pathlib import Path

from geometric_reasoner.shared_data_models import ArticleChunk, CodeConstraint


def _normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


def _mm_value(raw: str) -> float:
    return float(raw.replace(" ", ""))


def _float_value(raw: str) -> float:
    return float(raw.replace(" ", "").replace(",", "."))


def _build_constraint(
    article: ArticleChunk,
    *,
    parameter: str,
    operator: str,
    value: float,
    room_types: list[str],
    unit: str = "mm",
) -> CodeConstraint:
    return CodeConstraint(
        article=article.article,
        title=article.title,
        parameter=parameter,
        operator=operator,
        value=value,
        unit=unit,
        citation_text=article.text,
        room_types=room_types,
        authority=article.authority,
        jurisdiction=article.jurisdiction,
        priority=article.priority,
        effective_date=article.effective_date,
        amends_article=article.amends_article_id,
        patch_action=article.patch_action,
        applies_if=article.applies_if,
    )


def _find_mm(text: str, pattern: str) -> float:
    match = re.search(pattern, text)
    if not match:
        raise ValueError(f"Could not derive constraint from pattern: {pattern}")
    return _mm_value(match.group(1))


def _find_float(text: str, pattern: str) -> float:
    match = re.search(pattern, text)
    if not match:
        raise ValueError(f"Could not derive constraint from pattern: {pattern}")
    return _float_value(match.group(1))


def _derive_from_3_8_4_2(article: ArticleChunk) -> list[CodeConstraint]:
    text = _normalize_whitespace(article.text)
    diameter = _find_mm(text, r"not less than a\)\s+([\d ]+) mm in diameter")
    return [
        _build_constraint(
            article,
            parameter="turning_circle_diameter",
            operator=">=",
            value=diameter,
            room_types=["Residential Corridor"],
        )
    ]


def _derive_from_3_8_4_5(article: ArticleChunk) -> list[CodeConstraint]:
    text = _normalize_whitespace(article.text)
    return [
        _build_constraint(
            article,
            parameter="water_closet_rear_wall_clearance",
            operator=">=",
            value=_find_mm(text, r"rear wall clearance not less than a\)\s+([\d ]+) mm long"),
            room_types=["Residential Washroom"],
        ),
        _build_constraint(
            article,
            parameter="water_closet_side_clearance",
            operator=">=",
            value=_find_mm(text, r"side wall is\s+([\d ]+) mm to"),
            room_types=["Residential Washroom"],
        ),
        _build_constraint(
            article,
            parameter="water_closet_side_clearance",
            operator="<=",
            value=_find_mm(text, r"to\s+([\d ]+) mm"),
            room_types=["Residential Washroom"],
        ),
        _build_constraint(
            article,
            parameter="side_wall_length",
            operator=">=",
            value=_find_mm(text, r"side wall is not less than\s+([\d ]+) mm long"),
            room_types=["Residential Washroom"],
        ),
        _build_constraint(
            article,
            parameter="lavatory_side_wall_distance",
            operator=">=",
            value=_find_mm(text, r"distance between the centre line of the fixture and any side wall is not less than\s+([\d ]+) mm"),
            room_types=["Residential Washroom"],
        ),
        _build_constraint(
            article,
            parameter="lavatory_rim_height",
            operator="<=",
            value=_find_mm(text, r"rim height is not more than\s+([\d ]+) mm above the floor"),
            room_types=["Residential Washroom"],
        ),
        _build_constraint(
            article,
            parameter="turning_circle_diameter",
            operator=">=",
            value=_find_mm(text, r"round and not less than\s+([\d ]+) mm in diameter"),
            room_types=["Residential Washroom"],
        ),
        _build_constraint(
            article,
            parameter="lavatory_clear_space_length",
            operator=">=",
            value=_find_mm(text, r"the lavatory, not less than\s+([\d ]+) mm long"),
            room_types=["Residential Washroom"],
        ),
        _build_constraint(
            article,
            parameter="lavatory_clear_space_width",
            operator=">=",
            value=_find_mm(text, r"by not less than\s+([\d ]+) mm wide, the space being located in front of the lavatory"),
            room_types=["Residential Washroom"],
        ),
        _build_constraint(
            article,
            parameter="water_closet_clear_space_length",
            operator=">=",
            value=_find_mm(text, r"the water closet, not less than\s+([\d ]+) mm long"),
            room_types=["Residential Washroom"],
        ),
        _build_constraint(
            article,
            parameter="water_closet_clear_space_width",
            operator=">=",
            value=_find_mm(text, r"water closet, not less than [\d ]+ mm long, measured from the wall behind the water closet, by\s+([\d ]+) mm wide"),
            room_types=["Residential Washroom"],
        ),
        _build_constraint(
            article,
            parameter="water_closet_rear_reinforcement_width",
            operator=">=",
            value=_find_mm(text, r"over a surface not less than i\)\s+([\d ]+) mm wide, centered on the water closet"),
            room_types=["Residential Washroom"],
        ),
        _build_constraint(
            article,
            parameter="water_closet_rear_reinforcement_height",
            operator=">=",
            value=_find_mm(text, r"ii\)\s+([\d ]+) mm high, measured from the floor, or"),
            room_types=["Residential Washroom"],
        ),
        _build_constraint(
            article,
            parameter="water_closet_side_reinforcement_length",
            operator=">=",
            value=_find_mm(text, r"side wall, over a surface not less than\s+([\d ]+) mm long"),
            room_types=["Residential Washroom"],
        ),
        _build_constraint(
            article,
            parameter="water_closet_side_reinforcement_height",
            operator=">=",
            value=_find_mm(text, r"by\s+([\d ]+) mm high, measured from the floor, and"),
            room_types=["Residential Washroom"],
        ),
        _build_constraint(
            article,
            parameter="water_closet_secondary_rear_reinforcement_width",
            operator=">=",
            value=_find_mm(text, r"wall behind the water closet, over a surface not less than\s+([\d ]+) mm wide"),
            room_types=["Residential Washroom"],
        ),
        _build_constraint(
            article,
            parameter="water_closet_secondary_rear_reinforcement_height",
            operator=">=",
            value=_find_mm(text, r"by\s+([\d ]+) mm high, measured from the floor\. \(See Note A-3\.8\.4\.5\.\(4\)\.\)"),
            room_types=["Residential Washroom"],
        ),
        _build_constraint(
            article,
            parameter="bathtub_shower_reinforcement_height",
            operator=">=",
            value=_find_mm(text, r"over a height not less than\s+([\d ]+) mm measured from the floor"),
            room_types=["Residential Washroom"],
        ),
    ]


def _derive_from_3_8_4_3(article: ArticleChunk) -> list[CodeConstraint]:
    text = _normalize_whitespace(article.text)
    return [
        _build_constraint(
            article,
            parameter="sliding_door_latch_clearance_perpendicular",
            operator=">=",
            value=_find_mm(text, r"a\)\s+([\d ]+) mm beyond the edge of the door opening if the approach is perpendicular"),
            room_types=["Residential Door Area"],
        ),
        _build_constraint(
            article,
            parameter="sliding_door_latch_clearance_lateral",
            operator=">=",
            value=_find_mm(text, r"b\)\s+([\d ]+) mm beyond the edge of the door opening if the approach is parallel"),
            room_types=["Residential Door Area"],
        ),
        _build_constraint(
            article,
            parameter="door_side_clear_space_perpendicular_swing",
            operator=">=",
            value=_find_mm(text, r"i\)\s+([\d ]+) mm for a swinging door swinging away from the approach side"),
            room_types=["Residential Door Area"],
        ),
        _build_constraint(
            article,
            parameter="door_side_clear_space_perpendicular_sliding",
            operator=">=",
            value=_find_mm(text, r"ii\)\s+([\d ]+) mm for a sliding door if the approach is lateral"),
            room_types=["Residential Door Area"],
        ),
        _build_constraint(
            article,
            parameter="door_side_clear_space_perpendicular_other",
            operator=">=",
            value=_find_mm(text, r"iii\)\s+([\d ]+) mm in other cases"),
            room_types=["Residential Door Area"],
        ),
    ]


def _derive_from_3_8_4_4(article: ArticleChunk) -> list[CodeConstraint]:
    text = _normalize_whitespace(article.text)
    return [
        _build_constraint(
            article,
            parameter="control_height",
            operator=">=",
            value=_find_mm(text, r"mounted\s+([\d ]+) mm to"),
            room_types=["Residential Controls"],
        ),
        _build_constraint(
            article,
            parameter="control_height",
            operator="<=",
            value=_find_mm(text, r"mounted [\d ]+ mm to\s+([\d ]+) mm above the floor"),
            room_types=["Residential Controls"],
        ),
        _build_constraint(
            article,
            parameter="control_inside_corner_distance",
            operator=">=",
            value=_find_mm(text, r"distance not less than\s+([\d ]+) mm from the inside corner"),
            room_types=["Residential Controls"],
        ),
    ]


def _derive_from_3_8_5_2(article: ArticleChunk) -> list[CodeConstraint]:
    text = _normalize_whitespace(article.text)
    diameter = _find_mm(text, r"not less than a\)\s+([\d ]+) mm in diameter")
    return [
        _build_constraint(
            article,
            parameter="turning_circle_diameter",
            operator=">=",
            value=diameter,
            room_types=["Residential Corridor"],
        )
    ]


def _derive_from_3_8_5_3(article: ArticleChunk) -> list[CodeConstraint]:
    text = _normalize_whitespace(article.text)
    return [
        _build_constraint(
            article,
            parameter="sliding_door_latch_clearance_perpendicular",
            operator=">=",
            value=_find_mm(text, r"a\)\s+([\d ]+) mm beyond the edge of the door opening if the approach is perpendicular"),
            room_types=["Residential Door Area"],
        ),
        _build_constraint(
            article,
            parameter="sliding_door_latch_clearance_lateral",
            operator=">=",
            value=_find_mm(text, r"b\)\s+([\d ]+) mm beyond the edge of the door opening if the approach is lateral"),
            room_types=["Residential Door Area"],
        ),
        _build_constraint(
            article,
            parameter="door_side_clear_space_diameter",
            operator=">=",
            value=_find_mm(text, r"area not less than\s+([\d ]+) mm in diameter"),
            room_types=["Residential Door Area"],
        ),
        _build_constraint(
            article,
            parameter="door_side_clear_space_perpendicular_swing",
            operator=">=",
            value=_find_mm(text, r"i\)\s+([\d ]+) mm for a swinging door swinging away from the approach side"),
            room_types=["Residential Door Area"],
        ),
        _build_constraint(
            article,
            parameter="door_side_clear_space_perpendicular_sliding",
            operator=">=",
            value=_find_mm(text, r"ii\)\s+([\d ]+) mm for a sliding door if the approach is lateral"),
            room_types=["Residential Door Area"],
        ),
        _build_constraint(
            article,
            parameter="door_side_clear_space_perpendicular_other",
            operator=">=",
            value=_find_mm(text, r"iii\)\s+([\d ]+) mm in other cases"),
            room_types=["Residential Door Area"],
        ),
    ]


def _derive_from_3_8_5_4(article: ArticleChunk) -> list[CodeConstraint]:
    text = _normalize_whitespace(article.text)
    return [
        _build_constraint(
            article,
            parameter="control_height",
            operator=">=",
            value=_find_mm(text, r"mounted\s+([\d ]+) mm to"),
            room_types=["Residential Controls"],
        ),
        _build_constraint(
            article,
            parameter="control_height",
            operator="<=",
            value=_find_mm(text, r"mounted [\d ]+ mm to\s+([\d ]+) mm above the floor"),
            room_types=["Residential Controls"],
        ),
        _build_constraint(
            article,
            parameter="control_inside_corner_distance",
            operator=">=",
            value=_find_mm(text, r"distance not less than\s+([\d ]+) mm from the inside corner"),
            room_types=["Residential Controls"],
        ),
    ]


def _derive_from_3_8_5_5(article: ArticleChunk) -> list[CodeConstraint]:
    text = _normalize_whitespace(article.text)
    return [
        _build_constraint(
            article,
            parameter="water_closet_to_lavatory_trap_distance",
            operator=">=",
            value=_find_mm(text, r"centre line of the lavatory trap is not less than\s+([\d ]+) mm"),
            room_types=["Residential Bathroom"],
        ),
        _build_constraint(
            article,
            parameter="water_closet_side_wall_or_equipment_distance",
            operator=">=",
            value=_find_mm(text, r"any side wall or equipment is not less than\s+([\d ]+) mm"),
            room_types=["Residential Bathroom"],
        ),
        _build_constraint(
            article,
            parameter="lavatory_side_wall_distance",
            operator=">=",
            value=_find_mm(text, r"fixture and any side wall is not less than\s+([\d ]+) mm"),
            room_types=["Residential Bathroom"],
        ),
        _build_constraint(
            article,
            parameter="lavatory_trap_bottom_height",
            operator=">=",
            value=_find_mm(text, r"trap bottom is located\s+([\d ]+) mm to"),
            room_types=["Residential Bathroom"],
        ),
        _build_constraint(
            article,
            parameter="lavatory_trap_bottom_height",
            operator="<=",
            value=_find_mm(text, r"trap bottom is located [\d ]+ mm to\s+([\d ]+) mm above the floor"),
            room_types=["Residential Bathroom"],
        ),
        _build_constraint(
            article,
            parameter="lavatory_trap_entry_back_wall_distance",
            operator="<=",
            value=_find_mm(text, r"trap entrance is located not more than\s+([\d ]+) mm from the wall behind the lavatory"),
            room_types=["Residential Bathroom"],
        ),
        _build_constraint(
            article,
            parameter="shower_floor_width",
            operator=">=",
            value=_find_mm(text, r"floor surface of not less than\s+([\d ]+) mm by"),
            room_types=["Residential Bathroom"],
        ),
        _build_constraint(
            article,
            parameter="shower_floor_length",
            operator=">=",
            value=_find_mm(text, r"floor surface of not less than [\d ]+ mm by\s+([\d ]+) mm"),
            room_types=["Residential Bathroom"],
        ),
        _build_constraint(
            article,
            parameter="turning_circle_diameter",
            operator=">=",
            value=_find_mm(text, r"that is not less than\s+([\d ]+) mm in diameter"),
            room_types=["Residential Bathroom"],
        ),
        _build_constraint(
            article,
            parameter="shower_front_clearance_width",
            operator=">=",
            value=_find_mm(text, r"the shower, where provided, that is not less than\s+([\d ]+) mm by"),
            room_types=["Residential Bathroom"],
        ),
        _build_constraint(
            article,
            parameter="shower_front_clearance_length",
            operator=">=",
            value=_find_mm(text, r"the shower, where provided, that is not less than [\d ]+ mm by\s+([\d ]+) mm in front of the shower"),
            room_types=["Residential Bathroom"],
        ),
        _build_constraint(
            article,
            parameter="bathtub_front_clearance_length",
            operator=">=",
            value=_find_mm(text, r"the bathtub, where provided, that is not less than\s+([\d ]+) mm, measured from the faucets"),
            room_types=["Residential Bathroom"],
        ),
        _build_constraint(
            article,
            parameter="bathtub_front_clearance_width",
            operator=">=",
            value=_find_mm(text, r"measured from the faucets, by\s+([\d ]+) mm, measured perpendicularly to the bathtub"),
            room_types=["Residential Bathroom"],
        ),
        _build_constraint(
            article,
            parameter="bathtub_shower_reinforcement_height",
            operator=">=",
            value=_find_mm(text, r"in the walls around the bathtub or the shower, over a height not less than\s+([\d ]+) mm"),
            room_types=["Residential Bathroom"],
        ),
        _build_constraint(
            article,
            parameter="water_closet_rear_reinforcement_width",
            operator=">=",
            value=_find_mm(text, r"not less than i\)\s+([\d ]+) mm wide, centred on the floor flange"),
            room_types=["Residential Bathroom"],
        ),
        _build_constraint(
            article,
            parameter="water_closet_rear_reinforcement_height",
            operator=">=",
            value=_find_mm(text, r"ii\)\s+([\d ]+) mm high, measured from the floor"),
            room_types=["Residential Bathroom"],
        ),
    ]


def _derive_from_3_8_5_6(article: ArticleChunk) -> list[CodeConstraint]:
    text = _normalize_whitespace(article.text)
    area_match = re.search(r"area not less than\s+([\d.]+)\s*m²", text)
    if not area_match:
        raise ValueError("Could not derive bedroom area from Article 3.8.5.6")
    return [
        _build_constraint(
            article,
            parameter="bedroom_area",
            operator=">=",
            value=float(area_match.group(1)),
            room_types=["Residential Bedroom"],
            unit="m2",
        ),
        _build_constraint(
            article,
            parameter="bedroom_length",
            operator=">=",
            value=_find_mm(text, r"width not less than\s+([\d ]+) m"),
            room_types=["Residential Bedroom"],
            unit="m",
        ),
        _build_constraint(
            article,
            parameter="bedroom_width",
            operator=">=",
            value=_find_mm(text, r"length and a width not less than\s+([\d ]+) m"),
            room_types=["Residential Bedroom"],
            unit="m",
        ),
        _build_constraint(
            article,
            parameter="window_sill_height",
            operator="<=",
            value=_find_mm(text, r"not more than\s+([\d ]+) mm above the floor"),
            room_types=["Residential Bedroom"],
        ),
    ]


def _derive_from_3_8_5_7(article: ArticleChunk) -> list[CodeConstraint]:
    text = _normalize_whitespace(article.text)
    return [
        _build_constraint(
            article,
            parameter="kitchen_clear_floor_space_diameter",
            operator=">=",
            value=_find_mm(text, r"clear floor space not less than\s+([\d ]+) mm in diameter"),
            room_types=["Residential Kitchen"],
        ),
        _build_constraint(
            article,
            parameter="kitchen_sink_trap_bottom_height",
            operator="==",
            value=_find_mm(text, r"trap shall be located\s+([\d ]+) mm above the floor"),
            room_types=["Residential Kitchen"],
        ),
    ]


def _derive_from_3_8_5_8(article: ArticleChunk) -> list[CodeConstraint]:
    text = _normalize_whitespace(article.text)
    height = _find_mm(text, r"not more than\s+([\d ]+) mm above the floor")
    return [
        _build_constraint(article, parameter="window_sill_height", operator="<=", value=height, room_types=["Residential Living Room"]),
        _build_constraint(article, parameter="window_sill_height", operator="<=", value=height, room_types=["Residential Dining Room"]),
    ]


def _derive_from_3_8_5_9(article: ArticleChunk) -> list[CodeConstraint]:
    text = _normalize_whitespace(article.text)
    return [
        _build_constraint(
            article,
            parameter="balcony_clear_floor_space_diameter",
            operator=">=",
            value=_find_mm(text, r"clear floor space not less than\s+([\d ]+) mm in diameter"),
            room_types=["Residential Balcony"],
        )
    ]


def _derive_from_3_8_6_3(article: ArticleChunk) -> list[CodeConstraint]:
    text = _normalize_whitespace(article.text)
    return [
        _build_constraint(
            article,
            parameter="door_side_clear_space_diameter",
            operator=">=",
            value=_find_mm(text, r"not less than\s+([\d ]+) mm in diameter"),
            room_types=["Hotel Suite Entrance"],
        )
    ]


def _derive_from_3_8_6_4(article: ArticleChunk) -> list[CodeConstraint]:
    text = _normalize_whitespace(article.text)
    return [
        _build_constraint(
            article,
            parameter="towel_rack_height",
            operator="<=",
            value=_find_mm(text, r"not higher than\s+([\d ]+) mm above the floor"),
            room_types=["Hotel Bathroom"],
        )
    ]


def _derive_from_3_8_6_5(article: ArticleChunk) -> list[CodeConstraint]:
    text = _normalize_whitespace(article.text)
    return [
        _build_constraint(
            article,
            parameter="closet_front_clear_floor_space_diameter",
            operator=">=",
            value=_find_mm(text, r"clear floor space not less than\s+([\d ]+) mm in diameter"),
            room_types=["Hotel Closet"],
        ),
        _build_constraint(
            article,
            parameter="closet_rod_height",
            operator="<=",
            value=_find_mm(text, r"not more than\s+([\d ]+) mm above the floor"),
            room_types=["Hotel Closet"],
        ),
    ]


def _derive_from_mtl_11_018_x_article_14(article: ArticleChunk) -> list[CodeConstraint]:
    text = _normalize_whitespace(article.text)
    ratio = _find_float(text, r"at least\s+([\d.]+)%\s+of the total surface of the combined rooms") / 100.0
    return [
        _build_constraint(
            article,
            parameter="second_day_lighting_glazing_ratio",
            operator=">=",
            value=ratio,
            room_types=[
                "Residential Living Room",
                "Residential Bedroom",
                "Residential Dining Room",
                "Residential Kitchen",
            ],
            unit="ratio",
        )
    ]


def _derive_from_mtl_11_018_x_article_18(article: ArticleChunk) -> list[CodeConstraint]:
    text = _normalize_whitespace(article.text)
    return [
        _build_constraint(
            article,
            parameter="living_room_area",
            operator=">=",
            value=_find_float(text, r"([\d.]+)\s*m2,\s*with no dimension less than\s*[\d.]+\s*m,\s*if it is a living area"),
            room_types=["Residential Living Room"],
            unit="m2",
        ),
        _build_constraint(
            article,
            parameter="living_room_min_dimension",
            operator=">=",
            value=_find_float(text, r"13\.?5\s*m2,\s*with no dimension less than\s*([\d.]+)\s*m"),
            room_types=["Residential Living Room"],
            unit="m",
        ),
        _build_constraint(
            article,
            parameter="primary_bedroom_area",
            operator=">=",
            value=_find_float(text, r"5o\s*([\d.]+)\s*m2"),
            room_types=["Residential Bedroom"],
            unit="m2",
        ),
        _build_constraint(
            article,
            parameter="primary_bedroom_min_dimension",
            operator=">=",
            value=_find_float(text, r"5o\s*[\d.]+\s*m2,\s*with no dimension less than\s*([\d.]+)\s*m"),
            room_types=["Residential Bedroom"],
            unit="m",
        ),
        _build_constraint(
            article,
            parameter="secondary_bedroom_area",
            operator=">=",
            value=_find_float(text, r"6o\s*([\d.]+)\s*m2"),
            room_types=["Residential Bedroom"],
            unit="m2",
        ),
        _build_constraint(
            article,
            parameter="secondary_bedroom_min_dimension",
            operator=">=",
            value=_find_float(text, r"6o\s*[\d.]+\s*m2,\s*with no dimension less than\s*([\d.]+)\s*m"),
            room_types=["Residential Bedroom"],
            unit="m",
        ),
    ]


def _derive_from_mtl_11_018_x_article_23(article: ArticleChunk) -> list[CodeConstraint]:
    text = _normalize_whitespace(article.text)
    area_threshold = _find_float(text, r"more than\s*([\d.]+)\s*m2")
    return [
        _build_constraint(
            article,
            parameter="green_roof_trigger_area",
            operator=">",
            value=area_threshold,
            room_types=[],
            unit="m2",
        ),
        _build_constraint(
            article,
            parameter="green_roof_trigger_storeys",
            operator=">",
            value=_find_float(text, r"more than\s*([\d.]+)\s*floors"),
            room_types=[],
            unit="storeys",
        ),
        _build_constraint(
            article,
            parameter="green_roof_trigger_max_slope_ratio",
            operator="<=",
            value=_find_float(text, r"\(2:12\)\s*or\s*([\d.]+)%") / 100.0,
            room_types=[],
            unit="ratio",
        ),
        _build_constraint(
            article,
            parameter="green_roof_required",
            operator="==",
            value=1.0,
            room_types=[],
            unit="bool",
        ),
    ]


def _derive_from_mtl_11_018_article_14(article: ArticleChunk) -> list[CodeConstraint]:
    text = _normalize_whitespace(article.text)
    living_ratio = _find_float(text, r"1°\s*([\d.]+)%\s*of the area served by the following rooms")
    other_ratio = _find_float(text, r"2°\s*([\d.]+)%\s*of the area served by rooms")
    room_house_ratio = _find_float(text, r"3°\s*([\d.]+)%\s*of the area served by a room in a room house")
    second_day_ratio = _find_float(text, r"glass surface providing natural lighting is not less than\s*([\d.]+)\s*%\s*of the total surface")
    second_day_distance = _find_float(text, r"situated not more than\s*([\d.]+)\s*m from that surface")

    return [
        _build_constraint(
            article,
            parameter="natural_lighting_glazing_ratio",
            operator=">=",
            value=living_ratio / 100.0,
            room_types=["Residential Living Room", "Residential Dining Room"],
            unit="ratio",
        ),
        _build_constraint(
            article,
            parameter="natural_lighting_glazing_ratio",
            operator=">=",
            value=other_ratio / 100.0,
            room_types=["Residential Bedroom"],
            unit="ratio",
        ),
        _build_constraint(
            article,
            parameter="room_house_natural_lighting_glazing_ratio",
            operator=">=",
            value=room_house_ratio / 100.0,
            room_types=[],
            unit="ratio",
        ),
        _build_constraint(
            article,
            parameter="second_day_lighting_glazing_ratio",
            operator=">=",
            value=second_day_ratio / 100.0,
            room_types=[
                "Residential Living Room",
                "Residential Dining Room",
                "Residential Bedroom",
            ],
            unit="ratio",
        ),
        _build_constraint(
            article,
            parameter="second_day_lighting_max_opening_distance",
            operator="<=",
            value=second_day_distance,
            room_types=[
                "Residential Living Room",
                "Residential Dining Room",
                "Residential Bedroom",
            ],
            unit="m",
        ),
    ]


def _derive_from_nbc_2020_3_8_3_8(article: ArticleChunk) -> list[CodeConstraint]:
    text = _normalize_whitespace(article.text)
    return [
        _build_constraint(
            article,
            parameter="control_height",
            operator=">=",
            value=_find_mm(text, r"mounted\s+([\d ]+) mm to"),
            room_types=["Residential Controls"],
        ),
        _build_constraint(
            article,
            parameter="control_height",
            operator="<=",
            value=_find_mm(text, r"mounted [\d ]+ mm to\s+([\d ]+) mm above the floor"),
            room_types=["Residential Controls"],
        ),
    ]


def _derive_from_nbc_2020_3_8_3_16(article: ArticleChunk) -> list[CodeConstraint]:
    text = _normalize_whitespace(article.text)
    return [
        _build_constraint(
            article,
            parameter="lavatory_side_wall_distance",
            operator=">=",
            value=_find_mm(text, r"distance between the centre line of the lavatory and any side wall is not less than\s+([\d ]+) mm"),
            room_types=["Residential Bathroom", "Residential Washroom"],
        ),
        _build_constraint(
            article,
            parameter="lavatory_clear_space_width",
            operator=">=",
            value=_find_mm(text, r"at least i\)\s+([\d ]+) mm wide, centred on the lavatory"),
            room_types=["Residential Bathroom", "Residential Washroom"],
        ),
        _build_constraint(
            article,
            parameter="lavatory_clear_space_length",
            operator=">=",
            value=_find_mm(text, r"ii\)\s+([\d ]+) mm long, of which no more than"),
            room_types=["Residential Bathroom", "Residential Washroom"],
        ),
        _build_constraint(
            article,
            parameter="lavatory_rim_height",
            operator="<=",
            value=_find_mm(text, r"rim height not more than\s+([\d ]+) mm above the floor"),
            room_types=["Residential Bathroom", "Residential Washroom"],
        ),
    ]


def _derive_from_nbc_2020_3_8_3_17(article: ArticleChunk) -> list[CodeConstraint]:
    text = _normalize_whitespace(article.text)
    shower_width = _find_mm(text, r"not less than\s+([\d ]+) mm wide and")
    return [
        _build_constraint(
            article,
            parameter="shower_floor_width",
            operator=">=",
            value=shower_width,
            room_types=["Residential Bathroom"],
        ),
        _build_constraint(
            article,
            parameter="shower_floor_length",
            operator=">=",
            value=_find_mm(text, r"mm wide and\s+([\d ]+) mm deep"),
            room_types=["Residential Bathroom"],
        ),
        _build_constraint(
            article,
            parameter="shower_front_clearance_length",
            operator=">=",
            value=_find_mm(text, r"entrance to the shower that is not less than\s+([\d ]+) mm deep"),
            room_types=["Residential Bathroom"],
        ),
        _build_constraint(
            article,
            parameter="shower_front_clearance_width",
            operator=">=",
            value=shower_width,
            room_types=["Residential Bathroom"],
        ),
    ]


def _derive_from_quebec_2015_2022_3_8_3_8(article: ArticleChunk) -> list[CodeConstraint]:
    text = _normalize_whitespace(article.text)
    return [
        _build_constraint(
            article,
            parameter="control_height",
            operator=">=",
            value=_find_mm(text, r"mounted\s+([\d ]+) mm to"),
            room_types=["Residential Controls"],
        ),
        _build_constraint(
            article,
            parameter="control_height",
            operator="<=",
            value=_find_mm(text, r"mounted [\d ]+ mm to\s+([\d ]+) mm above the floor"),
            room_types=["Residential Controls"],
        ),
    ]


def _derive_from_quebec_2015_2022_3_8_3_15(article: ArticleChunk) -> list[CodeConstraint]:
    text = _normalize_whitespace(article.text)
    return [
        _build_constraint(
            article,
            parameter="lavatory_side_wall_distance",
            operator=">=",
            value=_find_mm(text, r"distance between the centre line of the lavatory and any side wall is not less than\s+([\d ]+) mm"),
            room_types=["Residential Bathroom", "Residential Washroom"],
        ),
        _build_constraint(
            article,
            parameter="lavatory_rim_height",
            operator="<=",
            value=_find_mm(text, r"rim height not more than\s+([\d ]+) mm above the floor"),
            room_types=["Residential Bathroom", "Residential Washroom"],
        ),
    ]


def _derive_from_quebec_2015_2022_3_8_3_16(article: ArticleChunk) -> list[CodeConstraint]:
    text = _normalize_whitespace(article.text)
    return [
        _build_constraint(
            article,
            parameter="shower_floor_width",
            operator=">=",
            value=_find_mm(text, r"not less than\s+([\d ]+) mm wide and"),
            room_types=["Residential Bathroom"],
        ),
        _build_constraint(
            article,
            parameter="shower_floor_length",
            operator=">=",
            value=_find_mm(text, r"mm wide and\s+([\d ]+) mm deep"),
            room_types=["Residential Bathroom"],
        ),
        _build_constraint(
            article,
            parameter="shower_front_clearance_length",
            operator=">=",
            value=_find_mm(text, r"entrance to the shower that is not less than\s+([\d ]+) mm deep"),
            room_types=["Residential Bathroom"],
        ),
    ]


def _derive_from_quebec_2015_2022_3_8_4_3(article: ArticleChunk) -> list[CodeConstraint]:
    text = _normalize_whitespace(article.text)
    return [
        _build_constraint(
            article,
            parameter="sliding_door_latch_clearance_perpendicular",
            operator=">=",
            value=_find_mm(text, r"a\)\s+([\d ]+) mm beyond the edge of the door opening if the approach is perpendicular"),
            room_types=["Residential Door Area"],
        ),
        _build_constraint(
            article,
            parameter="sliding_door_latch_clearance_lateral",
            operator=">=",
            value=_find_mm(text, r"b\)\s+([\d ]+) mm beyond the edge of the door opening if the approach is lateral"),
            room_types=["Residential Door Area"],
        ),
        _build_constraint(
            article,
            parameter="door_side_clear_space_perpendicular_swing",
            operator=">=",
            value=_find_mm(text, r"i\)\s+([\d ]+) mm if the door swings away from the approach side"),
            room_types=["Residential Door Area"],
        ),
        _build_constraint(
            article,
            parameter="door_side_clear_space_perpendicular_sliding",
            operator=">=",
            value=_find_mm(text, r"ii\)\s+([\d ]+) mm for a sliding door if the approach is lateral"),
            room_types=["Residential Door Area"],
        ),
        _build_constraint(
            article,
            parameter="door_side_clear_space_perpendicular_other",
            operator=">=",
            value=_find_mm(text, r"iii\)\s+([\d ]+) mm in other cases"),
            room_types=["Residential Door Area"],
        ),
    ]


ARTICLE_EXTRACTORS = {
    ("NBC_2020", "3.8.3.8"): _derive_from_nbc_2020_3_8_3_8,
    ("NBC_2020", "3.8.3.16"): _derive_from_nbc_2020_3_8_3_16,
    ("NBC_2020", "3.8.3.17"): _derive_from_nbc_2020_3_8_3_17,
    ("QUEBEC_2015_2022", "3.8.3.8"): _derive_from_quebec_2015_2022_3_8_3_8,
    ("QUEBEC_2015_2022", "3.8.3.15"): _derive_from_quebec_2015_2022_3_8_3_15,
    ("QUEBEC_2015_2022", "3.8.3.16"): _derive_from_quebec_2015_2022_3_8_3_16,
    ("QUEBEC_2015_2022", "3.8.4.3"): _derive_from_quebec_2015_2022_3_8_4_3,
    ("MTL_11_018", "14"): _derive_from_mtl_11_018_article_14,
    ("MTL_11_018_X", "14"): _derive_from_mtl_11_018_x_article_14,
    ("MTL_11_018_X", "18"): _derive_from_mtl_11_018_x_article_18,
    ("MTL_11_018_X", "23"): _derive_from_mtl_11_018_x_article_23,
    ("MTL_11_018_X", "27.1"): _derive_from_mtl_11_018_x_article_23,
    "3.8.4.2": _derive_from_3_8_4_2,
    "3.8.4.3": _derive_from_3_8_4_3,
    "3.8.4.4": _derive_from_3_8_4_4,
    "3.8.4.5": _derive_from_3_8_4_5,
    "3.8.5.2": _derive_from_3_8_5_2,
    "3.8.5.3": _derive_from_3_8_5_3,
    "3.8.5.4": _derive_from_3_8_5_4,
    "3.8.5.5": _derive_from_3_8_5_5,
    "3.8.5.6": _derive_from_3_8_5_6,
    "3.8.5.7": _derive_from_3_8_5_7,
    "3.8.5.8": _derive_from_3_8_5_8,
    "3.8.5.9": _derive_from_3_8_5_9,
    "3.8.6.3": _derive_from_3_8_6_3,
    "3.8.6.4": _derive_from_3_8_6_4,
    "3.8.6.5": _derive_from_3_8_6_5,
}


def derive_constraints_for_article(article: ArticleChunk) -> list[CodeConstraint]:
    extractor = ARTICLE_EXTRACTORS.get((article.authority, article.article)) or ARTICLE_EXTRACTORS.get(article.article)
    if extractor is None:
        return []
    try:
        return extractor(article)
    except ValueError:
        # First-pass corpora from other authorities can share article numbers while
        # still having text shapes that do not match the executable Quebec regexes.
        # Skip those chunks rather than crashing layered retrieval.
        return []


def derive_constraints_from_articles(articles: list[ArticleChunk]) -> list[CodeConstraint]:
    constraints: list[CodeConstraint] = []

    for article in articles:
        constraints.extend(derive_constraints_for_article(article))

    return constraints


def build_constraint_payload(articles: list[ArticleChunk], source: str, derived_from: str) -> dict:
    grouped: list[dict] = []
    constraints_by_article = derive_constraints_from_articles(articles)

    article_lookup = {(article.authority, article.article): article for article in articles}
    article_keys = sorted({(constraint.authority, constraint.article) for constraint in constraints_by_article})
    for authority, article_id in article_keys:
        article = article_lookup[(authority, article_id)]
        grouped.append(
            {
                "article": article.article,
                "article_id": article.article_id,
                "title": article.title,
                "authority": article.authority,
                "jurisdiction": article.jurisdiction,
                "priority": article.priority,
                "effective_date": article.effective_date,
                "amends_article": article.amends_article_id,
                "patch_action": article.patch_action,
                "applies_if": article.applies_if,
                "room_types": sorted(
                    {
                        room_type
                        for constraint in constraints_by_article
                        if constraint.authority == authority and constraint.article == article_id
                        for room_type in constraint.room_types
                    }
                ),
                "text": article.text,
                "constraints": [
                    {
                        "parameter": constraint.parameter,
                        "operator": constraint.operator,
                        "value": constraint.value,
                        "unit": constraint.unit,
                    }
                    for constraint in constraints_by_article
                    if constraint.authority == authority and constraint.article == article_id
                ],
            }
        )

    return {
        "source": source,
        "derived_from": derived_from,
        "articles": grouped,
    }


def write_constraint_payload(output_path: str | Path, payload: dict) -> None:
    Path(output_path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
