from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

from geometric_reasoner.ifc_ingestion import ingest_ifc_to_normalized_project_full


ROOT = Path(__file__).resolve().parents[1]
IFC_SAMPLE = ROOT / "data" / "ifc_samples" / "AC20-FZK-Haus.ifc"


@unittest.skipUnless(importlib.util.find_spec("ifcopenshell") is not None, "ifcopenshell is not installed")
class IfcOpenShellIngestionTests(unittest.TestCase):
    def test_ifcopenshell_parser_ingests_real_ifc(self) -> None:
        project = ingest_ifc_to_normalized_project_full(IFC_SAMPLE)

        self.assertEqual(project.project_id, "0lY6P5Ur90TAQnnnI6wtnb")
        self.assertEqual(project.source_format, "ifc_ifcopenshell_ingestion")
        self.assertEqual(len(project.levels), 2)
        self.assertEqual(len(project.units), 2)

        ground_floor = next(unit for unit in project.units if unit.name == "Erdgeschoss")
        bedroom = next(space for space in ground_floor.spaces if space.name == "Schlafzimmer")
        bedroom_window = next(element for element in bedroom.elements if element.ifc_type == "IFCWINDOW")

        self.assertEqual(bedroom.raw_properties["compliance_room_type"], "Residential Bedroom")
        self.assertTrue(any(element.ifc_type == "IFCDOOR" and element.hosted_by for element in ground_floor.spaces[0].elements))
        self.assertIn("geometry_bbox_width_mm", bedroom.raw_properties)
        self.assertIn("geometry_bbox_depth_mm", bedroom.raw_properties)
        self.assertGreater(bedroom.raw_properties["geometry_bbox_width_mm"], 0.0)
        self.assertGreater(bedroom.raw_properties["geometry_bbox_depth_mm"], 0.0)
        self.assertIn("geometry_bbox_min_z_mm", bedroom_window.raw_properties)
        self.assertAlmostEqual(bedroom_window.raw_properties["geometry_bbox_min_z_mm"], 800.0, delta=5.0)
        derived_parameters = {fact.parameter for fact in bedroom.derived_facts}
        self.assertIn("bedroom_area", derived_parameters)
        self.assertIn("bedroom_length", derived_parameters)
        self.assertIn("bedroom_width", derived_parameters)
        self.assertIn("window_sill_height", derived_parameters)


if __name__ == "__main__":
    unittest.main()
