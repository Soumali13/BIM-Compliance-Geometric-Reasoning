from __future__ import annotations

import unittest
import json
from pathlib import Path

from geometric_reasoner.auditor import audit_normalized_project, audit_normalized_space
from geometric_reasoner.bim_normalized_models import NormalizedProject
from geometric_reasoner.ifc_ingestion import ingest_ifc_to_normalized_project, ingest_ifc_to_normalized_project_full
from geometric_reasoner.research import load_article_chunks


ROOT = Path(__file__).resolve().parents[1]
ARTICLE_CHUNKS = ROOT / "data" / "compliance_corpora" / "corpus_manifest.json"
UNIT_521 = ROOT / "data" / "artifacts" / "normalized_bim" / "Unit_521_normalized_bim.json"
IFC_SAMPLE = ROOT / "data" / "ifc_samples" / "AC20-FZK-Haus.ifc"


class NormalizedAuditorTests(unittest.TestCase):
    def _load_project(self, path: Path) -> NormalizedProject:
        return NormalizedProject.model_validate(json.loads(path.read_text(encoding="utf-8")))

    def test_synthetic_normalized_space_audits_directly(self) -> None:
        project = self._load_project(UNIT_521)
        articles = load_article_chunks(ARTICLE_CHUNKS)

        kitchen_space = next(
            space
            for unit in project.units
            for space in unit.spaces
            if space.space_id == "Unit_521_kitchen_open_plan_space"
        )

        report = audit_normalized_space(kitchen_space, articles=articles)
        self.assertEqual(report.status, "UNKNOWN")
        self.assertEqual(report.room_type, "Residential Kitchen")
        self.assertEqual(sum(check.status == "UNKNOWN" for check in report.checks), 1)

    def test_ingested_ifc_project_can_be_audited_directly(self) -> None:
        project = ingest_ifc_to_normalized_project(IFC_SAMPLE)
        articles = load_article_chunks(ARTICLE_CHUNKS)

        reports = audit_normalized_project(project, articles=articles)
        report_by_space = {report.scene_id: report for report in reports}

        self.assertIn("Erdgeschoss_space_20909", report_by_space)
        bedroom_report = report_by_space["Erdgeschoss_space_20909"]
        self.assertEqual(bedroom_report.room_type, "Residential Bedroom")
        self.assertIn(bedroom_report.status, {"PASS", "UNKNOWN", "FAIL"})
        self.assertGreater(len(bedroom_report.checks), 0)

    def test_ifcopenshell_geometry_facts_drive_bedroom_audit(self) -> None:
        project = ingest_ifc_to_normalized_project_full(IFC_SAMPLE)
        articles = load_article_chunks(ARTICLE_CHUNKS)

        bedroom_space = next(
            space
            for unit in project.units
            for space in unit.spaces
            if space.space_id == "Erdgeschoss_space_20909"
        )

        report = audit_normalized_space(bedroom_space, articles=articles)
        self.assertEqual(report.room_type, "Residential Bedroom")
        self.assertEqual(report.status, "PASS")
        check_parameters = {check.parameter for check in report.checks}
        self.assertIn("window_sill_height", check_parameters)
        self.assertIn("bedroom_area", check_parameters)
        self.assertIn("bedroom_length", check_parameters)
        self.assertIn("bedroom_width", check_parameters)


if __name__ == "__main__":
    unittest.main()
