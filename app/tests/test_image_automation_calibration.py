"""Hold-out vs calibration separation + gate contracts.

Hold-out (40 each, 10/PSST) is the only acceptance set.
Calibration fixtures document thresholds and must not share IDs with hold-out.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from auto_write.image_automation.image_library_matcher import (
    AUTO_THRESHOLD,
    MARGIN_MIN,
    REVIEW_THRESHOLD,
)
from auto_write.image_automation.models import PsstClass

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "image_automation"
HOLDOUT = FIXTURES / "holdout"
CALIBRATION = FIXTURES / "calibration"
PSST_FOUR = [
    PsstClass.PROBLEM.value,
    PsstClass.SOLUTION.value,
    PsstClass.SCALE_UP.value,
    PsstClass.TEAM.value,
]


def test_holdout_and_calibration_dirs_are_separate():
    assert HOLDOUT.is_dir()
    assert CALIBRATION.is_dir()
    assert HOLDOUT.resolve() != CALIBRATION.resolve()
    assert (HOLDOUT / "classification_labels.json").is_file()
    assert (HOLDOUT / "matching_labels.json").is_file()
    assert (CALIBRATION / "match_thresholds.json").is_file()
    assert (CALIBRATION / "classification_samples.json").is_file()


def test_calibration_thresholds_match_code_constants():
    data = json.loads((CALIBRATION / "match_thresholds.json").read_text(encoding="utf-8"))
    th = data["thresholds"]
    assert th["AUTO_THRESHOLD"] == AUTO_THRESHOLD == 0.78
    assert th["REVIEW_THRESHOLD"] == REVIEW_THRESHOLD == 0.60
    assert th["MARGIN_MIN"] == MARGIN_MIN == 0.08
    assert data["purpose"] == "threshold_calibration_only_not_holdout"


def test_holdout_classification_has_10_per_psst():
    labels = json.loads((HOLDOUT / "classification_labels.json").read_text(encoding="utf-8"))[
        "labels"
    ]
    counts = Counter(row["psst"] for row in labels)
    assert len(labels) >= 40
    for psst in PSST_FOUR:
        assert counts[psst] == 10, f"{psst} count={counts[psst]}"


def test_holdout_matching_has_10_per_psst():
    cases = json.loads((HOLDOUT / "matching_labels.json").read_text(encoding="utf-8"))["cases"]
    counts = Counter(case["anchor"]["psst"] for case in cases)
    assert len(cases) >= 40
    for psst in PSST_FOUR:
        assert counts[psst] == 10, f"{psst} count={counts[psst]}"


def test_calibration_sample_ids_do_not_overlap_holdout():
    holdout_cls = json.loads((HOLDOUT / "classification_labels.json").read_text(encoding="utf-8"))
    holdout_ids = {row["id"] for row in holdout_cls["labels"]}
    cal = json.loads((CALIBRATION / "classification_samples.json").read_text(encoding="utf-8"))
    cal_ids = {row["id"] for row in cal["samples"]}
    assert holdout_ids.isdisjoint(cal_ids)
    assert cal["purpose"].endswith("not_holdout")
