from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from geometric_reasoner.auditor import audit_normalized_space
from geometric_reasoner.bim_normalized_models import NormalizedProject, NormalizedSpace
from geometric_reasoner.constraint_derivation import derive_constraints_for_article
from geometric_reasoner.research import load_article_chunks, load_rulebook, resolve_applicable_constraints
from geometric_reasoner.shared_data_models import CodeConstraint, Scene

ROOT = Path(__file__).resolve().parents[1]
ARTICLE_CHUNKS = ROOT / "data" / "compliance_corpora" / "corpus_manifest.json"
QUEBEC_ARTICLE_CHUNKS = ROOT / "data" / "compliance_corpora" / "quebec_b11_r2" / "quebec_b11_r2_articles.json"
MONTREAL_11_018_ARTICLES = ROOT / "data" / "compliance_corpora" / "montreal_11_018" / "montreal_11_018_articles.json"
MONTREAL_11_018_X_ARTICLES = ROOT / "data" / "compliance_corpora" / "montreal_11_018_x" / "montreal_11_018_x_articles.json"
NBC_2020_CONSTRAINTS = ROOT / "data" / "compliance_corpora" / "nbc_2020" / "nbc_2020_constraints_official.json"
QUEBEC_2015_2022_CONSTRAINTS = ROOT / "data" / "compliance_corpora" / "quebec_2015-2022" / "quebec_2015-2022_constraints_official.json"
QUEBEC_2020_ABOVE_CONSTRAINTS = ROOT / "data" / "compliance_corpora" / "quebec_2020_above" / "quebec_2020_above_constraints_official.json"
MONTREAL_11_018_CONSTRAINTS = ROOT / "data" / "compliance_corpora" / "montreal_11_018" / "montreal_11_018_constraints_official.json"
MONTREAL_11_018_X_CONSTRAINTS = ROOT / "data" / "compliance_corpora" / "montreal_11_018_x" / "montreal_11_018_x_constraints_official.json"
OFFICIAL_CONSTRAINTS = ROOT / "data" / "compliance_corpora" / "quebec_b11_r2" / "quebec_b11_r2_constraints_official.json"
NORMALIZED_ROOT = ROOT / "data" / "artifacts" / "normalized_bim"


