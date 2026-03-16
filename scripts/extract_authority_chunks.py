from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE_ROOT = Path(tempfile.gettempdir()) / "geometric_reasoner_cache"

for cache_dir in (
    CACHE_ROOT,
    CACHE_ROOT / "matplotlib",
    CACHE_ROOT / "fontconfig",
    CACHE_ROOT / "numba",
):
    cache_dir.mkdir(parents=True, exist_ok=True)

os.environ.setdefault("MPLCONFIGDIR", str(CACHE_ROOT / "matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(CACHE_ROOT))
os.environ.setdefault("NUMBA_CACHE_DIR", str(CACHE_ROOT / "numba"))
os.environ.setdefault("NUMBA_DISABLE_JIT", "1")
os.environ.setdefault("FONTCONFIG_PATH", str(CACHE_ROOT / "fontconfig"))

from unstructured.documents.elements import Element
from unstructured.partition.pdf import partition_pdf


@dataclass(frozen=True)
class AuthorityConfig:
    key: str
    authority: str
    jurisdiction: str
    priority: int
    effective_date: str
    patch_action: str
    pdf_path: Path
    output_path: Path
    extractor_kind: str
    scope: list[str]
    page_source: str = "pdftotext"


AUTHORITY_CONFIGS = {
    "MTL_11_018_X": AuthorityConfig(
        key="MTL_11_018_X",
        authority="MTL_11_018_X",
        jurisdiction="Montreal",
        priority=5,
        effective_date="2024-01-01",
        patch_action="override",
        pdf_path=ROOT / "data" / "compliance_corpora" / "montreal_11_018_x" / "montreal_11_018_x.pdf",
        output_path=ROOT / "data" / "compliance_corpora" / "montreal_11_018_x" / "montreal_11_018_x_articles.json",
        extractor_kind="montreal_bylaw",
        scope=["11-018-X"],
        page_source="pdftotext",
    ),
    "MTL_11_018": AuthorityConfig(
        key="MTL_11_018",
        authority="MTL_11_018",
        jurisdiction="Montreal",
        priority=4,
        effective_date="2011-10-24",
        patch_action="override",
        pdf_path=ROOT / "data" / "compliance_corpora" / "montreal_11_018" / "montreal_11_018.pdf",
        output_path=ROOT / "data" / "compliance_corpora" / "montreal_11_018" / "montreal_11_018_articles.json",
        extractor_kind="montreal_bylaw",
        scope=["11-018"],
        page_source="pdftotext",
    ),
    "NBC_2020": AuthorityConfig(
        key="NBC_2020",
        authority="NBC_2020",
        jurisdiction="Canada",
        priority=1,
        effective_date="2020-01-01",
        patch_action="add",
        pdf_path=ROOT / "data" / "compliance_corpora" / "nbc_2020" / "nbc_2020.pdf",
        output_path=ROOT / "data" / "compliance_corpora" / "nbc_2020" / "nbc_2020_articles.json",
        extractor_kind="nbc_accessibility",
        scope=["3.8.3"],
        page_source="pdftotext",
    ),
    "QUEBEC_2015_2022": AuthorityConfig(
        key="QUEBEC_2015_2022",
        authority="QUEBEC_2015_2022",
        jurisdiction="Quebec",
        priority=3,
        effective_date="2022-01-08",
        patch_action="replace",
        pdf_path=ROOT / "data" / "compliance_corpora" / "quebec_2015-2022" / "quebec_2015-2022.pdf",
        output_path=ROOT / "data" / "compliance_corpora" / "quebec_2015-2022" / "quebec_2015-2022_articles.json",
        extractor_kind="quebec_accessibility",
        scope=["3.8.3"],
        page_source="pdftotext",
    ),
    "QUEBEC_2020_ABOVE": AuthorityConfig(
        key="QUEBEC_2020_ABOVE",
        authority="QUEBEC_2020_ABOVE",
        jurisdiction="Quebec",
        priority=3,
        effective_date="2025-04-17",
        patch_action="replace",
        pdf_path=ROOT / "data" / "compliance_corpora" / "quebec_2020_above" / "quebec_2020_above.pdf",
        output_path=ROOT / "data" / "compliance_corpora" / "quebec_2020_above" / "quebec_2020_above_articles.json",
        extractor_kind="quebec_accessibility",
        scope=["3.8.3"],
        page_source="pdftotext",
    ),
}


MONTREAL_CHAPTER_RE = re.compile(r"(?m)^CHAPITRE\s+([IVXLC]+)\s*\n([^\n]+)")
MONTREAL_SECTION_RE = re.compile(r"(?m)^SECTION\s+([IVXLC]+)\s*\n([^\n]+)")
MONTREAL_SUBSECTION_RE = re.compile(r"(?m)^SOUS-SECTION\s+([IVXLC]+)\s*\n([^\n]+)")
MONTREAL_ARTICLE_RE = re.compile(r"(?m)^(\d+(?:\.\d+)?)\.\s")

CODE_ARTICLE_LINE_RE = re.compile(r"^3\.8\.(?:3|4|5|6)\.\d+\.$")


def _element_text(element: Element) -> str:
    text = getattr(element, "text", "") or ""
    return text.rstrip()


def _extract_pdf_pages_unstructured(pdf_path: Path) -> list[tuple[int | None, str]]:
    elements = partition_pdf(
        filename=str(pdf_path),
        strategy="fast",
        include_page_breaks=False,
    )

    pages: dict[int | None, list[str]] = {}
    for element in elements:
        text = _element_text(element)
        page_number = getattr(getattr(element, "metadata", None), "page_number", None)
        if not text:
            continue
        pages.setdefault(page_number, []).append(text)

    return [
        (page_number, "\n".join(lines))
        for page_number, lines in sorted(pages.items(), key=lambda item: item[0] or 0)
        if any(line.strip() for line in lines)
    ]


def _extract_pdf_pages_pdftotext(pdf_path: Path) -> list[tuple[int | None, str]]:
    info = subprocess.run(
        ["pdfinfo", str(pdf_path)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    pages_match = re.search(r"Pages:\s+(\d+)", info)
    if not pages_match:
        raise RuntimeError(f"Could not determine page count for {pdf_path}")

    page_count = int(pages_match.group(1))
    pages: list[tuple[int | None, str]] = []
    for page_number in range(1, page_count + 1):
        result = subprocess.run(
            ["pdftotext", "-f", str(page_number), "-l", str(page_number), str(pdf_path), "-"],
            check=True,
            capture_output=True,
            text=True,
        )
        if result.stdout.strip():
            pages.append((page_number, result.stdout))
    return pages


def extract_pdf_pages(pdf_path: Path, *, page_source: str) -> list[tuple[int | None, str]]:
    if page_source == "pdftotext":
        return _extract_pdf_pages_pdftotext(pdf_path)
    if page_source == "unstructured":
        return _extract_pdf_pages_unstructured(pdf_path)
    raise ValueError(f"Unsupported page source: {page_source}")


def _clean_common_text(text: str) -> str:
    cleaned = text.replace("\u00a0", " ")
    cleaned = re.sub(r"\f", "\n", cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _clean_montreal_page_text(text: str) -> str:
    cleaned = _clean_common_text(text)
    cleaned = re.sub(r"(?m)^\d{2}-\d{3}(?:-X)?/\d+\s*$", "", cleaned)
    cleaned = re.sub(r"(?m)^VILLE DE MONTRÉAL\s*$", "", cleaned)
    cleaned = re.sub(r"(?m)^RÈGLEMENT\s*$", "", cleaned)
    cleaned = re.sub(r"(?m)^Copyright.*$", "", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _clean_code_page_text(text: str) -> str:
    cleaned = _clean_common_text(text)
    cleaned = re.sub(r"(?m)^Copyright © NRC.*$", "", cleaned)
    cleaned = re.sub(
        r"(?m)^National Building Code of Canada (?:2015|2020)(?: \(incorporating Quebec amendments\))? Volume \d+\s*$",
        "",
        cleaned,
    )
    cleaned = re.sub(r"(?m)^Division B \d+-\d+\s*$", "", cleaned)
    cleaned = re.sub(r"(?m)^\d+-\d+ Division B\s*$", "", cleaned)
    cleaned = re.sub(r"(?m)^Division B\s*$", "Division B", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _append_article_text(current_article: dict, text: str, page_number: int | None) -> None:
    cleaned = text.strip(' "\u201c\u201d')
    cleaned = re.sub(r"\n{2,}", "\n", cleaned)
    cleaned = cleaned.strip()
    if not cleaned:
        return
    current_article["text_parts"].append(cleaned)
    if page_number is not None and page_number not in current_article["source_pages"]:
        current_article["source_pages"].append(page_number)


def _detect_amends_article_id(text: str) -> str | None:
    patterns = [
        r"L[’']article\s+(\d+(?:\.\d+)?)",
        r"article\s+(\d+(?:\.\d+)?)\s+de ce règlement",
        r"paragraphe\s+\d+\s+de l[’']article\s+(\d+(?:\.\d+)?)",
        r"article\s+(3\.\d+\.\d+\.\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def extract_montreal_bylaw_articles(config: AuthorityConfig) -> dict:
    pages = [
        (page_number, _clean_montreal_page_text(page_text))
        for page_number, page_text in extract_pdf_pages(config.pdf_path, page_source=config.page_source)
    ]

    articles: list[dict] = []
    current_article: dict | None = None
    current_chapter = ""
    current_section = ""
    current_subsection = ""
    current_section_title = ""

    for page_number, page_text in pages:
        if not page_text:
            continue

        events: list[tuple[str, int, re.Match[str]]] = []
        events.extend(("chapter", match.start(), match) for match in MONTREAL_CHAPTER_RE.finditer(page_text))
        events.extend(("section", match.start(), match) for match in MONTREAL_SECTION_RE.finditer(page_text))
        events.extend(("subsection", match.start(), match) for match in MONTREAL_SUBSECTION_RE.finditer(page_text))
        events.extend(("article", match.start(), match) for match in MONTREAL_ARTICLE_RE.finditer(page_text))
        events.sort(key=lambda item: item[1])

        cursor = 0
        for kind, position, match in events:
            if current_article and position > cursor:
                _append_article_text(current_article, page_text[cursor:position], page_number)

            if kind == "chapter":
                current_chapter = f"CHAPITRE {match.group(1)}"
            elif kind == "section":
                current_section = f"SECTION {match.group(1)}"
                current_section_title = match.group(2).strip()
            elif kind == "subsection":
                current_subsection = f"SOUS-SECTION {match.group(1)}"
                current_section_title = match.group(2).strip()
            else:
                if current_article:
                    text = "\n".join(current_article["text_parts"]).strip()
                    current_article["text"] = re.sub(r"\s+", " ", text).strip()
                    current_article["amends_article_id"] = _detect_amends_article_id(current_article["text"])
                    del current_article["text_parts"]
                    articles.append(current_article)

                section = " / ".join(part for part in [current_chapter, current_section, current_subsection] if part)
                current_article = {
                    "article": match.group(1),
                    "article_id": match.group(1),
                    "title": f"Article {match.group(1)}",
                    "section": section,
                    "section_title": current_section_title or section,
                    "source_pages": [],
                    "source_pdf": config.pdf_path.name,
                    "authority": config.authority,
                    "jurisdiction": config.jurisdiction,
                    "priority": config.priority,
                    "effective_date": config.effective_date,
                    "patch_action": config.patch_action,
                    "applies_if": {"jurisdiction": config.jurisdiction},
                    "text_parts": [],
                }

            cursor = match.end()

        if current_article and cursor < len(page_text):
            _append_article_text(current_article, page_text[cursor:], page_number)

    if current_article:
        text = "\n".join(current_article["text_parts"]).strip()
        current_article["text"] = re.sub(r"\s+", " ", text).strip()
        current_article["amends_article_id"] = _detect_amends_article_id(current_article["text"])
        del current_article["text_parts"]
        articles.append(current_article)

    return {
        "authority": config.authority,
        "jurisdiction": config.jurisdiction,
        "priority": config.priority,
        "effective_date": config.effective_date,
        "patch_action": config.patch_action,
        "source_pdf": str(config.pdf_path),
        "scope": config.scope,
        "generated_by": "scripts/extract_authority_chunks.py",
        "articles": articles,
    }


def _build_code_payload(config: AuthorityConfig, articles: list[dict]) -> dict:
    return {
        "authority": config.authority,
        "jurisdiction": config.jurisdiction,
        "priority": config.priority,
        "effective_date": config.effective_date,
        "patch_action": config.patch_action,
        "source_pdf": str(config.pdf_path),
        "scope": config.scope,
        "generated_by": "scripts/extract_authority_chunks.py",
        "articles": articles,
    }


def _collect_code_pages(config: AuthorityConfig) -> list[tuple[int | None, str]]:
    return [
        (page_number, _clean_code_page_text(page_text))
        for page_number, page_text in extract_pdf_pages(config.pdf_path, page_source=config.page_source)
    ]


def _finalize_article(current_article: dict | None, articles: list[dict]) -> dict | None:
    if not current_article:
        return None
    text = "\n".join(current_article["text_parts"]).strip()
    current_article["text"] = re.sub(r"\s+", " ", text).strip()
    current_article["amends_article_id"] = None
    del current_article["text_parts"]
    articles.append(current_article)
    return None


def _next_nonempty(lines: list[str], start_index: int) -> str | None:
    for index in range(start_index, len(lines)):
        candidate = lines[index].strip()
        if candidate:
            return candidate
    return None


def _is_code_header_article(article_line: str, next_line: str | None) -> bool:
    if not next_line:
        return True
    if next_line == "Division B":
        return True
    if CODE_ARTICLE_LINE_RE.fullmatch(next_line):
        return True
    if re.match(r"^(?:\d+\)|[a-z]\)|[ivxlcdm]+\)|\(See\b)", next_line):
        return True
    return False


def _looks_like_article_title(line: str) -> bool:
    if not line or line == "Division B":
        return False
    if CODE_ARTICLE_LINE_RE.fullmatch(line):
        return False
    if re.fullmatch(r"\d+-\d+ Division B", line) or re.fullmatch(r"Division B \d+-\d+", line):
        return False
    if re.match(r"^(?:\d+\)|[a-z]\)|[ivxlcdm]+\)|\(See\b)", line):
        return False
    return True


def _score_article_title(title: str) -> tuple[int, int]:
    invalid = not _looks_like_article_title(title)
    return (1 if invalid else 0, -len(title))


def _merge_articles_by_id(articles: list[dict]) -> list[dict]:
    merged: list[dict] = []
    by_id: dict[str, dict] = {}
    order: list[str] = []

    for article in articles:
        article_id = article["article_id"]
        if article_id not in by_id:
            by_id[article_id] = article
            order.append(article_id)
            continue

        existing = by_id[article_id]
        if _score_article_title(article["title"]) < _score_article_title(existing["title"]):
            existing["title"] = article["title"]

        if article["text"] and article["text"] not in existing["text"]:
            existing["text"] = " ".join(part for part in [existing["text"], article["text"]] if part).strip()

        pages = sorted(set(existing.get("source_pages", [])) | set(article.get("source_pages", [])))
        existing["source_pages"] = pages

    for article_id in order:
        merged.append(by_id[article_id])
    return merged


def _extract_code_accessibility_articles(config: AuthorityConfig, *, section_title: str) -> dict:
    pages = [
        (page_number, page_text)
        for page_number, page_text in _collect_code_pages(config)
    ]

    articles: list[dict] = []
    current_article: dict | None = None
    pending_article_id: str | None = None

    for page_number, page_text in pages:
        if not page_text:
            continue

        lines = page_text.splitlines()
        for index, raw_line in enumerate(lines):
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("Copyright © NRC"):
                continue
            if line == "Division B":
                continue
            if re.fullmatch(r"\d+-\d+ Division B", line) or re.fullmatch(r"Division B \d+-\d+", line):
                continue

            if CODE_ARTICLE_LINE_RE.fullmatch(line):
                next_line = _next_nonempty(lines, index + 1)
                if _is_code_header_article(line, next_line):
                    continue
                article_id = line[:-1]
                if current_article and current_article["article"] == article_id:
                    continue
                current_article = _finalize_article(current_article, articles)

                pending_article_id = article_id
                continue

            if pending_article_id:
                if line == f"{pending_article_id}." or not _looks_like_article_title(line):
                    continue
                current_article = {
                    "article": pending_article_id,
                    "article_id": pending_article_id,
                    "title": line,
                    "section": "3.8.3",
                    "section_title": section_title,
                    "source_pages": [page_number] if page_number is not None else [],
                    "source_pdf": config.pdf_path.name,
                    "authority": config.authority,
                    "jurisdiction": config.jurisdiction,
                    "priority": config.priority,
                    "effective_date": config.effective_date,
                    "patch_action": config.patch_action,
                    "applies_if": {"jurisdiction": config.jurisdiction},
                    "text_parts": [],
                }
                pending_article_id = None
                continue

            if current_article:
                _append_article_text(current_article, line, page_number)

    current_article = _finalize_article(current_article, articles)
    return _build_code_payload(config, _merge_articles_by_id(articles))


def extract_nbc_accessibility_articles(config: AuthorityConfig) -> dict:
    return _extract_code_accessibility_articles(config, section_title="Barrier-Free Design")


def extract_quebec_accessibility_articles(config: AuthorityConfig) -> dict:
    return _extract_code_accessibility_articles(config, section_title="Barrier-Free Design")


def extract_articles(config: AuthorityConfig) -> dict:
    if config.extractor_kind == "montreal_bylaw":
        return extract_montreal_bylaw_articles(config)
    if config.extractor_kind == "nbc_accessibility":
        return extract_nbc_accessibility_articles(config)
    if config.extractor_kind == "quebec_accessibility":
        return extract_quebec_accessibility_articles(config)
    raise ValueError(f"Unsupported extractor kind: {config.extractor_kind}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract authority-specific article chunks from source PDFs.")
    parser.add_argument(
        "authority",
        choices=sorted(AUTHORITY_CONFIGS),
        help="Authority corpus to extract.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    config = AUTHORITY_CONFIGS[args.authority]

    print(f"Using {config.page_source} PDF parsing for {config.authority}.", flush=True)
    payload = extract_articles(config)
    config.output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {len(payload['articles'])} article chunks to {config.output_path}")


if __name__ == "__main__":
    main()
