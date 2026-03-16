from __future__ import annotations

import argparse
import re
import sys
from html import escape
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.graphics.shapes import Drawing, Ellipse, Line, Polygon, Rect, String
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, Preformatted, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


DEFAULT_INPUT = ROOT / "docs" / "high_level_project_report.md"
DEFAULT_OUTPUT = ROOT / "docs" / "high_level_project_report.pdf"


SECTION_COLORS = {
    "header": colors.HexColor("#0F172A"),
    "subheader": colors.HexColor("#1E3A5F"),
    "border": colors.HexColor("#CBD5E1"),
    "muted": colors.HexColor("#475569"),
    "surface": colors.HexColor("#F8FAFC"),
    "surface_alt": colors.HexColor("#EEF2F7"),
    "brand": colors.HexColor("#0B6BCB"),
    "accent": colors.HexColor("#C98A2E"),
    "brand_dark": colors.HexColor("#0B2747"),
    "cover_band": colors.HexColor("#E8F1FB"),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render a markdown report to a styled PDF.")
    parser.add_argument("source", nargs="?", default=str(DEFAULT_INPUT), help="Path to the markdown source file.")
    parser.add_argument("output", nargs="?", default=str(DEFAULT_OUTPUT), help="Path to the output PDF.")
    return parser


def styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "cover_title": ParagraphStyle(
            "CoverTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=26,
            leading=32,
            textColor=SECTION_COLORS["header"],
            spaceAfter=8,
        ),
        "cover_subtitle": ParagraphStyle(
            "CoverSubtitle",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=12,
            textColor=SECTION_COLORS["brand"],
            spaceAfter=8,
        ),
        "h1": ParagraphStyle(
            "H1",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=24,
            textColor=SECTION_COLORS["header"],
            spaceBefore=8,
            spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "H2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            textColor=SECTION_COLORS["brand_dark"],
            spaceBefore=10,
            spaceAfter=6,
        ),
        "h3": ParagraphStyle(
            "H3",
            parent=base["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=SECTION_COLORS["subheader"],
            spaceBefore=8,
            spaceAfter=5,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=colors.black,
        ),
        "bullet": ParagraphStyle(
            "Bullet",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            leftIndent=14,
            firstLineIndent=-8,
            bulletIndent=4,
        ),
        "number": ParagraphStyle(
            "Number",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            leftIndent=18,
            firstLineIndent=-12,
        ),
        "code": ParagraphStyle(
            "Code",
            parent=base["Code"],
            fontName="Courier",
            fontSize=8.5,
            leading=10.5,
            textColor=SECTION_COLORS["brand_dark"],
        ),
        "small": ParagraphStyle(
            "Small",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            textColor=SECTION_COLORS["muted"],
        ),
    }


def brand_logo(width: float = 1.1 * inch, height: float = 1.1 * inch) -> Drawing:
    drawing = Drawing(width, height)
    bar_width = width * 0.17
    gap = width * 0.06
    left = width * 0.12
    base_y = height * 0.18
    heights = [height * 0.42, height * 0.62, height * 0.82]
    fills = [SECTION_COLORS["brand_dark"], SECTION_COLORS["brand"], SECTION_COLORS["accent"]]
    for index, (bar_height, fill) in enumerate(zip(heights, fills)):
        x = left + index * (bar_width + gap)
        drawing.add(Rect(x, base_y, bar_width, bar_height, fillColor=fill, strokeColor=fill))
    drawing.add(
        Polygon(
            [
                left - 2,
                base_y + height * 0.18,
                left + bar_width + gap * 0.4,
                base_y + 2,
                left + bar_width * 2.1 + gap * 1.4,
                base_y + height * 0.32,
                left + bar_width * 3.0 + gap * 2.0,
                base_y + height * 0.68,
            ],
            strokeColor=SECTION_COLORS["accent"],
            fillColor=None,
            strokeWidth=3,
        )
    )
    drawing.add(Line(left - 4, base_y - 4, width * 0.88, base_y - 4, strokeColor=SECTION_COLORS["border"], strokeWidth=1))
    return drawing


def page_chrome(canvas, doc) -> None:
    canvas.saveState()
    canvas.setStrokeColor(SECTION_COLORS["brand"])
    canvas.setLineWidth(1.2)
    canvas.line(doc.leftMargin, doc.pagesize[1] - 0.48 * inch, doc.pagesize[0] - doc.rightMargin, doc.pagesize[1] - 0.48 * inch)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(SECTION_COLORS["muted"])
    canvas.drawString(doc.leftMargin, 0.45 * inch, "BIM Compliance Geometric Reasoning")
    canvas.drawRightString(doc.pagesize[0] - doc.rightMargin, 0.45 * inch, f"Page {doc.page}")
    canvas.restoreState()


def paragraph(text: str, style: ParagraphStyle) -> Paragraph:
    text = escape(text)
    text = text.replace("`", "")
    return Paragraph(text.replace("\n", "<br/>"), style)


def code_block(text: str, styles_map: dict[str, ParagraphStyle]) -> Table:
    block = Preformatted(text.rstrip(), styles_map["code"])
    table = Table([[block]], colWidths=[7.0 * inch], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), SECTION_COLORS["surface_alt"]),
                ("BOX", (0, 0), (-1, -1), 0.6, SECTION_COLORS["border"]),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return table


