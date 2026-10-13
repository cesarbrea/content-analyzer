"""PDF report for one analysis run (reportlab; charts are the app's Altair charts rendered to PNG)."""
import io
from xml.sax.saxutils import escape

import vl_convert as vlc
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from charts import alignment_chart, tag_chart
from core.scoring import TagScore
from core.video import fmt_time

GITHUB_URL = "https://github.com/cesarbrea/content-analyzer"
CONTACT_EMAIL = "cesar.brea@alixpartners.com"
CHART_WIDTH_PX = 520


def _t(text: str) -> str:
    """Escape for Paragraph markup; the built-in fonts only cover cp1252, so swap other characters."""
    text = text.replace("−", "-").replace("‑", "-")
    return escape(text.encode("cp1252", "replace").decode("cp1252")).replace("\n", "<br/>")


def _chart_image(chart, max_width: float) -> Image:
    png = vlc.vegalite_to_png(chart.properties(width=CHART_WIDTH_PX).to_json(), scale=2)
    img = Image(io.BytesIO(png))
    ratio = min(1.0, max_width / img.drawWidth)
    img.drawWidth *= ratio
    img.drawHeight *= ratio
    return img


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.grey)
    canvas.drawString(doc.leftMargin, 0.5 * inch, f"{GITHUB_URL}  |  {CONTACT_EMAIL}")
    canvas.drawRightString(letter[0] - doc.rightMargin, 0.5 * inch, f"Page {doc.page}")
    canvas.restoreState()


def build_report(result: dict, shown: list[TagScore], product_desc: str, brief: str) -> bytes:
    """Sections, in order: product description, brief, filename, caption, tag chart, alignment chart,
    explanations, suggestions, tag table, session cost / runs / model. `shown` is the tag list currently
    on screen; `brief` is the one used for the evaluation (falls back to the current brief)."""
    ss = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=ss["BodyText"], fontSize=10, leading=13)
    cell = ParagraphStyle("cell", parent=body, fontSize=8, leading=10)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], spaceBefore=14, spaceAfter=4)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, title="Content Analyzer Report",
                            author=CONTACT_EMAIL, leftMargin=0.8 * inch, rightMargin=0.8 * inch,
                            topMargin=0.8 * inch, bottomMargin=0.9 * inch)
    width = doc.width
    alignment = result.get("alignment")
    brief_used = alignment["brief"] if alignment else brief

    story = [Paragraph("Content Analyzer Report", ss["Title"])]

    def section(title, text):
        story.append(Paragraph(title, h2))
        story.append(Paragraph(_t(text.strip()) if text and text.strip() else "<i>None provided.</i>", body))

    section("Product description", product_desc)
    section("Creative brief used", brief_used)
    section("Asset analyzed", result["filename"])
    section("Caption", result["caption"])

    if shown:
        story.append(Paragraph("Tag certainty", h2))
        story.append(_chart_image(tag_chart(shown)[0], width))

    if alignment:
        story.append(Paragraph(f"Creative brief alignment (overall {alignment['overall']:+.2f})", h2))
        story.append(_chart_image(alignment_chart(alignment)[0], width))
        story.append(Paragraph("Explanations", h2))
        for d, v in alignment["dimensions"].items():
            story.append(Paragraph(f"<b>{d.capitalize()} ({v['score']:+.2f}):</b> {_t(v['rationale'])}", body))
            story.append(Spacer(1, 4))
        story.append(Paragraph("Suggestions to align more closely with the brief", h2))
        for s in alignment["suggestions"]:
            story.append(Paragraph(f"• {_t(s)}", body))
            story.append(Spacer(1, 3))

    if shown:
        story.append(Paragraph("Tags", h2))
        rows = [[Paragraph(f"<b>{c}</b>", cell) for c in
                 ("Tag", "Source", "Certainty", "Agreement", "Self-conf.", "Runs", "Evidence")]]
        for s in shown:
            rows.append([Paragraph(_t(s.tag), cell), s.source, f"{s.certainty:.0%}", f"{s.agreement:.0%}",
                         f"{s.mean_self_confidence:.0%}", str(s.runs_seen), Paragraph(_t(s.evidence), cell)])
        table = Table(rows, repeatRows=1, colWidths=[width * f for f in (.17, .09, .1, .1, .1, .07, .37)])
        table.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eeeeee")),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(table)

    narr = result.get("story")
    if narr:
        story.append(Paragraph("Story", h2))
        story.append(Paragraph(_t(narr["logline"]), body))
        story.append(Spacer(1, 4))
        for b in narr["beats"]:
            story.append(Paragraph(f"<b>{fmt_time(b['start'])}-{fmt_time(b['end'])}</b> {_t(b['summary'])}", body))
        story.append(Paragraph("Characters", h2))
        for c in narr["characters"]:
            story.append(Paragraph(f"• <b>{_t(c['label'])}</b> ({_t(c['role'])}, {c['presence']}): "
                                   f"{_t(c['description'])}", body))
        story.append(Spacer(1, 4))
        story.append(Paragraph(f"<b>Arc:</b> {_t(narr['arc'])}", body))
        if narr.get("scores"):
            story.append(Paragraph("Story alignment with the brief", h2))
            for d, v in narr["scores"].items():
                story.append(Paragraph(f"<b>{d.replace('_', ' ').capitalize()} ({v['score']:+.2f}):</b> "
                                       f"{_t(v['rationale'])}", body))
            for sug in narr["suggestions"]:
                story.append(Paragraph(f"• {_t(sug)}", body))

    story.append(Paragraph("Session", h2))
    story.append(Paragraph(
        f"Cost: ${result['cost_usd']:.4f}<br/>Runs per asset (K): {result['k']}<br/>"
        f"Model: {_t(result['model'])}", body))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()
