import os
from typing import Dict, Any, List

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Image,
    Table,
    TableStyle,
    PageBreak,
    KeepTogether,
)
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT


def _img(path: str, max_w_in: float, max_h_in: float) -> Image:
    img = Image(path)
    img._restrictSize(max_w_in * inch, max_h_in * inch)
    return img


def build_pdf(payload: Dict[str, Any], analysis: Dict[str, Any]) -> str:
    out_dir = payload["out_dir"]
    pdf_path = os.path.join(out_dir, "report.pdf")

    styles = getSampleStyleSheet()

    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=landscape(letter),
        leftMargin=24,
        rightMargin=24,
        topMargin=24,
        bottomMargin=24,
    )

    story = []
    story.append(Paragraph("UK PDP Readiness Audit", styles["Title"]))
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"<b>URL:</b> {payload['url']}", styles["BodyText"]))
    story.append(Spacer(1, 10))

    # ---------- Findings table FIRST ----------
    story.append(Paragraph("<b>Findings (Actionable)</b>", styles["Heading2"]))
    story.append(Spacer(1, 8))

    findings: List[Dict[str, Any]] = analysis.get("findings", [])

    cell_style = ParagraphStyle(
        name="Cell",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=7,
        leading=9,
        alignment=TA_LEFT,
        wordWrap="CJK",
    )

    header_style = ParagraphStyle(
        name="HeaderCell",
        parent=cell_style,
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
    )

    def P(txt: Any, style: ParagraphStyle = cell_style) -> Paragraph:
        s = "" if txt is None else str(txt)
        s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        s = s.replace("\n", "<br/>")
        return Paragraph(s, style)

    table_data = [
        [
            P("Severity", header_style),
            P("Owner", header_style),
            P("Category", header_style),
            P("Issue", header_style),
            P("Recommendation", header_style),
            P("Evidence", header_style),
        ]
    ]

    for f in findings:
        table_data.append(
            [
                P(f.get("severity", "")),
                P(f.get("owner", "")),
                P(f.get("category", "")),
                P(f.get("issue", "")),
                P(f.get("recommendation", "")),
                P(f.get("evidence_screenshot", "")),
            ]
        )

    col_widths = [
        0.7 * inch,
        0.8 * inch,
        0.9 * inch,
        2.4 * inch,
        4.8 * inch,
        0.9 * inch,
    ]

    tbl = Table(
        table_data,
        colWidths=col_widths,
        repeatRows=1,
        splitByRow=1,
    )

    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
            ]
        )
    )

    story.append(tbl)

    story.append(PageBreak())

    # ---------- Evidence Screenshots ----------
    story.append(Paragraph("<b>Evidence Screenshots</b>", styles["Heading2"]))
    story.append(Spacer(1, 6))

    def add_shot(title: str, key: str, w: float, h: float) -> None:
        p = payload["paths"].get(key)
        if not p or not os.path.exists(p):
            return
        block = KeepTogether(
            [
                Paragraph(title, styles["Heading3"]),
                Spacer(1, 4),
                _img(p, w, h),
                Spacer(1, 10),
            ]
        )
        story.append(block)

    # Keep captions + images together; choose sizes that fit in landscape letter
    add_shot("Baseline PDP (full page; Details expanded if possible)", "full_page", 10.0, 5.8)
    add_shot("Care section (scrolled view)", "care_view", 10.0, 4.2)
    add_shot("Size & Fit section (scrolled view)", "size_fit_view", 10.0, 4.2)
    add_shot("Size chart / size guide (modal if present)", "size_chart_view", 10.0, 4.2)

    doc.build(story)
    return pdf_path