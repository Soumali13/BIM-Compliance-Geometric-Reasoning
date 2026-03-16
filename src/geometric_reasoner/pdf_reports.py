from __future__ import annotations

from html import escape
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from geometric_reasoner.bim_normalized_models import NormalizedProject, NormalizedSpace, NormalizedUnit
from geometric_reasoner.shared_data_models import ArticleChunk, AuditReport, CodeConstraint


STATUS_COLORS = {
    "PASS": colors.HexColor("#1f7a4d"),
    "FAIL": colors.HexColor("#b42318"),
    "UNKNOWN": colors.HexColor("#b54708"),
}

SECTION_COLORS = {
    "header": colors.HexColor("#0F172A"),
    "subheader": colors.HexColor("#1E3A5F"),
    "border": colors.HexColor("#cbd5e1"),
    "muted": colors.HexColor("#475569"),
    "surface": colors.HexColor("#F8FAFC"),
    "surface_alt": colors.HexColor("#EEF2F7"),
    "brand": colors.HexColor("#0B6BCB"),
    "accent": colors.HexColor("#C98A2E"),
    "brand_dark": colors.HexColor("#0B2747"),
    "cover_band": colors.HexColor("#E8F1FB"),
}


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "AuditTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=24,
            textColor=SECTION_COLORS["header"],
            spaceAfter=6,
        ),
        "subtitle": ParagraphStyle(
            "AuditSubtitle",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=13,
            textColor=SECTION_COLORS["muted"],
            spaceAfter=12,
        ),
        "cover_title": ParagraphStyle(
            "AuditCoverTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=26,
            leading=32,
            textColor=SECTION_COLORS["header"],
            spaceAfter=8,
        ),
        "cover_tag": ParagraphStyle(
            "AuditCoverTag",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=12,
            textColor=SECTION_COLORS["brand"],
            spaceAfter=8,
        ),
        "cover_meta": ParagraphStyle(
            "AuditCoverMeta",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=SECTION_COLORS["subheader"],
        ),
        "section": ParagraphStyle(
            "AuditSection",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=SECTION_COLORS["brand_dark"],
            spaceBefore=10,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "AuditBody",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            textColor=colors.black,
        ),
        "small": ParagraphStyle(
            "AuditSmall",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=SECTION_COLORS["muted"],
        ),
        "label": ParagraphStyle(
            "AuditLabel",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            textColor=SECTION_COLORS["subheader"],
        ),
        "badge": ParagraphStyle(
            "AuditBadge",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=10,
            textColor=colors.white,
            alignment=TA_CENTER,
        ),
    }


def _p(text: str, style: ParagraphStyle) -> Paragraph:
    escaped = escape(text).replace("\n", "<br/>")
    return Paragraph(escaped, style)


def _status_badge(status: str, styles: dict[str, ParagraphStyle]) -> Table:
    badge = Table([[Paragraph(status, styles["badge"])]], colWidths=[0.95 * inch])
    badge.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), STATUS_COLORS.get(status, SECTION_COLORS["muted"])),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOX", (0, 0), (-1, -1), 0, colors.white),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return badge


def _brand_logo(width: float = 0.95 * inch, height: float = 0.95 * inch) -> Drawing:
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


def _info_table(rows: list[tuple[str, str]], styles: dict[str, ParagraphStyle], widths: tuple[float, float]) -> Table:
    data = [[_p(label, styles["label"]), _p(value, styles["body"])] for label, value in rows]
    table = Table(data, colWidths=list(widths), hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), SECTION_COLORS["surface"]),
                ("BOX", (0, 0), (-1, -1), 0.6, SECTION_COLORS["border"]),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, SECTION_COLORS["border"]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return table


