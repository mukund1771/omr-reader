#!/usr/bin/env python3
"""
Generate an original A4 answer sheet (questions 1–3) inspired by UK 11+ line-in-box
layouts, with a machine-readable layout.json for the scanner.
"""

from __future__ import annotations

import json
from pathlib import Path

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.widgets import BarcodeCode128
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

# Original styling: magenta/pink form ink (common on commercial OMR), black anchors.
FORM_MAGENTA = colors.Color(0.78, 0.0, 0.46)
ANCHOR_BLACK = colors.black
TEXT_GREY = colors.Color(0.15, 0.15, 0.15)

# Registration frame (black) — scanner locks to this quadrilateral.
REG_X0 = 9 * mm
REG_Y0 = 11 * mm  # bottom edge of frame (PDF coords)
REG_W = 192 * mm
REG_H = 273 * mm


def pdf_to_norm(x_pdf: float, y_pdf: float) -> tuple[float, float]:
    """Top-left normalised coordinates inside registration frame."""
    nx = (x_pdf - REG_X0) / REG_W
    ny = 1.0 - (y_pdf - REG_Y0) / REG_H
    return nx, ny


def draw_timing_marks(c: canvas.Canvas) -> None:
    """Thin black timing segments along side margins (alignment aid, not proprietary)."""
    c.setStrokeColor(ANCHOR_BLACK)
    c.setFillColor(ANCHOR_BLACK)
    c.setLineWidth(0.6)
    xs_left = 3.5 * mm
    xs_right = 206.5 * mm
    tick_w = 4.0 * mm
    tick_h = 0.9 * mm
    # a few ticks spanning header + question block
    y_positions = [35, 55, 75, 95, 115, 135, 155, 175, 195, 215, 235, 255]
    for y_mm in y_positions:
        y = y_mm * mm
        c.rect(xs_left, y, tick_w, tick_h, stroke=0, fill=1)
        c.rect(xs_right - tick_w, y, tick_w, tick_h, stroke=0, fill=1)


def draw_q_block_boxes(
    c: canvas.Canvas,
    q_index: int,
    top_y_mm: float,
    row_h_mm: float,
    opt_labels: list[str],
) -> list[dict]:
    """
    One question: labels in left column, answer boxes on the right (GL-style).
    Returns mark metadata for layout.json.
    """
    marks: list[dict] = []
    left_x = 22 * mm
    label_col_w = 16 * mm
    gap = 4 * mm
    box_w = 22 * mm
    box_h = 6.5 * mm
    box_x0 = left_x + label_col_w + gap

    q_top_pdf = top_y_mm * mm
    block_h = row_h_mm * mm * len(opt_labels)

    c.setStrokeColor(FORM_MAGENTA)
    c.setLineWidth(0.9)
    # outer question frame
    c.rect(left_x - 4 * mm, q_top_pdf - block_h - 5 * mm, 170 * mm, block_h + 9 * mm)

    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(TEXT_GREY)
    label = "Example" if q_index == 0 else str(q_index)
    c.drawString(left_x, q_top_pdf - 4 * mm, label)

    c.setFont("Helvetica", 9.5)
    row_pdf_h = row_h_mm * mm
    for i, lab in enumerate(opt_labels):
        y_top = q_top_pdf - (i + 1) * row_pdf_h
        y_mid = y_top + row_pdf_h * 0.35
        c.setFillColor(TEXT_GREY)
        c.drawString(left_x + 1 * mm, y_mid, lab)
        # answer rectangle (magenta border, white interior)
        c.setStrokeColor(FORM_MAGENTA)
        c.setLineWidth(0.7)
        c.rect(box_x0, y_top + 0.7 * mm, box_w, box_h)

        y_pdf_bot = y_top + 0.7 * mm
        y_pdf_top = y_top + 0.7 * mm + box_h
        nx0, ny_top = pdf_to_norm(box_x0, y_pdf_top)
        nx1, ny_bot = pdf_to_norm(box_x0 + box_w, y_pdf_bot)
        marks.append(
            {
                "question": q_index,
                "option": lab,
                "rect_norm": [min(nx0, nx1), min(ny_top, ny_bot), max(nx0, nx1), max(ny_top, ny_bot)],
            }
        )
    return marks


