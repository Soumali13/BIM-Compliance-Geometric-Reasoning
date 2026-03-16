from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_UNIT = ROOT / "data" / "artifacts" / "normalized_bim" / "Unit_521_normalized_bim.json"
RETRIEVAL_MODES = {"overlap", "vector", "hybrid"}
REASONING_MODES = {"deterministic", "llm"}


def _display_path(path: Path) -> str:
    if path.is_absolute() and ROOT in path.parents:
        return str(path.relative_to(ROOT))
    return str(path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the default end-to-end audit and report demo for a normalized BIM file.")
    parser.add_argument(
        "normalized_json",
        nargs="?",
        default=str(DEFAULT_UNIT),
        help="Path to a normalized BIM project JSON file.",
    )
    parser.add_argument(
        "--retrieval-mode",
        choices=sorted(RETRIEVAL_MODES),
        default="hybrid",
        help="Retrieval strategy for article chunk selection. Defaults to hybrid.",
    )
    parser.add_argument(
        "--reasoning-mode",
        choices=sorted(REASONING_MODES),
        default="deterministic",
        help="Reasoning layer mode. Defaults to deterministic.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    retrieval_mode = args.retrieval_mode
    reasoning_mode = args.reasoning_mode
    normalized_path = Path(args.normalized_json)
    if not normalized_path.is_absolute():
        normalized_path = ROOT / normalized_path

    print(f"=== Unit Audit: {_display_path(normalized_path)} ===", flush=True)
    subprocess.run(
        [
            sys.executable,
            "scripts/audit_unit.py",
            str(normalized_path),
            "--retrieval-mode",
            retrieval_mode,
            "--reasoning-mode",
            reasoning_mode,
        ],
        check=True,
        cwd=ROOT,
    )
    print()
    print(f"=== Unit Report: {_display_path(normalized_path)} ===", flush=True)
    subprocess.run(
        [
            sys.executable,
            "scripts/build_unit_report.py",
            str(normalized_path),
            "--retrieval-mode",
            retrieval_mode,
            "--reasoning-mode",
            reasoning_mode,
        ],
        check=True,
        cwd=ROOT,
    )


if __name__ == "__main__":
    main()
