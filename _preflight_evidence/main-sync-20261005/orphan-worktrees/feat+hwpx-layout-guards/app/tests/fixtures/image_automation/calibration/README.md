# Calibration fixtures (NOT hold-out)

Threshold tuning and edge-case samples live here only.

- Hold-out gates (`../holdout/`) must **never** be used to retune
  `AUTO_THRESHOLD` / `REVIEW_THRESHOLD` / `MARGIN_MIN`.
- Calibration cases may be small and intentionally ambiguous.
- Acceptance gates (macro F1 ≥ 0.90, matching top-1 ≥ 0.90 with
  review-on-low-margin) are scored exclusively against `holdout/`.

Documented match thresholds (see `image_library_matcher.py`):

| Constant | Value | Meaning |
|---|---:|---|
| `AUTO_THRESHOLD` | 0.78 | auto-insert band lower bound |
| `REVIEW_THRESHOLD` | 0.60 | review band lower bound |
| `MARGIN_MIN` | 0.08 | 1st−2nd score margin; else `review` |