class AuditorTests(unittest.TestCase):
    def _load_project(self, path: Path) -> NormalizedProject:
        return NormalizedProject.model_validate(json.loads(path.read_text(encoding="utf-8")))

    def _load_space(self, project_file: str, space_id: str) -> NormalizedSpace:
        project = self._load_project(NORMALIZED_ROOT / project_file)
        return next(
            space
            for unit in project.units
            for space in unit.spaces
            if space.space_id == space_id
        )

    def _audit_with_articles(self, project_file: str, space_id: str):
        space = self._load_space(project_file, space_id)
        return audit_normalized_space(space, articles=load_article_chunks(ARTICLE_CHUNKS))

    def test_compliant_space_passes(self) -> None:
        report = self._audit_with_articles("Unit_410_normalized_bim.json", "Unit_410_bathroom_primary_space")

        self.assertTrue(report.passed)
        self.assertEqual(report.status, "PASS")
        self.assertEqual(report.metadata["constraint_source"], "runtime_derived")
        self.assertEqual(report.metadata["retrieval_mode"], "hybrid")
        self.assertEqual(report.metadata["reasoning_mode"], "deterministic")
        self.assertEqual(report.metadata["reasoning_generation_mode"], "deterministic")
        self.assertGreater(len(report.metadata["retrieved_article_scores"]), 0)
        self.assertGreaterEqual(len(report.checks), 10)
        self.assertTrue(all(check.status == "PASS" for check in report.checks))
        self.assertGreaterEqual(report.metadata["retrieved_article_count"], 1)
        self.assertIn("QCC_B11_R2:3.8.5.5", report.metadata["retrieved_articles"])
        self.assertIsNotNone(report.llm_reasoning)
        assert report.llm_reasoning is not None
        self.assertEqual(report.llm_reasoning.generation_mode, "deterministic")
        self.assertIn("passed", report.llm_reasoning.summary)
        self.assertGreater(len(report.llm_reasoning.finding_explanations), 0)

    def test_noncompliant_space_fails(self) -> None:
        report = self._audit_with_articles("Unit_411_normalized_bim.json", "Unit_411_bathroom_primary_space")

        self.assertFalse(report.passed)
        self.assertEqual(report.status, "FAIL")
        self.assertGreaterEqual(sum(check.status == "FAIL" for check in report.checks), 5)
        self.assertGreater(report.metadata["matched_constraint_count"], 0)
        self.assertGreater(report.metadata["finding_count"], 0)

    def test_missing_required_fact_is_unknown(self) -> None:
        report = self._audit_with_articles("Unit_521_normalized_bim.json", "Unit_521_kitchen_open_plan_space")

        self.assertFalse(report.passed)
        self.assertEqual(report.status, "UNKNOWN")
        self.assertEqual(sum(check.status == "UNKNOWN" for check in report.checks), 1)
        unknown_finding = next(check for check in report.checks if check.status == "UNKNOWN")
        self.assertEqual(unknown_finding.parameter, "kitchen_sink_trap_bottom_height")
        self.assertEqual(unknown_finding.expected_element_types, ["kitchen_sink"])
        self.assertIsNotNone(report.llm_reasoning)
        assert report.llm_reasoning is not None
        self.assertIn("kitchen_sink_trap_bottom_height", report.llm_reasoning.recommended_next_measurements)
        self.assertIn("unknown", report.llm_reasoning.summary.lower())

    def test_official_article_chunks_load(self) -> None:
        articles = load_article_chunks(QUEBEC_ARTICLE_CHUNKS)

        self.assertEqual(len(articles), 19)
        bathroom_article = next(article for article in articles if article.article == "3.8.5.5")
        doorway_article = next(article for article in articles if article.article == "3.8.4.3")
        self.assertEqual(bathroom_article.title, "Bathrooms")
        self.assertIn("1 500 mm in diameter", bathroom_article.text)
        self.assertNotIn("Publisher", doorway_article.text)
        self.assertNotIn("Provision", doorway_article.text)
        self.assertNotIn("Amendments", doorway_article.text)
        self.assertEqual(bathroom_article.authority, "QCC_B11_R2")
        self.assertEqual(bathroom_article.priority, 2)
        self.assertEqual(bathroom_article.article_id, bathroom_article.article)
        self.assertEqual(bathroom_article.patch_action, "replace")

    def test_official_constraints_are_derived_from_articles(self) -> None:
        constraints = load_rulebook(OFFICIAL_CONSTRAINTS)

        self.assertEqual(len(constraints), 66)

        bathroom_turning = next(
            constraint
            for constraint in constraints
            if constraint.article == "3.8.5.5"
            and constraint.parameter == "turning_circle_diameter"
            and constraint.room_types == ["Residential Bathroom"]
        )
        towel_rack = next(
            constraint
            for constraint in constraints
            if constraint.article == "3.8.6.4" and constraint.parameter == "towel_rack_height"
        )
        lavatory_trap = [
            constraint
            for constraint in constraints
            if constraint.article == "3.8.5.5" and constraint.parameter == "lavatory_trap_bottom_height"
        ]

        self.assertEqual(bathroom_turning.operator, ">=")
        self.assertEqual(bathroom_turning.value, 1500.0)
        self.assertEqual(bathroom_turning.authority, "QCC_B11_R2")
        self.assertEqual(bathroom_turning.priority, 2)
        self.assertEqual(towel_rack.operator, "<=")
        self.assertEqual(towel_rack.value, 1200.0)
        self.assertEqual({constraint.operator for constraint in lavatory_trap}, {">=", "<="})
        self.assertEqual({constraint.value for constraint in lavatory_trap}, {230.0, 300.0})

    def test_prederived_rulebook_reports_constraint_source(self) -> None:
        space = self._load_space("Unit_410_normalized_bim.json", "Unit_410_bathroom_primary_space")
        report = audit_normalized_space(space, rulebook=load_rulebook(OFFICIAL_CONSTRAINTS))

        self.assertEqual(report.metadata["constraint_source"], "prederived_rulebook")
        self.assertEqual(report.metadata["retrieval_mode"], "none")
        self.assertEqual(report.metadata["reasoning_mode"], "deterministic")
        self.assertEqual(report.metadata["reasoning_generation_mode"], "deterministic")

    def test_passing_space_uses_deterministic_reasoning_even_in_llm_mode(self) -> None:
        space = self._load_space("Unit_410_normalized_bim.json", "Unit_410_bathroom_primary_space")
        with patch("geometric_reasoner.llm_reasoner._openai_reasoning", side_effect=AssertionError("should not call llm")):
            report = audit_normalized_space(
                space,
                articles=load_article_chunks(ARTICLE_CHUNKS),
                reasoning_mode="llm",
            )

        self.assertEqual(report.status, "PASS")
        self.assertEqual(report.metadata["reasoning_mode"], "llm")
        self.assertEqual(report.metadata["reasoning_generation_mode"], "deterministic")
        self.assertIsNotNone(report.llm_reasoning)
        assert report.llm_reasoning is not None
        self.assertEqual(report.llm_reasoning.generation_mode, "deterministic")

    def test_llm_reasoning_mode_falls_back_deterministically(self) -> None:
        space = self._load_space("Unit_521_normalized_bim.json", "Unit_521_kitchen_open_plan_space")
        with patch("geometric_reasoner.llm_reasoner._openai_reasoning", side_effect=RuntimeError("no llm")):
            report = audit_normalized_space(
                space,
                articles=load_article_chunks(ARTICLE_CHUNKS),
                reasoning_mode="llm",
            )

        self.assertEqual(report.metadata["reasoning_mode"], "llm")
        self.assertEqual(report.metadata["reasoning_generation_mode"], "deterministic_fallback")
        self.assertIsNotNone(report.llm_reasoning)
        assert report.llm_reasoning is not None
        self.assertEqual(report.llm_reasoning.generation_mode, "deterministic_fallback")

    def test_montreal_constraint_artifacts_load(self) -> None:
        montreal_base = load_rulebook(MONTREAL_11_018_CONSTRAINTS)
        montreal_amendment = load_rulebook(MONTREAL_11_018_X_CONSTRAINTS)

        self.assertGreater(len(montreal_base), 0)
        self.assertGreater(len(montreal_amendment), 0)

        self.assertTrue(all(constraint.authority == "MTL_11_018" for constraint in montreal_base))
        self.assertTrue(all(constraint.authority == "MTL_11_018_X" for constraint in montreal_amendment))

        self.assertIn("natural_lighting_glazing_ratio", {constraint.parameter for constraint in montreal_base})
        self.assertIn("living_room_area", {constraint.parameter for constraint in montreal_amendment})

    def test_remaining_authority_constraint_artifacts_load(self) -> None:
        nbc_constraints = load_rulebook(NBC_2020_CONSTRAINTS)
        quebec_2015_constraints = load_rulebook(QUEBEC_2015_2022_CONSTRAINTS)
        quebec_2020_constraints = load_rulebook(QUEBEC_2020_ABOVE_CONSTRAINTS)

        self.assertGreater(len(nbc_constraints), 0)
        self.assertGreater(len(quebec_2015_constraints), 0)
        self.assertGreater(len(quebec_2020_constraints), 0)

        self.assertTrue(all(constraint.authority == "NBC_2020" for constraint in nbc_constraints))
        self.assertTrue(all(constraint.authority == "QUEBEC_2015_2022" for constraint in quebec_2015_constraints))
        self.assertTrue(all(constraint.authority == "QUEBEC_2020_ABOVE" for constraint in quebec_2020_constraints))

        self.assertIn("control_height", {constraint.parameter for constraint in nbc_constraints})
        self.assertIn("lavatory_rim_height", {constraint.parameter for constraint in quebec_2015_constraints})

    def test_multiple_unit_artifacts_cover_pass_fail_and_unknown(self) -> None:
        space_expectations = {
            ("Unit_520_normalized_bim.json", "Unit_520_bedroom_secondary_space"): "PASS",
            ("Unit_521_normalized_bim.json", "Unit_521_living_room_space"): "FAIL",
            ("Unit_521_normalized_bim.json", "Unit_521_bedroom_secondary_space"): "UNKNOWN",
            ("Hotel_Suite_510_normalized_bim.json", "Hotel_Suite_510_closet_space"): "PASS",
        }

        for (project_file, space_id), expected_status in space_expectations.items():
            with self.subTest(project=project_file, space=space_id):
                report = self._audit_with_articles(project_file, space_id)
                self.assertEqual(report.status, expected_status)
                self.assertGreater(len(report.checks), 0)
                self.assertGreater(report.metadata["retrieved_article_count"], 0)

    def test_duplicate_equivalent_checks_are_grouped(self) -> None:
        report = self._audit_with_articles("Unit_411_normalized_bim.json", "Unit_411_suite_entry_space")

        self.assertFalse(report.passed)
        self.assertEqual(report.status, "FAIL")
        self.assertGreaterEqual(report.metadata["matched_constraint_count"], 11)
        self.assertEqual(report.metadata["finding_count"], 6)
        self.assertIn("QCC_B11_R2:3.8.5.3", report.metadata["retrieved_articles"])
        self.assertIn("QCC_B11_R2:3.8.4.3", report.metadata["retrieved_articles"])
        self.assertEqual(len(report.checks), 6)

        duplicated_finding = next(
            check
            for check in report.checks
            if check.parameter == "sliding_door_latch_clearance_perpendicular"
        )
        self.assertEqual([citation.article for citation in duplicated_finding.citations], ["3.8.4.3", "3.8.5.3"])
        self.assertIn(duplicated_finding.active_authority, {"QCC_B11_R2", "QUEBEC_2020_ABOVE"})
        self.assertGreaterEqual(len(duplicated_finding.override_trace), 2)

    def test_manifest_loader_returns_layered_articles(self) -> None:
        articles = load_article_chunks(ARTICLE_CHUNKS)

        self.assertGreater(len(articles), 19)
        authorities = {article.authority for article in articles}
        self.assertIn("QCC_B11_R2", authorities)
        self.assertIn("NBC_2020", authorities)
        self.assertIn("MTL_11_018", authorities)
        self.assertIn("MTL_11_018_X", authorities)

    def test_montreal_11_018_x_articles_are_loaded_in_english(self) -> None:
        articles = load_article_chunks(MONTREAL_11_018_X_ARTICLES)

        article_14 = next(article for article in articles if article.article == "14")
        article_18 = next(article for article in articles if article.article == "18")

        self.assertIn("natural second-day lighting", article_14.text.lower())
        self.assertIn("useful surface of at least", article_18.text.lower())
        self.assertNotIn("éclairage", article_14.text.lower())
        self.assertEqual(article_14.authority, "MTL_11_018_X")
        self.assertEqual(article_14.priority, 5)

    def test_montreal_11_018_articles_are_loaded_in_english(self) -> None:
        articles = load_article_chunks(MONTREAL_11_018_ARTICLES)

        article_14 = next(article for article in articles if article.article == "14")

        self.assertIn("minimum glass floor area", article_14.text.lower())
        self.assertIn("natural second-day lighting", article_14.text.lower())
        self.assertNotIn("éclairage", article_14.text.lower())
        self.assertEqual(article_14.authority, "MTL_11_018")
        self.assertEqual(article_14.priority, 4)

    def test_montreal_11_018_derives_constraints(self) -> None:
        articles = load_article_chunks(MONTREAL_11_018_ARTICLES)

        article_14 = next(article for article in articles if article.article == "14")
        constraints = derive_constraints_for_article(article_14)

        living_ratio = next(
            constraint
            for constraint in constraints
            if constraint.parameter == "natural_lighting_glazing_ratio"
            and constraint.room_types == ["Residential Living Room", "Residential Dining Room"]
        )
        bedroom_ratio = next(
            constraint
            for constraint in constraints
            if constraint.parameter == "natural_lighting_glazing_ratio"
            and constraint.room_types == ["Residential Bedroom"]
        )
        second_day_ratio = next(
            constraint for constraint in constraints if constraint.parameter == "second_day_lighting_glazing_ratio"
        )

        self.assertEqual(living_ratio.authority, "MTL_11_018")
        self.assertEqual(living_ratio.priority, 4)
        self.assertEqual(living_ratio.value, 0.10)
        self.assertEqual(bedroom_ratio.value, 0.05)
        self.assertEqual(second_day_ratio.value, 0.10)
        self.assertEqual(second_day_ratio.unit, "ratio")

    def test_montreal_11_018_x_derives_constraints(self) -> None:
        articles = load_article_chunks(MONTREAL_11_018_X_ARTICLES)

        article_14 = next(article for article in articles if article.article == "14")
        article_18 = next(article for article in articles if article.article == "18")
        article_23 = next(article for article in articles if article.article == "23")

        lighting_constraints = derive_constraints_for_article(article_14)
        surface_constraints = derive_constraints_for_article(article_18)
        green_roof_constraints = derive_constraints_for_article(article_23)

        glazing_ratio = next(constraint for constraint in lighting_constraints if constraint.parameter == "second_day_lighting_glazing_ratio")
        living_room_area = next(constraint for constraint in surface_constraints if constraint.parameter == "living_room_area")
        green_roof_required = next(constraint for constraint in green_roof_constraints if constraint.parameter == "green_roof_required")

        self.assertEqual(glazing_ratio.authority, "MTL_11_018_X")
        self.assertEqual(glazing_ratio.priority, 5)
        self.assertEqual(glazing_ratio.operator, ">=")
        self.assertEqual(glazing_ratio.value, 0.10)
        self.assertEqual(glazing_ratio.unit, "ratio")
        self.assertEqual(living_room_area.value, 13.5)
        self.assertEqual(living_room_area.unit, "m2")
        self.assertEqual(green_roof_required.operator, "==")
        self.assertEqual(green_roof_required.value, 1.0)
        self.assertEqual(green_roof_required.unit, "bool")

    def test_resolve_applicable_constraints_prefers_highest_priority(self) -> None:
        scene = Scene(room_id="demo_room", room_type="Residential Bedroom", elements=[])
        constraints = [
            CodeConstraint(
                article="NBC-1",
                title="Baseline bedroom area",
                parameter="bedroom_area",
                operator=">=",
                value=9.0,
                unit="m2",
                citation_text="baseline",
                room_types=["Residential Bedroom"],
                authority="NBC_2020",
                priority=1,
                jurisdiction="Canada",
                patch_action="add",
            ),
            CodeConstraint(
                article="QCC-1",
                title="Quebec bedroom area",
                parameter="bedroom_area",
                operator=">=",
                value=10.5,
                unit="m2",
                citation_text="quebec",
                room_types=["Residential Bedroom"],
                authority="QCC_B11_R2",
                priority=2,
                jurisdiction="Quebec",
                patch_action="replace",
            ),
            CodeConstraint(
                article="MTL-1",
                title="Montreal bedroom area",
                parameter="bedroom_area",
                operator=">=",
                value=13.5,
                unit="m2",
                citation_text="montreal",
                room_types=["Residential Bedroom"],
                authority="MTL_11_018_X",
                priority=5,
                jurisdiction="Montreal",
                patch_action="override",
            ),
        ]

        resolved = resolve_applicable_constraints(scene, constraints, parameter="bedroom_area")

        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0].constraint.authority, "MTL_11_018_X")
        self.assertEqual(resolved[0].constraint.value, 13.5)
        self.assertEqual(
            [trace.authority for trace in resolved[0].override_trace],
            ["NBC_2020", "QCC_B11_R2", "MTL_11_018_X"],
        )

    def test_all_normalized_unit_artifacts_have_auditable_spaces(self) -> None:
        for artifact_path in sorted(NORMALIZED_ROOT.glob("*_normalized_bim.json")):
            if artifact_path.name.startswith("AC20-FZK-Haus"):
                continue
            project = self._load_project(artifact_path)
            auditable_spaces = [
                space
                for unit in project.units
                for space in unit.spaces
                if space.room_type
            ]

            with self.subTest(project=artifact_path.name):
                self.assertGreater(len(auditable_spaces), 0)


if __name__ == "__main__":
    unittest.main()