def _flow_node_box(label: str, styles_map: dict[str, ParagraphStyle], width: float, height: float) -> Table:
    label = label.replace("<br/>", "<br />")
    table = Table([[Paragraph(label, styles_map["body"])]], colWidths=[width], rowHeights=[height], hAlign="CENTER")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 1.0, SECTION_COLORS["brand"]),
                ("INNERGRID", (0, 0), (-1, -1), 0, colors.white),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def _flow_box_height(label: str, base_height: float = 0.58 * inch) -> float:
    normalized = label.replace("<br />", "<br/>")
    explicit_lines = normalized.count("<br/>") + 1
    text_only = re.sub(r"<br\s*/?>", " ", normalized)
    estimated_wrap_lines = max(1, (len(text_only) // 24) + 1)
    line_count = max(explicit_lines, estimated_wrap_lines)
    return max(base_height, (0.34 + 0.18 * line_count) * inch)


def _horizontal_arrow(width: float = 0.45 * inch, height: float = 0.38 * inch) -> Drawing:
    drawing = Drawing(width, height)
    mid_y = height / 2
    start_x = 2
    end_x = width - 10
    drawing.add(Line(start_x, mid_y, end_x, mid_y, strokeColor=SECTION_COLORS["brand_dark"], strokeWidth=1.6))
    drawing.add(
        Polygon(
            [end_x, mid_y + 4, width - 2, mid_y, end_x, mid_y - 4],
            fillColor=SECTION_COLORS["brand_dark"],
            strokeColor=SECTION_COLORS["brand_dark"],
        )
    )
    return drawing


def _vertical_arrow(width: float = 0.55 * inch, height: float = 0.42 * inch) -> Drawing:
    drawing = Drawing(width, height)
    mid_x = width / 2
    start_y = height - 2
    end_y = 10
    drawing.add(Line(mid_x, start_y, mid_x, end_y, strokeColor=SECTION_COLORS["brand_dark"], strokeWidth=1.6))
    drawing.add(
        Polygon(
            [mid_x - 4, end_y, mid_x, 2, mid_x + 4, end_y],
            fillColor=SECTION_COLORS["brand_dark"],
            strokeColor=SECTION_COLORS["brand_dark"],
        )
    )
    return drawing


def render_authority_precedence_diagram(styles_map: dict[str, ParagraphStyle]):
    labels = [
        "NBC_2020",
        "QCC_B11_R2",
        "QUEBEC_2015_2022 & QUEBEC_2020_ABOVE",
        "MTL_11_018",
        "MTL_11_018_X",
    ]
    rows = []
    for index, label in enumerate(labels):
        height = 0.41 * inch if "QUEBEC_2015_2022" not in label else 0.43 * inch
        rows.append([_flow_node_box(label, styles_map, 3.7 * inch, height)])
        if index < len(labels) - 1:
            rows.append([_vertical_arrow(width=0.65 * inch, height=0.24 * inch)])

    flow = Table(rows, colWidths=[4.0 * inch], hAlign="CENTER")
    flow.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    return KeepTogether([flow, Spacer(1, 0.08 * inch)])


def render_end_to_end_architecture_diagram(styles_map: dict[str, ParagraphStyle]):
    width = 430
    height = 485
    drawing = Drawing(width, height)

    box_w = 185
    box_h = 28
    x_center = (width - box_w) / 2
    x_left = 18
    x_right = width - x_left - box_w

    colors_fill = SECTION_COLORS["surface"]
    colors_stroke = SECTION_COLORS["brand"]
    colors_text = SECTION_COLORS["brand_dark"]

    def draw_box(x: float, y: float, label: str, w: float = box_w, h: float = box_h) -> tuple[float, float]:
        drawing.add(Rect(x, y, w, h, fillColor=colors_fill, strokeColor=colors_stroke, strokeWidth=1.0))
        if len(label) > 28 and " / " in label:
            parts = label.split(" / ")
            drawing.add(String(x + w / 2, y + h / 2 + 4, parts[0], fontName="Helvetica", fontSize=8.5, fillColor=colors_text, textAnchor="middle"))
            drawing.add(String(x + w / 2, y + h / 2 - 7, "/ " + parts[1], fontName="Helvetica", fontSize=8.5, fillColor=colors_text, textAnchor="middle"))
        else:
            drawing.add(String(x + w / 2, y + h / 2 - 3, label, fontName="Helvetica", fontSize=8.5, fillColor=colors_text, textAnchor="middle"))
        return (x + w / 2, y + h / 2)

    def draw_cylinder(x: float, y: float, label: str, w: float, h: float) -> tuple[float, float]:
        lip_h = 8
        drawing.add(Rect(x, y + lip_h / 2, w, h - lip_h, fillColor=colors_fill, strokeColor=colors_stroke, strokeWidth=1.0))
        drawing.add(Ellipse(x + w / 2, y + h - lip_h / 2, w / 2, lip_h / 2, fillColor=SECTION_COLORS["surface_alt"], strokeColor=colors_stroke, strokeWidth=1.0))
        drawing.add(Ellipse(x + w / 2, y + lip_h / 2, w / 2, lip_h / 2, fillColor=colors_fill, strokeColor=colors_stroke, strokeWidth=1.0))
        drawing.add(Line(x, y + lip_h / 2, x, y + h - lip_h / 2, strokeColor=colors_stroke, strokeWidth=1.0))
        drawing.add(Line(x + w, y + lip_h / 2, x + w, y + h - lip_h / 2, strokeColor=colors_stroke, strokeWidth=1.0))
        if len(label) > 16 and " / " in label:
            parts = label.split(" / ")
            drawing.add(String(x + w / 2, y + h / 2 + 4, parts[0], fontName="Helvetica", fontSize=7.5, fillColor=colors_text, textAnchor="middle"))
            drawing.add(String(x + w / 2, y + h / 2 - 7, "/ " + parts[1], fontName="Helvetica", fontSize=7.5, fillColor=colors_text, textAnchor="middle"))
        elif len(label) > 16:
            words = label.split()
            midpoint = len(words) // 2
            line1 = " ".join(words[:midpoint])
            line2 = " ".join(words[midpoint:])
            drawing.add(String(x + w / 2, y + h / 2 + 4, line1, fontName="Helvetica", fontSize=7.5, fillColor=colors_text, textAnchor="middle"))
            drawing.add(String(x + w / 2, y + h / 2 - 7, line2, fontName="Helvetica", fontSize=7.5, fillColor=colors_text, textAnchor="middle"))
        else:
            drawing.add(String(x + w / 2, y + h / 2 - 3, label, fontName="Helvetica", fontSize=8, fillColor=colors_text, textAnchor="middle"))
        return (x + w / 2, y + h / 2)

    def arrow_head(x: float, y: float, direction: str) -> None:
        if direction == "down":
            points = [x - 4, y + 6, x, y, x + 4, y + 6]
        elif direction == "up":
            points = [x - 4, y - 6, x, y, x + 4, y - 6]
        elif direction == "left":
            points = [x + 6, y + 4, x, y, x + 6, y - 4]
        else:
            points = [x - 6, y + 4, x, y, x - 6, y - 4]
        drawing.add(Polygon(points, fillColor=colors_text, strokeColor=colors_text))

    def vertical_arrow(x: float, y1: float, y2: float) -> None:
        drawing.add(Line(x, y1, x, y2, strokeColor=colors_text, strokeWidth=1.4))
        arrow_head(x, y2, "down")

    def connector(points: list[tuple[float, float]], arrow_to: tuple[float, float] | None = None) -> None:
        for (x1, y1), (x2, y2) in zip(points, points[1:]):
            drawing.add(Line(x1, y1, x2, y2, strokeColor=colors_text, strokeWidth=1.4))
        if arrow_to is not None:
            x_from, y_from = points[-2]
            x_to, y_to = arrow_to
            if abs(x_to - x_from) > abs(y_to - y_from):
                arrow_head(x_to, y_to, "right" if x_to > x_from else "left")
            else:
                arrow_head(x_to, y_to, "down" if y_to < y_from else "up")

    # Branched pipeline with geometry and retrieval in parallel.
    top_y = 422
    schema_y = 367
    article_y = 275
    constraint_y = 220
    precedence_y = 150
    eval_y = 95
    reasoning_y = 45
    reports_y = 0

    draw_box(x_center, top_y, "IFC / BIM Input")
    draw_box(x_center, schema_y, "Normalized BIM Schema")
    draw_box(x_left, 245, "Geometric Fact Extraction", w=170)
    store_w = 82
    store_h = 42
    store_x = x_right + 170 + 18
    store_mid_x = store_x + store_w / 2
    store_y = article_y
    draw_cylinder(store_x, store_y, "Chunk / Embedding Store", w=store_w, h=store_h)
    draw_box(x_right, article_y, "Compliance Corpora / Article Chunk Retrieval", w=170)
    draw_box(x_right, constraint_y, "Constraint Derivation", w=170)
    draw_box(x_center, precedence_y, "Precedence Resolution")
    draw_box(x_center, eval_y, "Deterministic Compliance Evaluation")
    draw_box(x_center, reasoning_y, "Reasoning LLM")
    draw_box(x_center, reports_y, "Reports: JSON / TXT / PDF")

    center_x = x_center + box_w / 2
    vertical_arrow(center_x, top_y, schema_y + box_h)

    schema_bottom = schema_y
    left_top = 245 + box_h
    right_top = article_y + box_h
    left_mid_x = x_left + 170 / 2
    right_mid_x = x_right + 170 / 2

    connector([(center_x, schema_bottom), (center_x, 316), (left_mid_x, 316), (left_mid_x, left_top)], (left_mid_x, 245 + box_h))
    connector([(center_x, schema_bottom), (center_x, 316), (right_mid_x, 316), (right_mid_x, right_top)], (right_mid_x, article_y + box_h))

    # Chunk/Embedding Store -> Compliance Corpora / Article Chunk Retrieval
    connector([(store_x, store_y + store_h / 2), (x_right + 170, article_y + 17)], (x_right + 170, article_y + 17))

    # Article Retrieval -> Constraint Derivation
    vertical_arrow(right_mid_x, article_y, constraint_y + box_h)

    precedence_top = precedence_y + box_h
    eval_top = eval_y + box_h

    # Constraint Derivation -> Precedence Resolution
    connector([(right_mid_x, constraint_y), (right_mid_x, 190), (center_x, 190), (center_x, precedence_top)], (center_x, precedence_top))

    # Geometric Fact Extraction -> Deterministic Evaluation
    connector([(left_mid_x, 245), (left_mid_x, 142), (center_x, 142), (center_x, eval_top)], (center_x, eval_top))

    # Precedence Resolution -> Deterministic Evaluation
    vertical_arrow(center_x, precedence_y, eval_y + box_h)

    vertical_arrow(center_x, eval_y, reasoning_y + box_h)
    vertical_arrow(center_x, reasoning_y, reports_y + box_h)

    container = Table([[drawing]], colWidths=[4.8 * inch], hAlign="CENTER")
    container.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    return KeepTogether([container, Spacer(1, 0.08 * inch)])


def render_flowchart(text: str, styles_map: dict[str, ParagraphStyle]):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines or not lines[0].startswith("flowchart"):
        return code_block(text, styles_map)

    if (
        "NBC_2020" in text
        and "QCC_B11_R2" in text
        and "QUEBEC_2015_2022" in text
        and "MTL_11_018_X" in text
    ):
        return render_authority_precedence_diagram(styles_map)
    if (
        "IFC / BIM Input" in text
        and "Normalized BIM Schema" in text
        and "Reports: JSON / TXT / PDF" in text
    ):
        return render_end_to_end_architecture_diagram(styles_map)

    direction = lines[0].split()[1] if len(lines[0].split()) > 1 else "TD"
    node_pattern = re.compile(r"([A-Za-z0-9_]+)\[(.+?)\]")
    edge_pattern = re.compile(r"([A-Za-z0-9_]+)\s*-->\s*([A-Za-z0-9_]+)")

    labels: dict[str, str] = {}
    edges: list[tuple[str, str]] = []
    for line in lines[1:]:
        for node_id, label in node_pattern.findall(line):
            labels[node_id] = label
        edge_match = edge_pattern.search(line)
        if edge_match:
            edges.append((edge_match.group(1), edge_match.group(2)))

    if not edges:
        return code_block(text, styles_map)

    ordered_nodes = [edges[0][0]]
    for _, target in edges:
        if target not in ordered_nodes:
            ordered_nodes.append(target)

    if direction in {"LR", "RL"}:
        row = []
        for index, node_id in enumerate(ordered_nodes):
            label = labels.get(node_id, node_id)
            row.append(_flow_node_box(label, styles_map, 1.85 * inch, _flow_box_height(label, 0.66 * inch)))
            if index < len(ordered_nodes) - 1:
                row.append(_horizontal_arrow())
        flow = Table([row], hAlign="CENTER")
        flow.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        return KeepTogether([flow, Spacer(1, 0.08 * inch)])

    rows = []
    for index, node_id in enumerate(ordered_nodes):
        label = labels.get(node_id, node_id)
        rows.append([_flow_node_box(label, styles_map, 3.95 * inch, _flow_box_height(label, 0.7 * inch))])
        if index < len(ordered_nodes) - 1:
            rows.append([_vertical_arrow()])
    flow = Table(rows, hAlign="CENTER")
    flow.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return KeepTogether([flow, Spacer(1, 0.08 * inch)])


def intro_panel(styles_map: dict[str, ParagraphStyle]) -> Table:
    text = "A precedence-aware BIM compliance system that connects legal code layers, geometric model facts, and explainable audit reporting."
    panel = Table([[paragraph(text, styles_map["body"])]], colWidths=[7.0 * inch], hAlign="LEFT")
    panel.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), SECTION_COLORS["cover_band"]),
                ("BOX", (0, 0), (-1, -1), 0.8, SECTION_COLORS["brand"]),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return panel