def _finding_card(report: AuditReport, finding, styles: dict[str, ParagraphStyle]) -> list:
    header = Table(
        [
            [
                _p(f"{finding.parameter}  |  {finding.active_authority}", styles["label"]),
                _status_badge(finding.status, styles),
            ]
        ],
        colWidths=[5.65 * inch, 1.0 * inch],
        hAlign="LEFT",
    )
    header.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, 0), SECTION_COLORS["surface_alt"]),
                ("BOX", (0, 0), (-1, -1), 0.6, SECTION_COLORS["border"]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )

    fact_value = (
        f"{finding.fact_value:.1f} {finding.fact_unit}"
        if finding.fact_value is not None and finding.fact_unit
        else "Missing"
    )
    requirement = f"{finding.operator} {finding.required_value:.1f} {finding.required_unit}"
    citations = ", ".join(
        f"{citation.authority}:{citation.article} {citation.title}" for citation in finding.citations
    )
    override_trace = (
        " -> ".join(
            f"{trace.authority}:{trace.article} {trace.operator} {trace.value:.1f} {trace.unit}"
            for trace in finding.override_trace
        )
        if finding.override_trace
        else "None"
    )
    rows = [
        ("Reason", finding.reason),
        ("Source", f"{finding.source_element or 'missing'}.{finding.source_measurement or finding.parameter}"),
        ("Fact", fact_value),
        ("Requirement", requirement),
        ("Jurisdiction", finding.active_jurisdiction),
        ("Citations", citations or "None"),
        ("Override trace", override_trace),
    ]
    if finding.expected_element_types:
        rows.append(("Expected from", ", ".join(finding.expected_element_types)))

    return [header, _info_table(rows, styles, (1.4 * inch, 5.45 * inch)), Spacer(1, 0.16 * inch)]


