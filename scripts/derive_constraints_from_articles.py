from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from geometric_reasoner.constraint_derivation import build_constraint_payload, write_constraint_payload
from geometric_reasoner.research import load_article_chunks


DEFAULT_ARTICLES_PATH = ROOT / "data" / "compliance_corpora" / "quebec_b11_r2" / "quebec_b11_r2_articles.json"


def _default_output_for_articles(articles_path: Path) -> Path:
    stem = articles_path.stem
    if stem.endswith("_articles"):
        stem = stem[: -len("_articles")]
    return articles_path.with_name(f"{stem}_constraints_official.json")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Derive executable constraints from an authority article corpus.")
    parser.add_argument(
        "articles_path",
        nargs="?",
        default=str(DEFAULT_ARTICLES_PATH),
        help="Path to an *_articles.json corpus file.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional explicit output path. Defaults to *_constraints_official.json beside the article corpus.",
    )
    parser.add_argument(
        "--source",
        default=None,
        help="Optional human-readable source description for the generated payload.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    articles_path = Path(args.articles_path).resolve()
    output_path = Path(args.output) if args.output else _default_output_for_articles(articles_path)
    source = args.source or f"Derived deterministically from official article chunks in {articles_path.name}."

    articles = load_article_chunks(articles_path)
    payload = build_constraint_payload(
        articles,
        source=source,
        derived_from=str(articles_path.relative_to(ROOT)),
    )
    write_constraint_payload(output_path, payload)

    constraint_count = sum(len(article["constraints"]) for article in payload["articles"])
    print(f"Wrote {constraint_count} constraints across {len(payload['articles'])} articles to {output_path}")


if __name__ == "__main__":
    main()