def markdown_to_story(source: Path) -> list:
    styles_map = styles()
    lines = source.read_text(encoding="utf-8").splitlines()
    story: list = [
        Spacer(1, 0.18 * inch),
        Table([[brand_logo(), paragraph("High-Level Project Report", styles_map["cover_title"])]], colWidths=[1.2 * inch, 5.9 * inch], hAlign="LEFT"),
        paragraph("BIM Compliance Geometric Reasoning", styles_map["cover_subtitle"]),
        intro_panel(styles_map),
        Spacer(1, 0.1 * inch),
    ]

    in_code = False
    code_language = ""
    code_lines: list[str] = []
    paragraph_lines: list[str] = []
    seen_h1 = False
    skipped_cover_h2 = False

    def flush_paragraph() -> None:
        nonlocal paragraph_lines
        if not paragraph_lines:
            return
        text = " ".join(line.strip() for line in paragraph_lines).strip()
        if text:
            story.append(paragraph(text, styles_map["body"]))
            story.append(Spacer(1, 0.08 * inch))
        paragraph_lines = []

    for raw_line in lines:
        line = raw_line.rstrip()

        if line.startswith("```"):
            flush_paragraph()
            if in_code:
                if code_language == "mermaid":
                    diagram_text = "\n".join(code_lines)
                    if (
                        "NBC_2020" in diagram_text
                        and "QCC_B11_R2" in diagram_text
                        and "MTL_11_018_X" in diagram_text
                    ):
                        story.append(paragraph("Diagram / Flowchart (Lowest to Highest)", styles_map["h3"]))
                    else:
                        story.append(paragraph("Diagram / Flowchart", styles_map["h3"]))
                    story.append(render_flowchart(diagram_text, styles_map))
                else:
                    story.append(code_block("\n".join(code_lines), styles_map))
                story.append(Spacer(1, 0.12 * inch))
                in_code = False
                code_language = ""
                code_lines = []
            else:
                in_code = True
                code_language = line[3:].strip()
            continue

        if in_code:
            code_lines.append(line)
            continue

        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            continue

        if stripped == "---":
            flush_paragraph()
            story.append(Spacer(1, 0.06 * inch))
            rule = Table([[""]], colWidths=[7.0 * inch], rowHeights=[0.02 * inch])
            rule.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), SECTION_COLORS["border"])]))
            story.append(rule)
            story.append(Spacer(1, 0.12 * inch))
            continue

        if stripped.startswith("# "):
            flush_paragraph()
            if not seen_h1:
                seen_h1 = True
                continue
            story.append(PageBreak())
            story.append(paragraph(stripped[2:], styles_map["h1"]))
            continue

        if stripped.startswith("## "):
            flush_paragraph()
            if not skipped_cover_h2:
                skipped_cover_h2 = True
                continue
            story.append(paragraph(stripped[3:], styles_map["h1"]))
            continue

        if stripped.startswith("### "):
            flush_paragraph()
            story.append(paragraph(stripped[4:], styles_map["h2"]))
            continue

        if stripped.startswith("- "):
            flush_paragraph()
            story.append(Paragraph(escape(stripped[2:]).replace("`", ""), styles_map["bullet"], bulletText="•"))
            story.append(Spacer(1, 0.03 * inch))
            continue

        if len(stripped) > 2 and stripped[0].isdigit() and stripped[1:].lstrip().startswith("."):
            flush_paragraph()
            num, body = stripped.split(".", 1)
            story.append(Paragraph(escape(body.strip()).replace("`", ""), styles_map["number"], bulletText=f"{num}."))
            story.append(Spacer(1, 0.03 * inch))
            continue

        paragraph_lines.append(stripped)

    flush_paragraph()
    return story


def render_markdown_pdf(source: Path, output: Path) -> None:
    doc = SimpleDocTemplate(
        str(output),
        pagesize=letter,
        leftMargin=0.7 * inch,
        rightMargin=0.7 * inch,
        topMargin=0.85 * inch,
        bottomMargin=0.75 * inch,
        title=source.stem,
        author="BIM Compliance Geometric Reasoning",
    )
    doc.build(markdown_to_story(source), onFirstPage=page_chrome, onLaterPages=page_chrome)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    source = Path(args.source)
    output = Path(args.output)
    render_markdown_pdf(source, output)
    print(f"Wrote PDF report to {output}")


if __name__ == "__main__":
    main()
