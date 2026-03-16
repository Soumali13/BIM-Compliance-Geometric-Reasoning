from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from geometric_reasoner.ifc_ingestion import (
    ingest_ifc_to_normalized_project,
    ingest_ifc_to_normalized_project_full,
)


DEFAULT_IFC = ROOT / "data" / "ifc_samples" / "AC20-FZK-Haus.ifc"
DEFAULT_OUTPUT = ROOT / "data" / "artifacts" / "normalized_bim" / "AC20-FZK-Haus_normalized_bim.json"
STEP_OUTPUT = ROOT / "data" / "artifacts" / "normalized_bim" / "AC20-FZK-Haus_step.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest a real IFC file into the normalized BIM intermediate schema.")
    parser.add_argument(
        "ifc_file",
        nargs="?",
        default=str(DEFAULT_IFC),
        help="Path to an IFC file.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Path to the normalized JSON output.",
    )
    parser.add_argument(
        "--parser",
        choices=["step", "ifcopenshell"],
        default="ifcopenshell",
        help="IFC ingestion backend. Defaults to 'ifcopenshell'; 'step' is a lightweight fallback parser.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    ifc_path = Path(args.ifc_file)
    if ifc_path.resolve() == DEFAULT_IFC.resolve():
        default_output = DEFAULT_OUTPUT if args.parser == "ifcopenshell" else STEP_OUTPUT
    else:
        suffix = "_normalized_bim.json" if args.parser == "ifcopenshell" else "_step.json"
        default_output = ROOT / "data" / "artifacts" / "normalized_bim" / f"{ifc_path.stem}{suffix}"
    output_path = Path(args.output) if args.output else default_output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if args.parser == "ifcopenshell":
        project = ingest_ifc_to_normalized_project_full(ifc_path)
    else:
        project = ingest_ifc_to_normalized_project(ifc_path)
    output_path.write_text(json.dumps(project.model_dump(), indent=2), encoding="utf-8")
    print(f"Wrote ingested IFC normalization to {output_path}")


if __name__ == "__main__":
    main()