def _page_chrome(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFillColor(SECTION_COLORS["cover_band"])
    canvas.rect(doc.leftMargin, doc.pagesize[1] - 0.72 * inch, doc.pagesize[0] - doc.leftMargin - doc.rightMargin, 0.28 * inch, fill=1, stroke=0)
    canvas.setStrokeColor(SECTION_COLORS["brand"])
    canvas.setLineWidth(1.2)
    canvas.line(doc.leftMargin, doc.pagesize[1] - 0.48 * inch, doc.pagesize[0] - doc.rightMargin, doc.pagesize[1] - 0.48 * inch)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(SECTION_COLORS["muted"])
    canvas.drawString(doc.leftMargin, 0.45 * inch, "BIM Compliance Geometric Reasoning")
    canvas.drawRightString(doc.pagesize[0] - doc.rightMargin, 0.45 * inch, f"Page {doc.page}")
    canvas.restoreState()


def _status_tile(status: str, count: int) -> Drawing:
    drawing = Drawing(2.15 * inch, 1.0 * inch)
    drawing.add(
        Rect(
            0,
            0,
            2.15 * inch,
            1.0 * inch,
            strokeColor=SECTION_COLORS["border"],
            fillColor=SECTION_COLORS["surface_alt"],
        )
    )
    drawing.add(String(14, 42, status, fontName="Helvetica-Bold", fontSize=11, fillColor=STATUS_COLORS[status]))
    drawing.add(String(14, 18, str(count), fontName="Helvetica-Bold", fontSize=22, fillColor=SECTION_COLORS["header"]))
    return drawing


def _status_chart(counts: dict[str, int]) -> Drawing:
    drawing = Drawing(6.8 * inch, 2.35 * inch)
    chart = VerticalBarChart()
    chart.x = 44
    chart.y = 28
    chart.height = 115
    chart.width = 380
    chart.data = [[counts["FAIL"], counts["UNKNOWN"], counts["PASS"]]]
    chart.categoryAxis.categoryNames = ["FAIL", "UNKNOWN", "PASS"]
    chart.categoryAxis.labels.fontName = "Helvetica"
    chart.categoryAxis.labels.fontSize = 8
    chart.valueAxis.labels.fontName = "Helvetica"
    chart.valueAxis.labels.fontSize = 8
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = max(1, max(counts.values()))
    chart.valueAxis.valueStep = max(1, chart.valueAxis.valueMax // 4 or 1)
    chart.barWidth = 0.4 * inch
    chart.groupSpacing = 0.45 * inch
    chart.barSpacing = 0.08 * inch
    chart.bars[0].fillColor = colors.HexColor("#64748b")
    chart.bars[0].strokeColor = colors.HexColor("#64748b")
    drawing.add(chart)

    legend_x = 455
    for offset, (label, color) in enumerate(
        [("FAIL", STATUS_COLORS["FAIL"]), ("UNKNOWN", STATUS_COLORS["UNKNOWN"]), ("PASS", STATUS_COLORS["PASS"])]
    ):
        y = 124 - offset * 22
        drawing.add(Rect(legend_x, y, 10, 10, fillColor=color, strokeColor=color))
        drawing.add(String(legend_x + 16, y + 1, label, fontName="Helvetica", fontSize=8, fillColor=SECTION_COLORS["muted"]))
    return drawing


def render_space_audit_pdf(
    pdf_path: Path,
    report: AuditReport,
    normalized_path: Path,
    unit: NormalizedUnit,
    space: NormalizedSpace,
    retrieved_articles: list[ArticleChunk],
    constraints: list[CodeConstraint],
) -> None:
    styles = _styles()
    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=letter,
        leftMargin=0.7 * inch,
        rightMargin=0.7 * inch,
        topMargin=0.85 * inch,
        bottomMargin=0.75 * inch,
        title=f"Space Audit {space.space_id}",
        author="BIM Compliance Geometric Reasoning",
    )

    story = [
        Table(
            [[_brand_logo(), _p("Space Audit Report", styles["title"])]],
            colWidths=[1.05 * inch, 6.15 * inch],
            hAlign="LEFT",
        ),
        _p(f"{space.name} ({report.room_type})", styles["subtitle"]),
    ]

    header = Table(
        [
            [
                _info_table(
                    [
                        ("Status", report.status),
                        ("Unit", unit.unit_id),
                        ("Space ID", space.space_id),
                        ("Constraint source", str(report.metadata.get("constraint_source", "unknown"))),
                        ("Retrieval mode", str(report.metadata.get("retrieval_mode", "unknown"))),
                        ("Reasoning mode", str(report.metadata.get("reasoning_mode", "deterministic"))),
                        ("Reasoning generation", str(report.metadata.get("reasoning_generation_mode", "deterministic"))),
                    ],
                    styles,
                    (1.55 * inch, 3.45 * inch),
                ),
                _info_table(
                    [
                        ("Retrieved articles", str(len(retrieved_articles))),
                        ("Derived constraints", str(len(constraints))),
                        ("Findings", str(report.metadata.get("finding_count", len(report.checks)))),
                    ],
                    styles,
                    (1.55 * inch, 2.35 * inch),
                ),
            ]
        ],
        colWidths=[4.9 * inch, 2.45 * inch],
        hAlign="LEFT",
    )
    header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.extend([header, Spacer(1, 0.16 * inch)])

    if report.llm_reasoning is not None:
        story.extend(
            [
                _p("Reasoning", styles["section"]),
                _info_table(
                    [
                        ("Summary", report.llm_reasoning.summary),
                        ("Precedence", report.llm_reasoning.precedence_explanation),
                        (
                            "Next measurements",
                            ", ".join(report.llm_reasoning.recommended_next_measurements) or "None",
                        ),
                    ],
                    styles,
                    (1.55 * inch, 5.95 * inch),
                ),
                Spacer(1, 0.16 * inch),
            ]
        )

    story.append(_p("Compliance Findings", styles["section"]))
    if report.checks:
        for finding in report.checks:
            story.extend(_finding_card(report, finding, styles))
    else:
        story.extend([_p("No compliance findings were produced for this space.", styles["body"]), Spacer(1, 0.12 * inch)])

    story.append(_p("Retrieved Context", styles["section"]))
    article_rows = [
        [
            _p("Authority", styles["label"]),
            _p("Article", styles["label"]),
            _p("Title", styles["label"]),
        ]
    ]
    for article in retrieved_articles[:10]:
        article_rows.append(
            [
                _p(article.authority, styles["body"]),
                _p(article.article, styles["body"]),
                _p(article.title, styles["body"]),
            ]
        )
    if len(article_rows) == 1:
        article_rows.append([_p("None", styles["body"]), _p("-", styles["body"]), _p("-", styles["body"])])
    article_table = Table(article_rows, colWidths=[1.35 * inch, 1.05 * inch, 4.95 * inch], hAlign="LEFT")
    article_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), SECTION_COLORS["surface_alt"]),
                ("BOX", (0, 0), (-1, -1), 0.6, SECTION_COLORS["border"]),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, SECTION_COLORS["border"]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.extend([article_table, Spacer(1, 0.16 * inch)])

    if report.unmatched_facts:
        story.append(_p("Unmatched Facts", styles["section"]))
        unmatched_rows = [("Fact", "Mapping")]
        for fact in report.unmatched_facts:
            unmatched_rows.append((f"{fact.source_element}.{fact.source_measurement}", fact.parameter))
        story.append(_info_table(unmatched_rows, styles, (2.75 * inch, 4.75 * inch)))

    doc.build(story, onFirstPage=_page_chrome, onLaterPages=_page_chrome)


