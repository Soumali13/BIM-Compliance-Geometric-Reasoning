from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from geometric_reasoner.auditor import audit_normalized_space
from geometric_reasoner.bim_normalized_models import NormalizedProject, NormalizedSpace, NormalizedUnit
from geometric_reasoner.cli import render_report
from geometric_reasoner.constraint_derivation import derive_constraints_from_articles
from geometric_reasoner.extraction import (
    compliance_room_type_for_normalized_space,
    extract_geometric_facts_from_normalized_space,
    normalized_space_to_scene,
)
from geometric_reasoner.pdf_reports import render_space_audit_pdf, render_unit_audit_pdf
from geometric_reasoner.research import load_article_chunks, retrieve_relevant_articles
from geometric_reasoner.shared_data_models import AuditReport


DEFAULT_TARGET = ROOT / "data" / "artifacts" / "normalized_bim" / "Unit_521_normalized_bim.json"
DEFAULT_ARTICLES = ROOT / "data" / "compliance_corpora" / "corpus_manifest.json"
DEFAULT_OUTPUT_ROOT = ROOT / "data" / "reports"
STATUS_ORDER = {"FAIL": 0, "UNKNOWN": 1, "PASS": 2}
RETRIEVAL_MODES = ("overlap", "vector", "hybrid")
REASONING_MODES = ("deterministic", "llm")


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or "unit_report"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a packaged audit report for a normalized BIM project JSON.")
    parser.add_argument(
        "target",
        nargs="?",
        default=str(DEFAULT_TARGET),
        help="Path to a normalized BIM project JSON file. Defaults to Unit_521_normalized_bim.json.",
    )
    parser.add_argument(
        "--articles",
        default=str(DEFAULT_ARTICLES),
        help="Path to an article chunk JSON file or corpus manifest used for retrieval.",
    )
    parser.add_argument(
        "--output-root",
        default=str(DEFAULT_OUTPUT_ROOT),
        help="Directory where the generated report folder will be created.",
    )
    parser.add_argument(
        "--package-name",
        default=None,
        help="Optional explicit name for the generated report folder.",
    )
    parser.add_argument(
        "--retrieval-mode",
        choices=RETRIEVAL_MODES,
        default="hybrid",
        help="Retrieval strategy for article chunk selection. Defaults to hybrid.",
    )
    parser.add_argument(
        "--reasoning-mode",
        choices=REASONING_MODES,
        default="deterministic",
        help="Reasoning layer mode. Defaults to deterministic.",
    )
    return parser


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _load_project(path: Path) -> NormalizedProject:
    return NormalizedProject.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _auditable_spaces(project: NormalizedProject) -> list[tuple[NormalizedUnit, NormalizedSpace]]:
    return [
        (unit, space)
        for unit in project.units
        for space in unit.spaces
        if compliance_room_type_for_normalized_space(space)
    ]


def _evaluate_space(
    space: NormalizedSpace,
    articles,
    retrieval_mode: str,
    reasoning_mode: str,
) -> tuple[AuditReport, list, list]:
    scene_stub = normalized_space_to_scene(space)
    compliance_room_type = compliance_room_type_for_normalized_space(space)
    if compliance_room_type:
        scene_stub.room_type = compliance_room_type
    facts = extract_geometric_facts_from_normalized_space(space)
    retrieved_articles = retrieve_relevant_articles(scene_stub, facts, articles, retrieval_mode=retrieval_mode)
    constraints = derive_constraints_from_articles(retrieved_articles)
    report = audit_normalized_space(
        space,
        articles=articles,
        retrieval_mode=retrieval_mode,
        reasoning_mode=reasoning_mode,
    )
    return report, retrieved_articles, constraints


def _build_space_report_text(
    report: AuditReport,
    retrieved_articles,
    constraints,
    normalized_path: Path,
    unit: NormalizedUnit,
    space: NormalizedSpace,
) -> str:
    lines = [
        render_report(report),
        "",
        "Metadata",
        f"- Source normalized BIM: {normalized_path}",
        f"- Unit ID: {unit.unit_id}",
        f"- Space ID: {space.space_id}",
        f"- Space name: {space.name}",
        f"- Retrieved articles: {', '.join(article.article for article in retrieved_articles) or 'none'}",
        f"- Derived constraints: {len(constraints)}",
        f"- Findings: {report.metadata.get('finding_count', 0)}",
    ]
    return "\n".join(lines).rstrip() + "\n"