def attach_qr(c: canvas.Canvas, x: float, y: float, size: float) -> None:
    qr = QrCodeWidget(
        value="MOCK11 SAMPLE SHEET Q1-3",
        barWidth=0.55 * mm,
        barHeight=0.55 * mm,
    )
    b = qr.getBounds()
    bw, bh = b[2] - b[0], b[3] - b[1]
    d = Drawing(size, size, transform=[size / bw, 0, 0, size / bh, -b[0] * size / bw, -b[1] * size / bh])
    d.add(qr)
    renderPDF.draw(d, c, x, y)


def attach_code128(c: canvas.Canvas, x: float, y: float, value: str, w: float, h: float) -> None:
    bc = BarcodeCode128(
        value=value,
        humanReadable=1,
        barWidth=0.22 * mm,
        barHeight=7 * mm,
        fontSize=6,
    )
    b = bc.getBounds()
    bw, bh = max(b[2] - b[0], 0.1), max(b[3] - b[1], 0.1)
    d = Drawing(w, h, transform=[w / bw, 0, 0, h / bh, -b[0] * w / bw, -b[1] * h / bh])
    d.add(bc)
    renderPDF.draw(d, c, x, y)


def main() -> None:
    out_dir = Path(__file__).resolve().parent / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = out_dir / "sample_answer_sheet_q1_q3.pdf"
    layout_path = out_dir / "sample_answer_sheet_q1_q3_layout.json"

    w_pt, h_pt = A4
    c = canvas.Canvas(str(pdf_path), pagesize=A4)

    # Page tint: white
    c.setFillColor(colors.white)
    c.rect(0, 0, w_pt, h_pt, stroke=0, fill=1)

    draw_timing_marks(c)

    # Registration quadrilateral (BLACK) — must be high-contrast for contour detection.
    c.setStrokeColor(ANCHOR_BLACK)
    c.setLineWidth(2.6)
    c.rect(REG_X0, REG_Y0, REG_W, REG_H, stroke=1, fill=0)

    # Title band
    c.setStrokeColor(FORM_MAGENTA)
    c.setLineWidth(1.0)
    c.line(12 * mm, 278 * mm, 198 * mm, 278 * mm)
    c.setFont("Helvetica-Bold", 13)
    c.setFillColor(TEXT_GREY)
    c.drawString(12 * mm, 281 * mm, "Practice answer sheet — verbal reasoning (sample: questions 1–3)")
    c.setFont("Helvetica-Oblique", 8.5)
    c.drawString(12 * mm, 273 * mm, "Original mock layout for in-centre use. Not affiliated with any awarding body.")

    attach_qr(c, 12 * mm, 232 * mm, 26 * mm)

    # Pupil / school strip (magenta ruled)
    c.setStrokeColor(FORM_MAGENTA)
    c.setLineWidth(0.7)
    y0 = 250 * mm
    c.rect(12 * mm, y0 - 18 * mm, 120 * mm, 8 * mm)
    c.rect(134 * mm, y0 - 18 * mm, 64 * mm, 8 * mm)
    c.setFont("Helvetica", 8.5)
    c.setFillColor(TEXT_GREY)
    c.drawString(13 * mm, y0 - 8.5 * mm, "Pupil surname and forename (print)")
    c.drawString(135 * mm, y0 - 8.5 * mm, "Centre / class code")

    # Date boxes DD MM YYYY
    c.drawString(12 * mm, y0 - 28 * mm, "Date of test (DD / MM / YYYY)")
    bx = 62 * mm
    for label, count in [("DD", 2), ("MM", 2), ("YY", 2)]:
        c.drawString(bx, y0 - 28 * mm, label)
        for j in range(count):
            c.rect(bx + 14 * mm + j * 7.5 * mm, y0 - 30 * mm, 6.5 * mm, 7 * mm)
        bx += 14 * mm + count * 7.5 * mm + 10 * mm

    # Instructions + example
    c.setFont("Helvetica-Bold", 9.5)
    c.drawString(12 * mm, 205 * mm, "How to mark your answers")
    c.setFont("Helvetica", 9)
    instr = (
        "Use a sharp HB or B pencil. For each question draw a single neat horizontal line inside ONE box only, "
        "unless the question tells you to mark TWO answers. Rub out errors fully. Do not fold or crease this sheet."
    )
    text_obj = c.beginText(12 * mm, 198 * mm)
    text_obj.textLine(instr[:95])
    text_obj.textLine(instr[95:])
    c.drawText(text_obj)

    c.setFont("Helvetica-Oblique", 8.5)
    c.drawString(12 * mm, 184 * mm, "Example (correct style of mark):")
    ex_labels = ["m", "f", "a", "l", "d"]
    ex_marks = draw_q_block_boxes(c, 0, 182, 7.2, ex_labels)
    # draw a synthetic horizontal mark in option "a" (third row) for illustration only
    for m in ex_marks:
        if m["option"] != "a":
            continue
        nx0, ny0, nx1, ny1 = m["rect_norm"]
        x0 = REG_X0 + nx0 * REG_W
        x1 = REG_X0 + nx1 * REG_W
        y_pdf_top = REG_Y0 + (1.0 - ny0) * REG_H
        y_pdf_bot = REG_Y0 + (1.0 - ny1) * REG_H
        cy = (y_pdf_top + y_pdf_bot) / 2
        c.setStrokeColor(ANCHOR_BLACK)
        c.setLineWidth(1.1)
        c.line(x0 + 2.5 * mm, cy, x1 - 2.5 * mm, cy)
    c.setFont("Helvetica", 8)
    c.setFillColor(TEXT_GREY)
    c.drawString(12 * mm, 148 * mm, "Example row is not scored.")

    # Questions 1–3 (A–E); question 3 requires two answers for demo of dual-mark logic.
    all_marks: list[dict] = []
    all_marks += draw_q_block_boxes(c, 1, 136, 7.2, ["A", "B", "C", "D", "E"])
    all_marks += draw_q_block_boxes(c, 2, 96, 7.2, ["A", "B", "C", "D", "E"])
    all_marks += draw_q_block_boxes(c, 3, 56, 7.2, ["A", "B", "C", "D", "E"])
    c.setFont("Helvetica-Bold", 9)
    c.drawString(38 * mm, 64 * mm, "Question 3: mark TWO answers")

    attach_code128(c, 12 * mm, 10 * mm, "MOCK11-SAMPLE-Q3", 72 * mm, 12 * mm)
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(FORM_MAGENTA)
    c.drawCentredString(105 * mm, 16 * mm, "PLEASE TURN OVER")

    c.showPage()
    c.save()

    layout = {
        "version": 1,
        "title": "sample_answer_sheet_q1_q3",
        "page_size_pt": [w_pt, h_pt],
        "registration": {
            "quad_pdf_mm_bl_origin": [
                [REG_X0 / mm, REG_Y0 / mm],
                [(REG_X0 + REG_W) / mm, REG_Y0 / mm],
                [(REG_X0 + REG_W) / mm, (REG_Y0 + REG_H) / mm],
                [REG_X0 / mm, (REG_Y0 + REG_H) / mm],
            ],
            "note": "Quad order is BL, BR, TR, TL in PDF mm with origin bottom-left.",
        },
        "questions": [
            {"id": 1, "min_select": 1, "max_select": 1, "options": ["A", "B", "C", "D", "E"]},
            {"id": 2, "min_select": 1, "max_select": 1, "options": ["A", "B", "C", "D", "E"]},
            {"id": 3, "min_select": 2, "max_select": 2, "options": ["A", "B", "C", "D", "E"]},
        ],
        "marks": [m for m in all_marks if m["question"] != 0],
        "example_marks": [m for m in all_marks if m["question"] == 0],
    }
    layout_path.write_text(json.dumps(layout, indent=2), encoding="utf-8")
    print(f"Wrote {pdf_path}")
    print(f"Wrote {layout_path}")


if __name__ == "__main__":
    main()
