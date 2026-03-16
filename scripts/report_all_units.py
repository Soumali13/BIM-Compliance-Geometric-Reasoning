from __future__ import annotations

import argparse
from pathlib import Path

from geometric_reasoner.research import load_article_chunks

from build_unit_report import _build_project_package

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_UNITS_ROOT = ROOT / "data" / "artifacts" / "normalized_bim"
DEFAULT_ARTICLES = ROOT / "data" / "compliance_corpora" / "corpus_manifest.json"
DEFAULT_OUTPUT_ROOT = ROOT / "data" / "reports"
RETRIEVAL_MODES = ("overlap", "vector", "hybrid")
REASONING_MODES = ("deterministic", "llm")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate packaged PDF reports for every normalized unit artifact.")
    parser.add_argument(
        "--units-root",
        default=str(DEFAULT_UNITS_ROOT),
        help="Directory containing normalized unit artifacts.",
    )
    parser.add_argument(
        "--articles",
        default=str(DEFAULT_ARTICLES),
        help="Path to an article chunk JSON file or corpus manifest used for retrieval.",
    )
    parser.add_argument(
        "--output-root",
        default=str(DEFAULT_OUTPUT_ROOT),
        help="Directory where report folders will be created.",
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


def _unit_artifacts(units_root: Path) -> list[Path]:
    return sorted(units_root.glob("*_normalized_bim.json"))


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    units_root = Path(args.units_root)
    output_root = Path(args.output_root)
    articles = load_article_chunks(args.articles)

    artifact_paths = _unit_artifacts(units_root)
    if not artifact_paths:
        raise SystemExit(f"No normalized unit artifacts found under {units_root}")

    generated: list[Path] = []
    for artifact_path in artifact_paths:
        package_dir = _build_project_package(
            artifact_path,
            output_root,
            articles,
            retrieval_mode=args.retrieval_mode,
            reasoning_mode=args.reasoning_mode,
        )
        generated.append(package_dir)
        print(f"{artifact_path.name} -> {package_dir}")

    print(f"Generated {len(generated)} unit report packages in {output_root}")


if __name__ == "__main__":
    main()
