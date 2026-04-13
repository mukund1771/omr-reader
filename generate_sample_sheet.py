#!/usr/bin/env python3
"""
Generate an original GL-inspired A4 answer sheet (questions 1–3 + example).
Horizontal block layout closely matches UK 11+ OMR style.
Compatible with scan_mark_sheet.py.
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

# ── Colours ──────────────────────────────────────────────────────────────────
FORM_C = colors.Color(0.78, 0.0, 0.46)   # GL-style magenta/pink
BLACK  = colors.black
GREY   = colors.Color(0.12, 0.12, 0.12)  # near-black text

# ── Registration frame (black border scanner locks onto) ──────────────────────
REG_X0, REG_Y0 = 9 * mm, 11 * mm
REG_W,  REG_H  = 192 * mm, 273 * mm   # right=201mm, top=284mm

# ── Question block geometry ───────────────────────────────────────────────────
BLOCK_W    = 44.5 * mm   # width of each question block
BLOCK_GAP  = 3.5  * mm   # gap between blocks
NUM_BLOCKS = 4            # EXAMPLE + Q1 + Q2 + Q3

# Centre the 4 blocks inside the registration frame
BLOCKS_X0 = REG_X0 + (REG_W - (NUM_BLOCKS * BLOCK_W + (NUM_BLOCKS - 1) * BLOCK_GAP)) / 2

HDR_H    = 8.5 * mm   # question-number header strip height
OPT_H    = 7.5 * mm   # height per option row
NUM_OPTS = 5
BLOCK_H  = HDR_H + NUM_OPTS * OPT_H   # ≈ 46 mm

# Option box dimensions (inside each block row)
BOX_X_OFFSET = 16.0 * mm                           # block-left to box-left
BOX_W        = BLOCK_W - BOX_X_OFFSET - 2.0 * mm  # ≈ 26.5 mm
BOX_H        = OPT_H - 2.0 * mm                   # ≈ 5.5 mm

# Top edge of question-block row (PDF bottom-origin)
BLOCKS_TOP_Y = 205 * mm


# ── Helpers ───────────────────────────────────────────────────────────────────

def _norm(x_pdf: float, y_pdf: float) -> tuple[float, float]:
    """Normalised (0–1) coords inside registration frame; origin = top-left."""
    nx = (x_pdf - REG_X0) / REG_W
    ny = 1.0 - (y_pdf - REG_Y0) / REG_H
    return nx, ny


def _timing_marks(c: canvas.Canvas) -> None:
    c.setFillColor(BLACK)
    tw, th = 4.0 * mm, 0.9 * mm
    xs_l, xs_r = 3.5 * mm, 206.5 * mm
    for ym in [28, 48, 68, 88, 108, 128, 148, 168, 188, 208, 228, 248, 268]:
        y = ym * mm
        c.rect(xs_l, y, tw, th, stroke=0, fill=1)
        c.rect(xs_r - tw, y, tw, th, stroke=0, fill=1)


def _qr(c: canvas.Canvas, x: float, y: float, size: float) -> None:
    qr = QrCodeWidget(value="MOCK11+ SAMPLE Q1-3", barWidth=0.55 * mm, barHeight=0.55 * mm)
    b  = qr.getBounds()
    bw, bh = b[2] - b[0], b[3] - b[1]
    d = Drawing(size, size, transform=[size / bw, 0, 0, size / bh,
                                        -b[0] * size / bw, -b[1] * size / bh])
    d.add(qr)
    renderPDF.draw(d, c, x, y)


def _barcode(c: canvas.Canvas, x: float, y: float, val: str, w: float, h: float) -> None:
    bc = BarcodeCode128(value=val, humanReadable=1,
                        barWidth=0.22 * mm, barHeight=7 * mm, fontSize=6)
    b  = bc.getBounds()
    bw, bh = max(b[2] - b[0], 0.1), max(b[3] - b[1], 0.1)
    d = Drawing(w, h, transform=[w / bw, 0, 0, h / bh,
                                   -b[0] * w / bw, -b[1] * h / bh])
    d.add(bc)
    renderPDF.draw(d, c, x, y)


def _question_block(
    c: canvas.Canvas,
    bx: float,
    btop: float,
    q_index: int,
    opt_labels: list[str],
    dual: bool = False,
) -> list[dict]:
    """
    Draw one question block.
    bx = left edge, btop = top edge (PDF bottom-origin, in pt).
    Returns mark metadata for layout.json.
    """
    marks: list[dict] = []

    # Outer block border
    c.setStrokeColor(FORM_C)
    c.setLineWidth(0.85)
    c.rect(bx, btop - BLOCK_H, BLOCK_W, BLOCK_H, stroke=1, fill=0)

    # Divider below header
    c.setLineWidth(0.55)
    c.line(bx, btop - HDR_H, bx + BLOCK_W, btop - HDR_H)

    # Question number / label
    q_lbl = "EXAMPLE" if q_index == 0 else str(q_index)
    if dual:
        q_lbl += " \u2605"          # ★  (two-mark indicator)
    c.setFont("Helvetica-Bold", 7.5 if q_index == 0 else 11)
    c.setFillColor(GREY)
    c.drawString(bx + 2 * mm, btop - HDR_H + 2.2 * mm, q_lbl)

    # Option rows
    c.setFont("Helvetica", 9)
    for i, lbl in enumerate(opt_labels):
        row_bot = btop - HDR_H - (i + 1) * OPT_H
        row_mid = row_bot + OPT_H * 0.45

        # Label text
        c.setFillColor(GREY)
        c.drawString(bx + 2.5 * mm, row_mid - 3.0, lbl)

        # Mark rectangle
        box_x = bx + BOX_X_OFFSET
        box_y = row_bot + (OPT_H - BOX_H) / 2
        c.setStrokeColor(FORM_C)
        c.setLineWidth(0.7)
        c.rect(box_x, box_y, BOX_W, BOX_H, stroke=1, fill=0)

        # Normalised coords for scanner
        nx0, ny_t = _norm(box_x, box_y + BOX_H)
        nx1, ny_b = _norm(box_x + BOX_W, box_y)
        marks.append({
            "question": q_index,
            "option":   lbl,
            "rect_norm": [
                min(nx0, nx1), min(ny_t, ny_b),
                max(nx0, nx1), max(ny_t, ny_b),
            ],
        })
    return marks


def _example_mark(c: canvas.Canvas, mark: dict) -> None:
    """Draw a pre-filled horizontal pencil line inside the given mark box."""
    nx0, ny0, nx1, ny1 = mark["rect_norm"]
    x0  = REG_X0 + nx0 * REG_W
    x1  = REG_X0 + nx1 * REG_W
    y_t = REG_Y0 + (1.0 - ny0) * REG_H
    y_b = REG_Y0 + (1.0 - ny1) * REG_H
    cy  = (y_t + y_b) / 2
    c.setStrokeColor(BLACK)
    c.setLineWidth(1.4)
    c.line(x0 + 2.5 * mm, cy, x1 - 2.5 * mm, cy)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    out_dir = Path(__file__).resolve().parent / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf_path    = out_dir / "sample_answer_sheet_q1_q3.pdf"
    layout_path = out_dir / "sample_answer_sheet_q1_q3_layout.json"

    W, H = A4   # 595.28 pt × 841.89 pt
    c = canvas.Canvas(str(pdf_path), pagesize=A4)

    # White background
    c.setFillColor(colors.white)
    c.rect(0, 0, W, H, stroke=0, fill=1)

    _timing_marks(c)

    # ── Registration frame ────────────────────────────────────────────────
    c.setStrokeColor(BLACK)
    c.setLineWidth(2.6)
    c.rect(REG_X0, REG_Y0, REG_W, REG_H, stroke=1, fill=0)

    # ── Title ─────────────────────────────────────────────────────────────
    c.setFont("Helvetica-Bold", 11.5)
    c.setFillColor(FORM_C)
    c.drawString(12 * mm, 280 * mm, "PRACTICE ANSWER SHEET \u2014 VERBAL REASONING 1")
    c.setFont("Helvetica-Oblique", 7.5)
    c.setFillColor(GREY)
    c.drawString(12 * mm, 275.5 * mm,
                 "Original design for in-centre mock exams. "
                 "Not affiliated with GL Assessment or any awarding body.")
    c.setStrokeColor(FORM_C)
    c.setLineWidth(1.0)
    c.line(12 * mm, 274 * mm, 198 * mm, 274 * mm)

    # ── QR code (top-right, clear of all text) ───────────────────────────
    # Placed at top-right corner: x=178–196mm, y=263–281mm
    _qr(c, 178 * mm, 263 * mm, 18 * mm)

    # ── Pupil / School fields ─────────────────────────────────────────────
    c.setFont("Helvetica", 7.5)
    c.setFillColor(GREY)
    c.setStrokeColor(FORM_C)
    c.setLineWidth(0.7)

    # Pupil Name box (spans most of header width)
    c.drawString(12 * mm, 271.5 * mm, "Pupil's Name")
    c.rect(12 * mm, 262.5 * mm, 120 * mm, 8 * mm, stroke=1, fill=0)

    # School Name box (right of pupil name, left of QR)
    c.drawString(136 * mm, 271.5 * mm, "School Name")
    c.rect(136 * mm, 262.5 * mm, 38 * mm, 8 * mm, stroke=1, fill=0)

    # Unique Pupil Number — 12 individual digit boxes
    c.drawString(12 * mm, 259.5 * mm, "UNIQUE PUPIL NUMBER")
    for k in range(12):
        c.rect(12 * mm + k * 7.0 * mm, 252 * mm, 6.2 * mm, 6.5 * mm, stroke=1, fill=0)

    # School Number — 6 digit boxes (right column)
    c.drawString(100 * mm, 259.5 * mm, "SCHOOL NUMBER")
    for k in range(6):
        c.rect(130 * mm + k * 7.0 * mm, 252 * mm, 6.2 * mm, 6.5 * mm, stroke=1, fill=0)

    # Date of test  DD / MM / YYYY (below UPN row)
    c.drawString(12 * mm, 248.5 * mm, "DATE OF TEST")
    field_x = 45 * mm
    for lbl, cnt in [("DAY", 2), ("MONTH", 2), ("YEAR", 4)]:
        c.drawString(field_x, 248.5 * mm, lbl)
        for j in range(cnt):
            c.rect(field_x + j * 7.0 * mm, 241 * mm, 6.2 * mm, 6.5 * mm, stroke=1, fill=0)
        field_x += cnt * 7.0 * mm + 9 * mm

    # Second DATE OF TEST block (right side — mirrors GL layout)
    c.drawString(134 * mm, 248.5 * mm, "DATE OF TEST")
    c.drawString(163 * mm, 248.5 * mm, "DAY")
    c.drawString(176 * mm, 248.5 * mm, "MONTH")
    c.drawString(191 * mm, 248.5 * mm, "YEAR")
    for k in range(2):
        c.rect(163 * mm + k * 6.7 * mm, 241 * mm, 6.0 * mm, 6.5 * mm, stroke=1, fill=0)
    for k in range(2):
        c.rect(177 * mm + k * 6.7 * mm, 241 * mm, 6.0 * mm, 6.5 * mm, stroke=1, fill=0)
    for k in range(4):
        c.rect(190 * mm + k * 4.2 * mm, 241 * mm, 3.8 * mm, 6.5 * mm, stroke=1, fill=0)

    # ── Instructions ──────────────────────────────────────────────────────
    c.setFont("Helvetica-Bold", 10.5)
    c.setFillColor(GREY)
    c.drawString(12 * mm, 233 * mm, "Please mark boxes with a thin horizontal line")
    c.setFont("Helvetica", 8.5)
    c.drawString(12 * mm, 227 * mm,
                 "Use a sharp HB or B pencil.  Mark ONE box per question "
                 "(TWO boxes for Question 3\u2605).  Rub out errors completely.")

    # ── Question blocks ───────────────────────────────────────────────────
    opt_labels  = ["A", "B", "C", "D", "E"]
    block_specs = [
        (0, opt_labels, False),   # EXAMPLE
        (1, opt_labels, False),   # Question 1
        (2, opt_labels, False),   # Question 2
        (3, opt_labels, True),    # Question 3 (dual-mark)
    ]

    all_marks: list[dict] = []
    for idx, (qnum, opts, dual) in enumerate(block_specs):
        bx = BLOCKS_X0 + idx * (BLOCK_W + BLOCK_GAP)
        all_marks += _question_block(c, bx, BLOCKS_TOP_Y, qnum, opts, dual)

    # Pre-fill example mark in option "B" (shows pupils how to mark)
    for m in all_marks:
        if m["question"] == 0 and m["option"] == "B":
            _example_mark(c, m)
            break

    # Note below blocks
    c.setFont("Helvetica-Oblique", 7.5)
    c.setFillColor(GREY)
    c.drawString(BLOCKS_X0, BLOCKS_TOP_Y - BLOCK_H - 5 * mm,
                 "\u2605 Question 3: mark exactly TWO answers.     "
                 "EXAMPLE block is shown for reference — it is not scored.")

    # ── Barcode + "PLEASE TURN OVER" ─────────────────────────────────────
    _barcode(c, 12 * mm, 13 * mm, "MOCK11-SAMPLE-Q3", 72 * mm, 12 * mm)
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(FORM_C)
    c.drawCentredString(105 * mm, 16.5 * mm, "PLEASE TURN OVER")

    c.showPage()
    c.save()

    # ── Layout JSON for scanner ───────────────────────────────────────────
    layout = {
        "version": 1,
        "title": "sample_answer_sheet_q1_q3",
        "page_size_pt": list(A4),
        "registration": {
            "quad_pdf_mm_bl_origin": [
                [REG_X0 / mm, REG_Y0 / mm],
                [(REG_X0 + REG_W) / mm, REG_Y0 / mm],
                [(REG_X0 + REG_W) / mm, (REG_Y0 + REG_H) / mm],
                [REG_X0 / mm, (REG_Y0 + REG_H) / mm],
            ],
            "note": "Quad order BL, BR, TR, TL in PDF mm (bottom-left origin).",
        },
        "questions": [
            {"id": 1, "min_select": 1, "max_select": 1, "options": ["A", "B", "C", "D", "E"]},
            {"id": 2, "min_select": 1, "max_select": 1, "options": ["A", "B", "C", "D", "E"]},
            {"id": 3, "min_select": 2, "max_select": 2, "options": ["A", "B", "C", "D", "E"]},
        ],
        "marks":         [m for m in all_marks if m["question"] != 0],
        "example_marks": [m for m in all_marks if m["question"] == 0],
    }
    layout_path.write_text(json.dumps(layout, indent=2), encoding="utf-8")
    print(f"PDF  \u2192 {pdf_path}")
    print(f"JSON \u2192 {layout_path}")


if __name__ == "__main__":
    main()