def _build_space_package(
    normalized_path: Path,
    unit: NormalizedUnit,
    space: NormalizedSpace,
    destination_dir: Path,
    articles,
    retrieval_mode: str,
    reasoning_mode: str,
) -> dict:
    report, retrieved_articles, constraints = _evaluate_space(space, articles, retrieval_mode, reasoning_mode)
    destination_dir.mkdir(parents=True, exist_ok=True)

    _write_json(destination_dir / "space_input.json", space.model_dump())
    _write_json(destination_dir / "retrieved_articles.json", [article.model_dump() for article in retrieved_articles])
    _write_json(destination_dir / "derived_constraints.json", [constraint.model_dump() for constraint in constraints])
    _write_json(destination_dir / "audit_report.json", report.model_dump())

    report_text_path = destination_dir / "audit_report.txt"
    report_text_path.write_text(
        _build_space_report_text(report, retrieved_articles, constraints, normalized_path, unit, space),
        encoding="utf-8",
    )
    render_space_audit_pdf(
        destination_dir / "audit_report.pdf",
        report,
        normalized_path,
        unit,
        space,
        retrieved_articles,
        constraints,
    )

    return {
        "space_id": report.scene_id,
        "space_name": space.name,
        "room_type": report.room_type,
        "status": report.status,
        "reasoning_generation_mode": report.metadata.get("reasoning_generation_mode"),
        "reasoning_summary": report.llm_reasoning.summary if report.llm_reasoning is not None else None,
        "recommended_next_measurements": (
            report.llm_reasoning.recommended_next_measurements if report.llm_reasoning is not None else []
        ),
        "artifacts": [
            "space_input.json",
            "retrieved_articles.json",
            "derived_constraints.json",
            "audit_report.json",
            "audit_report.txt",
            "audit_report.pdf",
        ],
    }


