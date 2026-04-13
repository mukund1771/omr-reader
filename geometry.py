"""Shared helpers for sheet registration and ROI geometry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import cv2
import numpy as np


def order_quad_pts(pts: np.ndarray) -> np.ndarray:
    """Order 4 points as TL, TR, BR, BL (for perspective warp to upright rect)."""
    pts = np.asarray(pts, dtype=np.float32).reshape(-1, 2)
    if pts.shape[0] != 4:
        raise ValueError("Need exactly 4 points")
    s = pts.sum(axis=1)
    diff = np.diff(pts, axis=1).ravel()
    tl = pts[np.argmin(s)]
    br = pts[np.argmax(s)]
    tr = pts[np.argmin(diff)]
    bl = pts[np.argmax(diff)]
    return np.array([tl, tr, br, bl], dtype=np.float32)


def warp_quad_to_rect(
    image_bgr: np.ndarray, quad_pts: np.ndarray, out_w: int, out_h: int
) -> np.ndarray:
    dst = np.array(
        [[0, 0], [out_w - 1, 0], [out_w - 1, out_h - 1], [0, out_h - 1]],
        dtype=np.float32,
    )
    m = cv2.getPerspectiveTransform(quad_pts.astype(np.float32), dst)
    return cv2.warpPerspective(image_bgr, m, (out_w, out_h))


def largest_quad_contour(
    gray: np.ndarray,
    min_area_ratio: float = 0.15,
    max_area_ratio: float = 0.98,
) -> np.ndarray | None:
    """Find the largest roughly quadrilateral contour (outer registration frame)."""
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    th = cv2.Canny(blur, 40, 160)
    th = cv2.dilate(th, np.ones((3, 3), np.uint8), iterations=1)
    cnts, _ = cv2.findContours(th, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    h, w = gray.shape[:2]
    img_area = float(h * w)
    best = None
    best_area = 0.0
    for c in cnts:
        area = cv2.contourArea(c)
        if area < min_area_ratio * img_area or area > max_area_ratio * img_area:
            continue
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        if len(approx) != 4:
            continue
        if area > best_area:
            best_area = area
            best = approx.reshape(4, 2)
    return best


@dataclass(frozen=True)
class NormRect:
    """Rectangle in normalized coordinates (0–1), origin top-left of registration quad."""

    x0: float
    y0: float
    x1: float
    y1: float

    def to_pixels(self, w: int, h: int, inset: float = 0.02) -> tuple[int, int, int, int]:
        bw = self.x1 - self.x0
        bh = self.y1 - self.y0
        ix = bw * inset
        iy = bh * inset
        x0 = int(round((self.x0 + ix) * w))
        y0 = int(round((self.y0 + iy) * h))
        x1 = int(round((self.x1 - ix) * w))
        y1 = int(round((self.y1 - iy) * h))
        return x0, y0, x1, y1


def horizontal_line_score(gray_roi: np.ndarray) -> tuple[float, float]:
    """
    Score how much a thin horizontal stroke is present in the ROI.
    Returns (band_ink_fraction, row_projection_peak) for debugging.
    """
    if gray_roi.size == 0:
        return 0.0, 0.0
    g = cv2.GaussianBlur(gray_roi, (3, 3), 0)
    _, bw = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    h, w = bw.shape
    if h < 6 or w < 6:
        return 0.0, 0.0
    # central horizontal band — where pupils are instructed to draw the line
    y0, y1 = int(h * 0.30), int(h * 0.70)
    band = bw[y0:y1, :]
    ink = float(np.mean(band > 0))
    # horizontal closing emphasises strokes vs speckle
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (max(7, w // 6), 1))
    closed = cv2.morphologyEx(band, cv2.MORPH_CLOSE, k)
    ink_closed = float(np.mean(closed > 0))
    proj = np.mean(closed > 0, axis=1)
    peak = float(np.max(proj)) if proj.size else 0.0
    return max(ink, ink_closed), peak
