from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class NormalizedPlacement(BaseModel):
    level_id: str
    level_name: str
    x_mm: float
    y_mm: float
    z_mm: float = 0.0
    rotation_deg: float = 0.0


class NormalizedLevel(BaseModel):
    level_id: str
    name: str
    elevation_mm: float


class NormalizedDerivedFact(BaseModel):
    fact_id: str
    parameter: str
    value: float
    unit: str
    source_element_id: str | None = None
    source_element_label: str | None = None
    source_property: str
    description: str


class NormalizedElement(BaseModel):
    element_id: str
    source_label: str
    semantic_type: str
    ifc_type: str
    revit_category: str
    contained_in_space: str | None = None
    hosted_by: str | None = None
    adjacent_to: list[str] = Field(default_factory=list)
    placement: NormalizedPlacement
    raw_properties: dict[str, Any] = Field(default_factory=dict)


class NormalizedSpace(BaseModel):
    space_id: str
    unit_id: str
    name: str
    room_type: str
    ifc_type: str = "IfcSpace"
    revit_category: str = "Rooms"
    level_id: str
    contained_in_unit: str
    adjacent_to: list[str] = Field(default_factory=list)
    placement: NormalizedPlacement
    source_scene: str
    source_room_id: str
    raw_properties: dict[str, Any] = Field(default_factory=dict)
    elements: list[NormalizedElement] = Field(default_factory=list)
    derived_facts: list[NormalizedDerivedFact] = Field(default_factory=list)


class NormalizedUnit(BaseModel):
    unit_id: str
    name: str
    level_id: str
    contained_in_project: str
    source_manifest: str
    spaces: list[NormalizedSpace] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class NormalizedProject(BaseModel):
    project_id: str
    name: str
    source_format: str
    levels: list[NormalizedLevel] = Field(default_factory=list)
    units: list[NormalizedUnit] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