def _render_unit_summary(
    normalized_path: Path,
    project: NormalizedProject,
    space_results: list[tuple[NormalizedUnit, NormalizedSpace, AuditReport]],
    retrieval_mode: str,
    reasoning_mode: str,
) -> str:
    counts = Counter(report.status for _, _, report in space_results)
    overall_status = min((report.status for _, _, report in space_results), key=lambda status: STATUS_ORDER[status])
    unit_ids = ", ".join(unit.unit_id for unit in project.units)
    lines = [
        f"Project: {project.name}",
        f"Project ID: {project.project_id}",
        f"Units: {unit_ids}",
        f"Source normalized BIM: {normalized_path}",
        f"Overall unit status: {overall_status}",
        f"Audited space count: {len(space_results)}",
        f"Retrieval mode: {retrieval_mode}",
        f"Reasoning mode: {reasoning_mode}",
        "",
        "Space summary:",
    ]

    for unit, space, report in space_results:
        lines.append(f"- {unit.unit_id} :: {space.space_id} ({space.name}): {report.status}")
        if report.status in {"FAIL", "UNKNOWN"} and report.llm_reasoning is not None:
            lines.append(f"  reason: {report.llm_reasoning.summary}")
            if report.llm_reasoning.recommended_next_measurements:
                lines.append(
                    "  next measurements: "
                    + ", ".join(report.llm_reasoning.recommended_next_measurements)
                )

    lines.extend(
        [
            "",
            "Status counts:",
            f"- PASS: {counts.get('PASS', 0)}",
            f"- FAIL: {counts.get('FAIL', 0)}",
            f"- UNKNOWN: {counts.get('UNKNOWN', 0)}",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _package_name(target_path: Path, project: NormalizedProject) -> str:
    return _safe_name(target_path.stem or project.project_id)


def _build_project_package(
    normalized_path: Path,
    output_root: Path,
    articles,
    *,
    package_name: str | None = None,
    retrieval_mode: str = "hybrid",
    reasoning_mode: str = "deterministic",
) -> Path:
    project = _load_project(normalized_path)
    generated_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    package_dir = output_root / _safe_name(package_name) if package_name else output_root / _package_name(normalized_path, project)
    package_dir.mkdir(parents=True, exist_ok=True)

    input_spaces_dir = package_dir / "input_spaces"
    space_reports_dir = package_dir / "space_reports"
    input_spaces_dir.mkdir(exist_ok=True)
    space_reports_dir.mkdir(exist_ok=True)

    shutil.copy2(normalized_path, package_dir / "source_normalized_project.json")

    space_results: list[tuple[NormalizedUnit, NormalizedSpace, AuditReport]] = []
    space_manifests: list[dict] = []

    for unit, space in _auditable_spaces(project):
        space_report_dir = space_reports_dir / _safe_name(space.space_id)
        space_manifest = _build_space_package(
            normalized_path,
            unit,
            space,
            space_report_dir,
            articles,
            retrieval_mode,
            reasoning_mode,
        )
        space_manifests.append(space_manifest)
        _write_json(input_spaces_dir / f"{space.space_id}.json", space.model_dump())
        report = AuditReport.model_validate(json.loads((space_report_dir / "audit_report.json").read_text(encoding="utf-8")))
        space_results.append((unit, space, report))

    unit_summary_text = _render_unit_summary(normalized_path, project, space_results, retrieval_mode, reasoning_mode)
    unit_summary_path = package_dir / "unit_audit.txt"
    unit_summary_path.write_text(unit_summary_text, encoding="utf-8")
    render_unit_audit_pdf(
        package_dir / "unit_audit.pdf",
        normalized_path,
        project,
        space_results,
        retrieval_mode,
        reasoning_mode,
        generated_at,
    )

    counts = Counter(report.status for _, _, report in space_results)
    overall_status = min((report.status for _, _, report in space_results), key=lambda status: STATUS_ORDER[status])
    unit_summary_json = {
        "project_id": project.project_id,
        "project_name": project.name,
        "unit_ids": [unit.unit_id for unit in project.units],
        "source_normalized_project": str(normalized_path),
        "overall_status": overall_status,
        "retrieval_mode": retrieval_mode,
        "reasoning_mode": reasoning_mode,
        "generated_at": generated_at,
        "space_count": len(space_results),
        "status_counts": {
            "PASS": counts.get("PASS", 0),
            "FAIL": counts.get("FAIL", 0),
            "UNKNOWN": counts.get("UNKNOWN", 0),
        },
        "spaces": [
            {
                "unit_id": unit.unit_id,
                "space_id": space.space_id,
                "space_name": space.name,
                "room_type": report.room_type,
                "status": report.status,
                "reasoning_generation_mode": report.metadata.get("reasoning_generation_mode"),
                "reasoning_summary": report.llm_reasoning.summary if report.llm_reasoning is not None else None,
                "recommended_next_measurements": (
                    report.llm_reasoning.recommended_next_measurements if report.llm_reasoning is not None else []
                ),
            }
            for unit, space, report in space_results
        ],
    }
    _write_json(package_dir / "unit_audit.json", unit_summary_json)

    package_manifest = {
        "project_id": project.project_id,
        "project_name": project.name,
        "unit_ids": [unit.unit_id for unit in project.units],
        "artifacts": [
            "source_normalized_project.json",
            "unit_audit.json",
            "unit_audit.txt",
            "unit_audit.pdf",
            "input_spaces/",
            "space_reports/",
        ],
        "retrieval_mode": retrieval_mode,
        "reasoning_mode": reasoning_mode,
        "generated_at": generated_at,
        "space_reports": space_manifests,
    }
    _write_json(package_dir / "manifest.json", package_manifest)
    return package_dir


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    target_path = Path(args.target)
    output_root = Path(args.output_root)
    articles = load_article_chunks(args.articles)
    package_dir = _build_project_package(
        target_path,
        output_root,
        articles,
        package_name=args.package_name,
        retrieval_mode=args.retrieval_mode,
        reasoning_mode=args.reasoning_mode,
    )
    print(f"Wrote unit report package to {package_dir}")


if __name__ == "__main__":
    main()
