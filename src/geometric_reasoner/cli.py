from __future__ import annotations

import argparse
import json
from pathlib import Path

from geometric_reasoner.auditor import audit_scene
from geometric_reasoner.shared_data_models import Scene
from geometric_reasoner.research import load_article_chunks, load_rulebook

DEFAULT_RULEBOOK = Path(__file__).resolve().parents[2] / "data" / "compliance_corpora" / "quebec_b11_r2" / "quebec_b11_r2_constraints_official.json"
DEFAULT_ARTICLES = Path(__file__).resolve().parents[2] / "data" / "compliance_corpora" / "corpus_manifest.json"
RETRIEVAL_MODES = ("overlap", "vector", "hybrid")
REASONING_MODES = ("deterministic", "llm")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit a BIM-lite scene against structured accessibility constraints.")
    parser.add_argument("scene", help="Path to a scene JSON file")
    parser.add_argument(
        "--rules",
        default=None,
        help="Optional path to a pre-derived JSON constraint file. If omitted, the CLI retrieves relevant article chunks and derives constraints on the fly.",
    )
    parser.add_argument(
        "--articles",
        default=str(DEFAULT_ARTICLES),
        help="Path to an article chunk JSON file or corpus manifest used for retrieval. Defaults to the layered corpus manifest.",
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
        help="Reasoning layer mode. Defaults to deterministic. LLM mode requires a configured OpenAI client.",
    )
    return parser


def render_report(report) -> str:
    lines = [
        f"Scene: {report.scene_id} ({report.room_type})",
        f"Overall status: {report.status}",
        f"Constraint source: {report.metadata.get('constraint_source', 'unknown')}",
        f"Retrieval mode: {report.metadata.get('retrieval_mode', 'none')}",
        f"Reasoning mode: {report.metadata.get('reasoning_mode', 'deterministic')}",
        f"Reasoning generation: {report.metadata.get('reasoning_generation_mode', 'deterministic')}",
        "",
    ]

    if report.llm_reasoning is not None:
        lines.extend(
            [
                "Reasoning summary:",
                f"  {report.llm_reasoning.summary}",
                f"  Precedence: {report.llm_reasoning.precedence_explanation}",
                (
                    "  Recommended next measurements: "
                    + ", ".join(report.llm_reasoning.recommended_next_measurements)
                )
                if report.llm_reasoning.recommended_next_measurements
                else "",
                "",
            ]
        )

    for check in report.checks:
        status = check.status
        article_label = ", ".join(citation.article for citation in check.citations)
        source_label = (
            f"{check.source_element}.{check.source_measurement}"
            if check.source_element and check.source_measurement
            else f"missing.{check.parameter}"
        )
        lines.extend(
            [
                f"[{status}] Articles {article_label} - {source_label}",
                f"  fact: {check.fact_value:.1f} {check.fact_unit}" if check.fact_value is not None and check.fact_unit else "  fact: missing",
                f"  requirement: {check.operator} {check.required_value:.1f} {check.required_unit}",
                f"  reason: {check.reason}",
                f"  active authority: {check.active_authority} ({check.active_jurisdiction})",
                f"  citations: {'; '.join(f'{citation.article} {citation.title}' for citation in check.citations)}",
                (
                    "  override trace: "
                    + " -> ".join(
                        f"{trace.authority}:{trace.article} {trace.operator} {trace.value:.1f} {trace.unit}"
                        for trace in check.override_trace
                    )
                )
                if check.override_trace
                else "",
                f"  expected from: {', '.join(check.expected_element_types)}" if check.expected_element_types else "",
                "",
            ]
        )

    if report.unmatched_facts:
        lines.append("Unmatched facts:")
        for fact in report.unmatched_facts:
            lines.append(f"  - {fact.source_element}.{fact.source_measurement} -> {fact.parameter}")

    return "\n".join(lines).rstrip()


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    with Path(args.scene).open("r", encoding="utf-8") as f:
        scene = Scene.model_validate(json.load(f))

    if args.rules:
        report = audit_scene(scene, rulebook=load_rulebook(args.rules))
    else:
        report = audit_scene(
            scene,
            articles=load_article_chunks(args.articles),
            retrieval_mode=args.retrieval_mode,
            reasoning_mode=args.reasoning_mode,
        )
    print(render_report(report))


if __name__ == "__main__":
    main()
