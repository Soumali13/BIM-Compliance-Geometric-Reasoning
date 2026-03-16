# BIM-Compliance-Geometric-Reasoning

A local-first compliance prototype that treats:

- normalized BIM unit artifacts as the audit input
- authority-split compliance corpora as the retrieval corpus
- code clauses as executable constraints
- compliance as geometric fact evaluation with precedence-aware rule resolution

## Current data layout

- `data/compliance_corpora/`
  - authority-split compliance corpora
  - `nbc_2020/`
  - `quebec_b11_r2/`
  - `quebec_2015-2022/`
  - `quebec_2020_above/`
  - `montreal_11_018/`
  - `montreal_11_018_x/`
  - `corpus_manifest.json`
  - current extracted article chunks are populated in `quebec_b11_r2/`
  - the other authority folders are ready for chunk extraction and patch-layer retrieval
- `data/ifc_samples/`
  - raw IFC input samples
- `data/artifacts/normalized_bim/`
  - canonical normalized BIM audit inputs for synthetic units and real IFC ingestion

## Included normalized BIM inputs

- `data/artifacts/normalized_bim/Unit_410_normalized_bim.json`
- `data/artifacts/normalized_bim/Unit_411_normalized_bim.json`
- `data/artifacts/normalized_bim/Unit_520_normalized_bim.json`
- `data/artifacts/normalized_bim/Unit_521_normalized_bim.json`
- `data/artifacts/normalized_bim/Hotel_Suite_510_normalized_bim.json`
- `data/artifacts/normalized_bim/AC20-FZK-Haus_normalized_bim.json`

The `*_normalized_bim.json` files are the canonical normalized BIM audit inputs.
`AC20-FZK-Haus_normalized_bim.json` is a real IFC sample ingested through `ifcopenshell`.

## Main commands

Audit every auditable space in a normalized unit artifact:

```bash
./audit-unit data/artifacts/normalized_bim/Unit_521_normalized_bim.json
./audit-unit data/artifacts/normalized_bim/Hotel_Suite_510_normalized_bim.json
./audit-unit data/artifacts/normalized_bim/Unit_521_normalized_bim.json --retrieval-mode overlap
./audit-unit data/artifacts/normalized_bim/Unit_521_normalized_bim.json --reasoning-mode llm
```

Audit a normalized BIM project directly, optionally targeting one space:

```bash
./audit-normalized data/artifacts/normalized_bim/Unit_521_normalized_bim.json
./audit-normalized data/artifacts/normalized_bim/Unit_521_normalized_bim.json --space-id Unit_521_kitchen_open_plan_space
./audit-normalized data/artifacts/normalized_bim/AC20-FZK-Haus_normalized_bim.json --space-id Erdgeschoss_space_20909
./audit-normalized data/artifacts/normalized_bim/Unit_521_normalized_bim.json --space-id Unit_521_kitchen_open_plan_space --retrieval-mode vector
./audit-normalized data/artifacts/normalized_bim/Unit_521_normalized_bim.json --space-id Unit_521_kitchen_open_plan_space --reasoning-mode llm
```

Audit a low-level BIM-lite scene JSON directly with the package CLI:

```bash
geometric-audit path/to/scene.json
geometric-audit path/to/scene.json --retrieval-mode overlap
geometric-audit path/to/scene.json --retrieval-mode vector
geometric-audit path/to/scene.json --reasoning-mode llm
```

Generate a packaged unit report from a normalized unit artifact:

```bash
./report-unit data/artifacts/normalized_bim/Unit_521_normalized_bim.json
./report-unit data/artifacts/normalized_bim/Unit_521_normalized_bim.json --retrieval-mode vector
./report-unit data/artifacts/normalized_bim/Unit_521_normalized_bim.json --reasoning-mode llm
./report-all-units
./report-all-units --retrieval-mode overlap
./report-all-units --reasoning-mode llm
```

`./report-all-units` generates packaged PDF report folders for every `*_normalized_bim.json` artifact under `data/artifacts/normalized_bim`, including the real IFC-derived sample.

Run the default demo flow:

```bash
./run-demo
./run-demo --retrieval-mode vector
./run-demo --reasoning-mode llm
```

This now:

- audits the default normalized unit artifact
- generates a packaged report under `data/reports/`
- uses `hybrid` retrieval by default unless you pass `--retrieval-mode overlap|vector|hybrid`
- uses deterministic reasoning by default unless you pass `--reasoning-mode llm`
- in `llm` mode, only `FAIL` and `UNKNOWN` spaces use the LLM; `PASS` spaces stay deterministic

Ingest the real IFC sample into normalized BIM:

```bash
./ingest-ifc
./ingest-ifc data/ifc_samples/AC20-FZK-Haus.ifc
```

Default real IFC output:

```text
data/artifacts/normalized_bim/AC20-FZK-Haus_normalized_bim.json
```

Optional lightweight fallback:

```bash
./ingest-ifc --parser step --output data/artifacts/normalized_bim/AC20-FZK-Haus_step.json
```

## What the normalized audit path does

- loads a `NormalizedProject`
- audits every supported `NormalizedSpace`
- retrieves relevant code articles for each space
- derives executable constraints from those articles
- resolves active rules by authority priority and effective date
- carries override traces into findings and reports
- generates a reasoning layer with:
  - summary
  - precedence explanation
  - recommended next measurements
  - per-finding explanations
- produces `PASS`, `FAIL`, or `UNKNOWN`

`--reasoning-mode deterministic` uses a local template-driven reasoning layer.
`--reasoning-mode llm` attempts to use the OpenAI client for `FAIL` and `UNKNOWN` spaces only, while `PASS` spaces stay deterministic. If the OpenAI client is unavailable or the call fails, the audit falls back to deterministic reasoning.

For real IFC ingestion through `ifcopenshell`, the pipeline also derives geometry-based facts from IFC shape representations, including:

- window sill height
- element bounding-box width and height
- approximate room length, width, height, and area

## Report packaging

`./report-unit` creates a folder under `data/reports/<unit_id>/` with:

- `source_normalized_project.json`
- `unit_audit.json`
- `unit_audit.txt`
- `unit_audit.pdf`
- `input_spaces/`
- `space_reports/`

Each `space_reports/<space_id>/` package contains:

- `space_input.json`
- `retrieved_articles.json`
- `derived_constraints.json`
- `audit_report.json`
- `audit_report.txt`
- `audit_report.pdf`

## Rules pipeline

Regenerate article chunks from the official Quebec code PDF:

```bash
./regen-articles
```

Regenerate executable constraints from the article corpus:

```bash
./regen-constraints
```

Notes:

- `./regen-articles` uses `unstructured`
- the first run is slower on the full Quebec PDF
- the script prints a progress message before parsing

## Tests

```bash
./test
```

## Legal note

The article corpus comes from the official Quebec code source, but this repo is still a prototype and not a legal opinion or design approval tool.
