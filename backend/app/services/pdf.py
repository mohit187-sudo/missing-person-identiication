"""Minimal, dependency-light PDF report generation (fpdf2)."""
from __future__ import annotations

from datetime import datetime
from typing import List


def _pdf():
    from fpdf import FPDF

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    return pdf


def _row(pdf, values: List[str], widths: List[int], bold: bool = False) -> None:
    from fpdf.enums import XPos, YPos

    pdf.set_font("Helvetica", "B" if bold else "", 8 if not bold else 9)
    for v, w in zip(values, widths):
        pdf.cell(w, 6 if not bold else 7, str(v)[:40], border=1, new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.ln(7 if bold else 6)


def build_video_report_pdf(video, rows: List[dict], disclaimer: str) -> bytes:
    from fpdf.enums import XPos, YPos

    pdf = _pdf()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "Video Analysis Review Report", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 6, f"Video: {video.title} ({video.id})", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.multi_cell(0, 6, f"Generated: {datetime.utcnow().isoformat()}Z", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "Important notice", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 9)
    pdf.multi_cell(0, 5, disclaimer, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)
    headers = ["Timestamp", "Case", "Score", "Threshold", "Model", "Review"]
    widths = [24, 34, 20, 22, 40, 30]
    _row(pdf, headers, widths, bold=True)
    for r in rows[:200]:
        _row(
            pdf,
            [
                f"{(r.get('timestamp_seconds') or 0):.2f}s",
                str(r.get("candidate_case_number", "")),
                f"{r.get('similarity_score', 0):.4f}",
                f"{r.get('threshold_used', 0):.2f}",
                f"{r.get('model_name', '')} {r.get('model_version', '')}",
                str(r.get("review_status", "")),
            ],
            widths,
        )
    if not rows:
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(0, 8, "No candidate matches were recorded for this video.", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    return bytes(pdf.output())


def build_case_report_pdf(case_rows: List[dict], disclaimer: str) -> bytes:
    from fpdf.enums import XPos, YPos

    pdf = _pdf()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "Missing Person Case Report", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 9)
    pdf.multi_cell(0, 5, disclaimer, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)
    headers = ["Case #", "Name", "Status", "Last seen", "Photos", "Created"]
    widths = [30, 38, 26, 26, 14, 34]
    _row(pdf, headers, widths, bold=True)
    for r in case_rows[:500]:
        _row(
            pdf,
            [
                str(r["case_number"]),
                str(r.get("full_name") or "(name unknown)"),
                str(r.get("status", "")),
                str(r.get("last_seen_date") or "-"),
                str(r.get("photo_count", 0)),
                str(r.get("created_at", ""))[:19],
            ],
            widths,
        )
    return bytes(pdf.output())
