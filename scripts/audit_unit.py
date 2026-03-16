from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from geometric_reasoner.auditor import audit_normalized_space
from geometric_reasoner.bim_normalized_models import NormalizedProject, NormalizedSpace, NormalizedUnit
from geometric_reasoner.cli import render_report
from geometric_reasoner.extraction import compliance_room_type_for_normalized_space
from geometric_reasoner.research import load_article_chunks
from geometric_reasoner.shared_data_models import AuditReport

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NORMALIZED = ROOT / "data" / "artifacts" / "normalized_bim" / "Unit_521_normalized_bim.json"
DEFAULT_ARTICLES = ROOT / "data" / "compliance_corpora" / "corpus_manifest.json"
STATUS_ORDER = {"FAIL": 0, "UNKNOWN": 1, "PASS": 2}
RETRIEVAL_MODES = ("overlap", "vector", "hybrid")
REASONING_MODES = ("deterministic", "llm")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit every supported space in a normalized BIM project JSON.")
    parser.add_argument(
        "normalized_json",
        nargs="?",
        default=str(DEFAULT_NORMALIZED),
        help="Path to a normalized BIM project JSON file.",
    )
    parser.add_argument(
        "--articles",
        default=str(DEFAULT_ARTICLES),
        help="Path to an article chunk JSON file or corpus manifest used for retrieval.",
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


def _load_project(path: Path) -> NormalizedProject:
    return NormalizedProject.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _auditable_spaces(project: NormalizedProject) -> list[tuple[NormalizedUnit, NormalizedSpace]]:
    return [
        (unit, space)
        for unit in project.units
        for space in unit.spaces
        if compliance_room_type_for_normalized_space(space)
    ]


def _render_summary(
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
        f"Overall unit status: {overall_status}",
        f"Audited space count: {len(space_results)}",
        f"Retrieval mode: {retrieval_mode}",
        f"Reasoning mode: {reasoning_mode}",
        "",
        "Space summary:",
    ]

    for unit, space, report in space_results:
        lines.append(f"- {unit.unit_id} :: {space.space_id} ({space.name}): {report.status}")

    lines.extend(
        [
            "",
            "Status counts:",
            f"- PASS: {counts.get('PASS', 0)}",
            f"- FAIL: {counts.get('FAIL', 0)}",
            f"- UNKNOWN: {counts.get('UNKNOWN', 0)}",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    normalized_path = Path(args.normalized_json)
    project = _load_project(normalized_path)
    articles = load_article_chunks(args.articles)
    space_results: list[tuple[NormalizedUnit, NormalizedSpace, AuditReport]] = []

    for unit, space in _auditable_spaces(project):
        report = audit_normalized_space(
            space,
            articles=articles,
            retrieval_mode=args.retrieval_mode,
            reasoning_mode=args.reasoning_mode,
        )
        space_results.append((unit, space, report))
        print(f"=== {space.space_id} ({space.name}) ===")
        print(render_report(report))
        print()

    print(_render_summary(project, space_results, args.retrieval_mode, args.reasoning_mode))


if __name__ == "__main__":
    main()
