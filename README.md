## Setup

```bash
cd omr-reader
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python generate_sample_sheet.py
```

## workflow

1. Print `sample.pdf` on plain A4 (colour or greyscale is fine; magenta rules are optional visually).
2. Candidates mark with **HB/B pencil**: one neat **horizontal line** in the box (question 3 asks for **two** lines in two boxes).
3. Scan or photograph the full page (whole black registration frame visible).
4. Run:

```bash
python scan_mark_sheet.py \
  --image path/to/scan.png \
  --layout output/sample_answer_sheet_q1_q3_layout.json \
  --key "1:B,2:A,3:BD" \
  --student "Pupil Name" \
  --out output/result.csv \
  --debug-warp output/debug_dewarp.png
```

- Omit `--key` if you only want detected answers, not a score.
- If the page cannot be found automatically, dewarp/crop to the **inner black frame** and use `--prealigned` (same aspect as the tool’s internal 1200×… template); see `synthetic_scan_test.py`.

## Synthetic tests

```bash
python synthetic_scan_test.py
```

Produces marked PNGs and CSVs under `test_results/` (clean marks, light marks, deliberate ambiguity on Q1).

## Not in this sample repo

- Short **video** demo: record screen (e.g. Loom) showing print → fill → scan → CSV.
- Full multi-page templates, A–D–N layouts, staff GUI, and **Excel** export are natural next steps after client sign-off.

## Tuning

Ink thresholds default to `--strong 0.07` and `--weak 0.035` (fraction of dark pixels in the pencil band). Adjust if your scanner prints lighter or darker.
