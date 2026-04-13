#!/usr/bin/env python3
"""Render synthetic filled marks on the dewarped template and run the scanner."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent
LAYOUT = ROOT / "output" / "sample_answer_sheet_q1_q3_layout.json"
WARP_W = 1200
WARP_H = int(WARP_W * 297 / 210)


def load_layout() -> dict:
    return json.loads(LAYOUT.read_text(encoding="utf-8"))


def blank_warped_bgr() -> np.ndarray:
    """Approximate printed page: off-white background."""
    return np.full((WARP_H, WARP_W, 3), (252, 252, 252), dtype=np.uint8)


def draw_horizontal_mark(img: np.ndarray, rect_norm: list[float], strength: float = 1.0) -> None:
    h, w = img.shape[:2]
    nx0, ny0, nx1, ny1 = rect_norm
    x0, y0 = int(nx0 * w), int(ny0 * h)
    x1, y1 = int(nx1 * w), int(ny1 * h)
    cx0 = int(x0 + (x1 - x0) * 0.18)
    cx1 = int(x1 - (x1 - x0) * 0.18)
    cy = (y0 + y1) // 2
    grey = int(35 * strength + 220 * (1 - strength))
    cv2.line(img, (cx0, cy), (cx1, cy), (grey, grey, grey), thickness=2, lineType=cv2.LINE_AA)


def main() -> None:
    layout = load_layout()
    if not LAYOUT.exists():
        print("Run generate_sample_sheet.py first.", file=sys.stderr)
        sys.exit(1)

    cases = [
        ("clean", {"1": "B", "2": "A", "3": ["B", "D"]}, 1.0),
        ("light_marks", {"1": "B", "2": "A", "3": ["B", "D"]}, 0.55),
        ("ambiguous_q1", {"1": ["B", "C"], "2": "A", "3": ["B", "D"]}, 1.0),
    ]

    out_dir = ROOT / "test_results"
    out_dir.mkdir(parents=True, exist_ok=True)

    summary_lines: list[str] = []

    for name, answers, strength in cases:
        img = blank_warped_bgr()
        for m in layout["marks"]:
            q = str(m["question"])
            opt = str(m["option"]).upper()
            sel = answers.get(q)
            if sel is None:
                continue
            if isinstance(sel, str):
                wanted = {sel.upper()}
            else:
                wanted = {s.upper() for s in sel}
            if opt in wanted:
                draw_horizontal_mark(img, m["rect_norm"], strength=strength)

        img_path = out_dir / f"synthetic_{name}.png"
        cv2.imwrite(str(img_path), img)
        csv_path = out_dir / f"synthetic_{name}.csv"
        cmd = [
            sys.executable,
            str(ROOT / "scan_mark_sheet.py"),
            "--prealigned",
            "--image",
            str(img_path),
            "--layout",
            str(LAYOUT),
            "--key",
            "1:B,2:A,3:BD",
            "--student",
            name,
            "--out",
            str(csv_path),
        ]
        subprocess.check_call(cmd, cwd=str(ROOT))
        summary_lines.append(f"{name}: image={img_path.name} csv={csv_path.name}")

    (out_dir / "synthetic_runs.txt").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    print("Synthetic tests written under test_results/")


if __name__ == "__main__":
    main()
