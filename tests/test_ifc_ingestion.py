from __future__ import annotations

import unittest
from pathlib import Path

from geometric_reasoner.ifc_ingestion import ingest_ifc_to_normalized_project


ROOT = Path(__file__).resolve().parents[1]
IFC_SAMPLE = ROOT / "data" / "ifc_samples" / "AC20-FZK-Haus.ifc"


class IfcIngestionTests(unittest.TestCase):
    def test_real_ifc_ingests_into_normalized_project(self) -> None:
        project = ingest_ifc_to_normalized_project(IFC_SAMPLE)

        self.assertEqual(project.project_id, "0lY6P5Ur90TAQnnnI6wtnb")
        self.assertEqual(project.name, "Projekt-FZK-Haus")
        self.assertEqual(project.source_format, "ifc_step_ingestion")
        self.assertEqual(len(project.levels), 2)
        self.assertEqual(len(project.units), 2)

        ground_floor = next(unit for unit in project.units if unit.name == "Erdgeschoss")
        attic = next(unit for unit in project.units if unit.name == "Dachgeschoss")

        self.assertEqual(len(ground_floor.spaces), 6)
        self.assertEqual(len(attic.spaces), 1)

        bedroom = next(space for space in ground_floor.spaces if space.name == "Schlafzimmer")
        bathroom = next(space for space in ground_floor.spaces if space.name == "Bad")
        gallery = next(space for space in attic.spaces if space.name == "Galerie")

        self.assertEqual(bedroom.raw_properties["ifc_name"], "4")
        self.assertIn(bathroom.space_id, bedroom.adjacent_to)
        self.assertEqual(gallery.level_id, attic.level_id)

        door = next(element for element in ground_floor.spaces[0].elements if element.ifc_type == "IFCDOOR")
        window = next(element for element in ground_floor.spaces[0].elements if element.ifc_type == "IFCWINDOW")

        self.assertIsNotNone(door.hosted_by)
        self.assertEqual(window.revit_category, "Windows")
        self.assertGreater(len(ground_floor.spaces[0].derived_facts), 0)


if __name__ == "__main__":
    unittest.main()
