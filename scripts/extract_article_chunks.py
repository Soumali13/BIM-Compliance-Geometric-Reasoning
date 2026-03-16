from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PDF_PATH = ROOT / "data" / "compliance_corpora" / "quebec_b11_r2" / "quebec_b11_r2.pdf"
OUTPUT_PATH = ROOT / "data" / "compliance_corpora" / "quebec_b11_r2" / "quebec_b11_r2_articles.json"
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

SECTION_HEADER_RE = re.compile(r'(3\.8\.(?:4|5|6))\.\s+([A-Z][A-Za-z \-]+?(?:Occupancy|Motels))')
ARTICLE_HEADER_RE = re.compile(
    r'(3\.8\.(?:4|5|6)\.\d+)\.\s+([A-Z][A-Za-z \-]+?)(?=\s+\(See Note|\s+\d+\)\s|$)'
)


def extract_pdf_pages(pdf_path: Path) -> list[tuple[int | None, str]]:
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


def _element_text(element: Element) -> str:
    text = getattr(element, "text", "") or ""
    return text.rstrip()


def _normalize_page_text(page_text: str) -> str:
    normalized = " ".join(page_text.split()).strip()
    normalized = re.sub(
        r"Updated to .*?Provision Amendments",
        " ",
        normalized,
    )
    normalized = re.sub(
        r"© Québec Official Publisher .*?Provision Amendments",
        " ",
        normalized,
    )
    return " ".join(normalized.split())


def _append_article_text(current_article: dict, text: str, page_number: int | None) -> None:
    cleaned = text.strip(' "\u201c\u201d')
    cleaned = _strip_footer_artifacts(cleaned)
    if not cleaned:
        return
    current_article["text_parts"].append(cleaned)
    if page_number is not None and page_number not in current_article["source_pages"]:
        current_article["source_pages"].append(page_number)


def _strip_footer_artifacts(text: str) -> str:
    cleaned = text
    while "Updated to" in cleaned and "Provision Amendments" in cleaned:
        start = cleaned.index("Updated to")
        end = cleaned.index("Provision Amendments") + len("Provision Amendments")
        cleaned = f"{cleaned[:start]} {cleaned[end:]}"
    return " ".join(cleaned.split())


def extract_articles(pdf_path: Path) -> dict:
    pages = extract_pdf_pages(pdf_path)

    articles: list[dict] = []
    current_section = ""
    current_section_title = ""
    current_article: dict | None = None

    for page_number, page_text in pages:
        normalized_page_text = _normalize_page_text(page_text)
        if not normalized_page_text:
            continue

        events: list[tuple[str, int, re.Match[str]]] = []
        events.extend(("section", match.start(), match) for match in SECTION_HEADER_RE.finditer(normalized_page_text))
        events.extend(("article", match.start(), match) for match in ARTICLE_HEADER_RE.finditer(normalized_page_text))
        events.sort(key=lambda item: item[1])

        cursor = 0
        for kind, position, match in events:
            if current_article and position > cursor:
                _append_article_text(current_article, normalized_page_text[cursor:position], page_number)

            if kind == "section":
                current_section = match.group(1)
                current_section_title = match.group(2).strip(' "”')
            else:
                if current_article:
                    current_article["text"] = _strip_footer_artifacts(" ".join(current_article["text_parts"]).strip())
                    del current_article["text_parts"]
                    articles.append(current_article)

                current_article = {
                    "article": match.group(1),
                    "title": match.group(2).strip(' "”'),
                    "section": current_section,
                    "section_title": current_section_title,
                    "source_pages": [],
                    "source_pdf": pdf_path.name,
                    "text_parts": [],
                }

            cursor = match.end()

        if current_article and cursor < len(normalized_page_text):
            _append_article_text(current_article, normalized_page_text[cursor:], page_number)

    if current_article:
        current_article["text"] = _strip_footer_artifacts(" ".join(current_article["text_parts"]).strip())
        del current_article["text_parts"]
        articles.append(current_article)

    return {
        "source_pdf": str(pdf_path),
        "scope": ["3.8.4", "3.8.5", "3.8.6"],
        "generated_by": "scripts/extract_article_chunks.py",
        "articles": articles,
    }


def main() -> None:
    print("Using unstructured PDF parsing; the first run may take a while.", flush=True)
    payload = extract_articles(PDF_PATH)
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {len(payload['articles'])} article chunks to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
