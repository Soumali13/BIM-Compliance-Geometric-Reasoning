from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from geometric_reasoner.auditor import audit_normalized_project, audit_normalized_space
from geometric_reasoner.bim_normalized_models import NormalizedProject
from geometric_reasoner.cli import render_report
from geometric_reasoner.research import load_article_chunks, load_rulebook


DEFAULT_NORMALIZED = ROOT / "data" / "artifacts" / "normalized_bim" / "Unit_521_normalized_bim.json"
DEFAULT_ARTICLES = ROOT / "data" / "compliance_corpora" / "corpus_manifest.json"
RETRIEVAL_MODES = ("overlap", "vector", "hybrid")
REASONING_MODES = ("deterministic", "llm")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit normalized BIM JSON directly.")
    parser.add_argument("normalized_json", nargs="?", default=str(DEFAULT_NORMALIZED), help="Path to a normalized BIM project JSON file.")
    parser.add_argument("--space-id", default=None, help="Optional normalized space_id to audit.")
    parser.add_argument("--rules", default=None, help="Optional pre-derived constraint JSON.")
    parser.add_argument("--articles", default=str(DEFAULT_ARTICLES), help="Article chunk JSON used for retrieval.")
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


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    project = _load_project(Path(args.normalized_json))
    rulebook = load_rulebook(args.rules) if args.rules else None
    articles = None if args.rules else load_article_chunks(args.articles)

    if args.space_id:
        for unit in project.units:
            for space in unit.spaces:
                if space.space_id == args.space_id:
                    print(
                        render_report(
                            audit_normalized_space(
                                space,
                                rulebook=rulebook,
                                articles=articles,
                                retrieval_mode=args.retrieval_mode,
                                reasoning_mode=args.reasoning_mode,
                            )
                        )
                    )
                    return
        raise SystemExit(f"Could not find space_id {args.space_id}")

    reports = audit_normalized_project(
        project,
        rulebook=rulebook,
        articles=articles,
        retrieval_mode=args.retrieval_mode,
        reasoning_mode=args.reasoning_mode,
    )
    for index, report in enumerate(reports):
        if index:
            print()
        print(render_report(report))


if __name__ == "__main__":
    main()
