#!/usr/bin/env python3
"""
Render synthetic filled marks on a blank template and run the scanner.
Produces annotated debug images showing detected marks for each test case.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT    = Path(__file__).resolve().parent
LAYOUT  = ROOT / "output" / "sample_answer_sheet_q1_q3_layout.json"
WARP_W  = 1200
WARP_H  = int(WARP_W * 297 / 210)


def load_layout() -> dict:
    return json.loads(LAYOUT.read_text(encoding="utf-8"))


def blank_page() -> np.ndarray:
    """Off-white background simulating printed paper."""
    return np.full((WARP_H, WARP_W, 3), (250, 250, 250), dtype=np.uint8)


def draw_mark(img: np.ndarray, rect_norm: list[float], strength: float = 1.0) -> None:
    """Draw a thin horizontal pencil-line mark inside the given normalised box."""
    h, w = img.shape[:2]
    nx0, ny0, nx1, ny1 = rect_norm
    x0, y0 = int(nx0 * w), int(ny0 * h)
    x1, y1 = int(nx1 * w), int(ny1 * h)
    # Inset horizontally ~18% each side to avoid touching box border
    cx0 = int(x0 + (x1 - x0) * 0.18)
    cx1 = int(x1 - (x1 - x0) * 0.18)
    cy  = (y0 + y1) // 2
    # Pencil grey: darker = stronger mark
    grey = int(35 * strength + 220 * (1.0 - strength))
    cv2.line(img, (cx0, cy), (cx1, cy), (grey, grey, grey), thickness=2, lineType=cv2.LINE_AA)


def annotate_result(img: np.ndarray, layout: dict, selected: dict, ambiguous: dict) -> np.ndarray:
    """
    Draw coloured overlays on the warped image:
      green  = correctly detected mark
      orange = ambiguous / flagged
      red    = no mark (empty option, shown faintly for reference)
    """
    out = img.copy()
    h, w = out.shape[:2]

    for m in layout["marks"]:
        q   = int(m["question"])
        opt = str(m["option"]).upper()
        nx0, ny0, nx1, ny1 = m["rect_norm"]
        x0, y0 = int(nx0 * w), int(ny0 * h)
        x1, y1 = int(nx1 * w), int(ny1 * h)

        sel_opts = [o.upper() for o in selected.get(q, [])]
        is_amb   = q in ambiguous

        if is_amb:
            colour = (0, 165, 255)    # orange
            thick  = 2
        elif opt in sel_opts:
            colour = (0, 200, 60)     # green
            thick  = 2
        else:
            colour = (180, 180, 180)  # light grey — not selected
            thick  = 1

        cv2.rectangle(out, (x0, y0), (x1, y1), colour, thick)

    return out


def run_case(
    name: str,
    answers: dict,
    strength: float,
    layout: dict,
    out_dir: Path,
) -> None:
    # Draw synthetic marks on blank page
    img = blank_page()
    for m in layout["marks"]:
        q   = str(m["question"])
        opt = str(m["option"]).upper()
        sel = answers.get(q)
        if sel is None:
            continue
        wanted = {sel.upper()} if isinstance(sel, str) else {s.upper() for s in sel}
        if opt in wanted:
            draw_mark(img, m["rect_norm"], strength=strength)

    img_path = out_dir / f"synthetic_{name}.png"
    cv2.imwrite(str(img_path), img)

    # Run scanner
    csv_path  = out_dir / f"synthetic_{name}.csv"
    warp_path = out_dir / f"synthetic_{name}_warp.png"
    cmd = [
        sys.executable, str(ROOT / "scan_mark_sheet.py"),
        "--prealigned",
        "--image",  str(img_path),
        "--layout", str(LAYOUT),
        "--key",    "1:B,2:A,3:BD",
        "--student", name,
        "--out",    str(csv_path),
        "--debug-warp", str(warp_path),
    ]
    result = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    print(result.stdout.strip())
    if result.returncode != 0:
        print(result.stderr.strip(), file=sys.stderr)

    # Parse selected / ambiguous from scanner output for annotation
    # Re-run score_sheet directly for annotation
    import cv2 as _cv2
    from scan_mark_sheet import score_sheet, load_layout as _load_layout
    _layout  = _load_layout(LAYOUT)
    img_bgr  = _cv2.imread(str(img_path), _cv2.IMREAD_COLOR)
    selected, ambiguous, _dbg, warped = score_sheet(img_bgr, _layout, 0.07, 0.035, prealigned=True)

    annotated = annotate_result(warped, _layout, selected, ambiguous)
    ann_path  = out_dir / f"synthetic_{name}_annotated.png"
    _cv2.imwrite(str(ann_path), annotated)
    print(f"  annotated → {ann_path.name}")


def main() -> None:
    if not LAYOUT.exists():
        print("Run generate_sample_sheet.py first.", file=sys.stderr)
        sys.exit(1)

    layout  = load_layout()
    out_dir = ROOT / "test_results"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Test cases: (name, answers, mark_strength)
    cases = [
        # Clean, full-strength marks — should score 3/3
        ("clean",         {"1": "B",       "2": "A",  "3": ["B", "D"]}, 1.0),
        # Light marks (strength 0.55) — tolerance test, should still score 3/3
        ("light_marks",   {"1": "B",       "2": "A",  "3": ["B", "D"]}, 0.55),
        # Two marks on Q1 — should be flagged as ambiguous
        ("ambiguous_q1",  {"1": ["B", "C"],"2": "A",  "3": ["B", "D"]}, 1.0),
    ]

    summary: list[str] = []
    for name, answers, strength in cases:
        print(f"\n── Case: {name} (strength={strength}) ──")
        run_case(name, answers, strength, layout, out_dir)
        summary.append(f"{name}: strength={strength}  answers={answers}")

    summary_path = out_dir / "synthetic_runs.txt"
    summary_path.write_text("\n".join(summary) + "\n", encoding="utf-8")
    print(f"\nAll results written to  {out_dir}/")


if __name__ == "__main__":
    main()