def render_unit_audit_pdf(
    pdf_path: Path,
    normalized_path: Path,
    project: NormalizedProject,
    space_results: list[tuple[NormalizedUnit, NormalizedSpace, AuditReport]],
    retrieval_mode: str,
    reasoning_mode: str,
    generated_at: str,
) -> None:
    styles = _styles()
    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=letter,
        leftMargin=0.7 * inch,
        rightMargin=0.7 * inch,
        topMargin=0.85 * inch,
        bottomMargin=0.75 * inch,
        title=f"Project Audit {project.project_id}",
        author="BIM Compliance Geometric Reasoning",
    )

    counts = {"PASS": 0, "FAIL": 0, "UNKNOWN": 0}
    for _, _, report in space_results:
        counts[report.status] += 1
    overall_status = min((report.status for _, _, report in space_results), key=lambda status: {"FAIL": 0, "UNKNOWN": 1, "PASS": 2}[status])

    cover_narrative = Table(
        [[_p("Structured code reasoning across BIM geometry, layered corpora, and precedence-aware rule resolution.", styles["body"])]],
        colWidths=[7.15 * inch],
        hAlign="LEFT",
    )
    cover_narrative.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), SECTION_COLORS["cover_band"]),
                ("BOX", (0, 0), (-1, -1), 0.6, SECTION_COLORS["brand"]),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )

    story = [
        Spacer(1, 0.42 * inch),
        Table(
            [[_brand_logo(1.2 * inch, 1.2 * inch), _p("Audit Summary", styles["cover_title"])]],
            colWidths=[1.3 * inch, 5.95 * inch],
            hAlign="LEFT",
        ),
        _p("BIM Compliance Geometric Reasoning", styles["cover_tag"]),
        _p(project.name, styles["subtitle"]),
        _p("Compliance Audit Package", styles["cover_meta"]),
        _info_table(
            [
                ("Project ID", project.project_id),
                ("Units", ", ".join(unit.unit_id for unit in project.units)),
                ("Overall status", overall_status),
                ("Audited spaces", str(len(space_results))),
                ("Retrieval mode", retrieval_mode),
                ("Reasoning mode", reasoning_mode),
                ("Generated at", generated_at),
            ],
            styles,
            (1.65 * inch, 5.85 * inch),
        ),
        Spacer(1, 0.12 * inch),
        cover_narrative,
        Spacer(1, 0.16 * inch),
        _p("Portfolio Snapshot", styles["section"]),
    ]

    tile_row = Table(
        [[_status_tile("FAIL", counts["FAIL"]), _status_tile("UNKNOWN", counts["UNKNOWN"]), _status_tile("PASS", counts["PASS"])]],
        colWidths=[2.2 * inch, 2.2 * inch, 2.2 * inch],
        hAlign="LEFT",
    )
    tile_row.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story.extend(
        [
            tile_row,
            Spacer(1, 0.22 * inch),
            _p("Status Distribution", styles["section"]),
            _status_chart(counts),
            PageBreak(),
            Table(
                [[_brand_logo(0.82 * inch, 0.82 * inch), _p("Audit Detail", styles["title"])]],
                colWidths=[0.95 * inch, 6.25 * inch],
                hAlign="LEFT",
            ),
            _p(project.name, styles["subtitle"]),
        ]
    )

    count_table = Table(
        [
            [
                _status_badge("FAIL", styles),
                _status_badge("UNKNOWN", styles),
                _status_badge("PASS", styles),
            ],
            [
                _p(str(counts["FAIL"]), styles["title"]),
                _p(str(counts["UNKNOWN"]), styles["title"]),
                _p(str(counts["PASS"]), styles["title"]),
            ],
        ],
        colWidths=[2.25 * inch, 2.25 * inch, 2.25 * inch],
        hAlign="LEFT",
    )
    count_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.6, SECTION_COLORS["border"]),
                ("BACKGROUND", (0, 1), (-1, 1), SECTION_COLORS["surface"]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 1), (-1, 1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.extend([count_table, Spacer(1, 0.18 * inch), _p("Space Status Matrix", styles["section"])])

    summary_rows = [
        [
            _p("Unit", styles["label"]),
            _p("Space", styles["label"]),
            _p("Room type", styles["label"]),
            _p("Status", styles["label"]),
            _p("Reasoning", styles["label"]),
        ]
    ]
    for unit, space, report in space_results:
        summary_rows.append(
            [
                _p(unit.unit_id, styles["body"]),
                _p(space.name, styles["body"]),
                _p(report.room_type, styles["body"]),
                _p(report.status, styles["body"]),
                _p(str(report.metadata.get("reasoning_generation_mode", "deterministic")), styles["body"]),
            ]
        )
    summary_table = Table(
        summary_rows,
        colWidths=[1.05 * inch, 2.2 * inch, 1.85 * inch, 0.8 * inch, 1.35 * inch],
        repeatRows=1,
        hAlign="LEFT",
    )
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), SECTION_COLORS["surface_alt"]),
                ("BOX", (0, 0), (-1, -1), 0.6, SECTION_COLORS["border"]),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, SECTION_COLORS["border"]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.extend([summary_table, Spacer(1, 0.18 * inch)])

    exceptions = [(unit, space, report) for unit, space, report in space_results if report.status in {"FAIL", "UNKNOWN"}]
    if exceptions:
        story.append(_p("Spaces Requiring Attention", styles["section"]))
        for unit, space, report in exceptions:
            title_table = Table(
                [[_p(f"{unit.unit_id} :: {space.name}", styles["label"]), _status_badge(report.status, styles)]],
                colWidths=[6.2 * inch, 1.0 * inch],
                hAlign="LEFT",
            )
            title_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (0, 0), SECTION_COLORS["surface_alt"]),
                        ("BOX", (0, 0), (-1, -1), 0.6, SECTION_COLORS["border"]),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 8),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                        ("TOPPADDING", (0, 0), (-1, -1), 7),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                    ]
                )
            )
            reasoning = report.llm_reasoning.summary if report.llm_reasoning is not None else "No reasoning summary available."
            next_measurements = (
                ", ".join(report.llm_reasoning.recommended_next_measurements)
                if report.llm_reasoning is not None and report.llm_reasoning.recommended_next_measurements
                else "None"
            )
            story.extend(
                [
                    title_table,
                    _info_table(
                        [
                            ("Room type", report.room_type),
                            ("Reason", reasoning),
                            ("Next measurements", next_measurements),
                        ],
                        styles,
                        (1.55 * inch, 5.95 * inch),
                    ),
                    Spacer(1, 0.16 * inch),
                ]
            )

    doc.build(story, onFirstPage=_page_chrome, onLaterPages=_page_chrome)
