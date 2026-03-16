from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from geometric_reasoner.research import load_article_chunks
from geometric_reasoner.vector_retrieval import (
    DEFAULT_MODEL_NAME,
    build_article_vector_index,
    write_article_vector_index,
)


DEFAULT_ARTICLES = ROOT / "data" / "compliance_corpora" / "corpus_manifest.json"
DEFAULT_OUTPUT = ROOT / "data" / "artifacts" / "vector_index" / "article_chunks_index.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a local vector index for article chunks.")
    parser.add_argument(
        "--articles",
        default=str(DEFAULT_ARTICLES),
        help="Path to an article chunk JSON file or corpus manifest.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Output path for the vector index JSON.",
    )
    parser.add_argument(
        "--model-name",
        default=DEFAULT_MODEL_NAME,
        help="Sentence-transformer model name used to encode article chunks.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    articles = load_article_chunks(args.articles)
    payload = build_article_vector_index(
        articles,
        model_name=args.model_name,
        allow_download=True,
    )
    write_article_vector_index(args.output, payload)
    print(
        f"Wrote {payload['index_type']} index with model {payload['model_name']} "
        f"for {payload['article_count']} article chunks to {args.output}"
    )


if __name__ == "__main__":
    main()
