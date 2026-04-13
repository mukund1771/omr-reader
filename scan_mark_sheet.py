#!/usr/bin/env python3
"""
Scan a filled answer sheet (photo or scan), detect the registration frame, read
horizontal pencil marks in boxed options, and write CSV / optional JSON.

Example:
  python scan_mark_sheet.py \\
    --image path/to/scan.png \\
    --layout output/sample_answer_sheet_q1_q3_layout.json \\
    --key "1:B,2:A,3:BD" \\
    --student "Taylor J." \\
    --out output/result.csv
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from geometry import horizontal_line_score, largest_quad_contour, order_quad_pts, warp_quad_to_rect

WARP_W = 1200
WARP_H = int(WARP_W * 297 / 210)


def load_layout(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_key(s: str) -> dict[int, list[str]]:
    """Format: 1:B,2:A,3:BD (multiple letters for multi-select)."""
    out: dict[int, list[str]] = {}
    if not s.strip():
        return out
    for part in s.split(","):
        part = part.strip()
        if not part or ":" not in part:
            continue
        q, ans = part.split(":", 1)
        out[int(q)] = [ch.upper() for ch in ans.strip().upper()]
    return out


def classify_marks(
    scores: dict[tuple[int, str], float],
    questions: list[dict],
    strong: float,
    weak: float,
) -> tuple[dict[int, list[str]], dict[int, list[str]], dict[int, list[tuple[str, float]]]]:
    """
    Returns (selected, ambiguous_flags, debug_scores_per_q).
    A question is accepted when exactly `hi` options meet the strong threshold and every
    other option sits below the faint threshold (tolerates light smudges / erased boxes).
    """
    selected: dict[int, list[str]] = {}
    ambiguous: dict[int, list[str]] = {}
    debug: dict[int, list[tuple[str, float]]] = {}

    for spec in questions:
        qid = int(spec["id"])
        hi = int(spec.get("max_select", spec.get("min_select", 1)))
        opts = [str(x).upper() for x in spec["options"]]
        rows = [(o, scores.get((qid, o), 0.0)) for o in opts]
        rows.sort(key=lambda t: t[1], reverse=True)
        debug[qid] = rows

        strong_opts = [o for o, s in rows if s >= strong]
        if len(strong_opts) > hi:
            ambiguous[qid] = ["too_many_strong"]
            continue
        if len(strong_opts) < hi:
            ambiguous[qid] = ["too_few_strong"]
            continue
        rest_scores = [s for o, s in rows if o not in strong_opts]
        if rest_scores and max(rest_scores) >= weak:
            ambiguous[qid] = ["competing_faint_or_partial"]
            continue
        selected[qid] = sorted(strong_opts)
    return selected, ambiguous, debug


def score_sheet(
    image_bgr: np.ndarray,
    layout: dict[str, Any],
    strong_t: float,
    weak_t: float,
    prealigned: bool,
) -> tuple[dict[int, list[str]], dict[int, list[str]], dict[int, list[tuple[str, float]]], np.ndarray]:
    if prealigned:
        warped = cv2.resize(image_bgr, (WARP_W, WARP_H), interpolation=cv2.INTER_AREA)
    else:
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        quad = largest_quad_contour(gray)
        if quad is None:
            raise SystemExit(
                "Could not find registration frame. Try a flatter scan with the full page visible, "
                "or export a dewarped patch and pass --prealigned."
            )
        quad = order_quad_pts(quad)
        warped = warp_quad_to_rect(image_bgr, quad, WARP_W, WARP_H)
    g2 = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)

    scores: dict[tuple[int, str], float] = {}
    h, w = g2.shape[:2]
    for m in layout["marks"]:
        q = int(m["question"])
        opt = str(m["option"]).upper()
        nx0, ny0, nx1, ny1 = m["rect_norm"]
        x0, y0, x1, y1 = (
            int(nx0 * w),
            int(ny0 * h),
            int(nx1 * w),
            int(ny1 * h),
        )
        roi = g2[y0:y1, x0:x1]
        ink, _peak = horizontal_line_score(roi)
        scores[(q, opt)] = ink

    selected, ambiguous, dbg = classify_marks(scores, layout["questions"], strong_t, weak_t)
    return selected, ambiguous, dbg, warped


def grade(selected: dict[int, list[str]], key: dict[int, list[str]]) -> tuple[int, list[int]]:
    wrong: list[int] = []
    score = 0
    for q, exp in key.items():
        got = selected.get(q, [])
        exp_s = sorted(exp)
        got_s = sorted(got)
        if exp_s == got_s:
            score += 1
        else:
            wrong.append(q)
    return score, wrong


def main() -> None:
    ap = argparse.ArgumentParser(description="Scan GL-style line-in-box answer sheet (sample).")
    ap.add_argument("--image", required=True, type=Path, help="Scan/photo path (png/jpg/tiff)")
    ap.add_argument("--layout", required=True, type=Path, help="layout.json from generate_sample_sheet.py")
    ap.add_argument("--key", default="", help='Optional answer key, e.g. 1:B,2:A,3:BD')
    ap.add_argument("--student", default="", help="Student name or ID for CSV column")
    ap.add_argument("--out", required=True, type=Path, help="Output CSV path")
    ap.add_argument("--debug-warp", type=Path, default=None, help="If set, save dewarped colour image for QC")
    ap.add_argument("--strong", type=float, default=0.07, help="Ink fraction considered a firm mark")
    ap.add_argument("--weak", type=float, default=0.035, help="Ink fraction considered a faint mark")
    ap.add_argument(
        "--prealigned",
        action="store_true",
        help="Image is already the dewarped registration patch at the template aspect (synthetic tests).",
    )
    args = ap.parse_args()

    layout = load_layout(args.layout)
    image_bgr = cv2.imread(str(args.image), cv2.IMREAD_COLOR)
    if image_bgr is None:
        raise SystemExit(f"Failed to read image: {args.image}")

    selected, ambiguous, dbg, warped = score_sheet(
        image_bgr, layout, args.strong, args.weak, args.prealigned
    )
    if args.debug_warp:
        args.debug_warp.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(args.debug_warp), warped)

    key = parse_key(args.key)
    score, wrong = grade(selected, key) if key else (0, [])

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "student",
                "q1",
                "q2",
                "q3",
                "score",
                "wrong_questions",
                "ambiguous",
                "notes",
            ]
        )
        amb_str = ";".join(f"Q{k}:{','.join(v)}" for k, v in sorted(ambiguous.items()))
        w.writerow(
            [
                args.student,
                "".join(selected.get(1, [])),
                "".join(selected.get(2, [])),
                "".join(selected.get(3, [])),
                score if key else "",
                ",".join(str(x) for x in wrong) if key else "",
                amb_str,
                "",
            ]
        )

    print("Selected:", selected)
    if ambiguous:
        print("Ambiguous:", ambiguous)
    if key:
        print("Score:", score, "Wrong:", wrong)
    print("Wrote", args.out)


if __name__ == "__main__":
    main()
