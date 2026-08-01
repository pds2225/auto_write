"""PSST 분류기 단위 테스트 + hold-out macro F1."""

from __future__ import annotations

import json
from pathlib import Path

from auto_write.image_automation.models import PsstClass, VisualAsset
from auto_write.image_automation.psst_image_classifier import (
    classify_assets,
    classify_from_hints,
    macro_f1,
)


def test_folder_hint_priority():
    assert classify_from_hints(parent_hint="1.문제인식", filename="a.png") == PsstClass.PROBLEM
    assert classify_from_hints(parent_hint="2.실현가능성", filename="b.png") == PsstClass.SOLUTION
    assert classify_from_hints(parent_hint="3.성장전략", filename="c.png") == PsstClass.SCALE_UP
    assert classify_from_hints(parent_hint="4.기업구성", filename="d.png") == PsstClass.TEAM


def test_keyword_fallback():
    assert classify_from_hints(filename="시장규모_TAM.png") == PsstClass.PROBLEM
    assert classify_from_hints(filename="기술_아키텍처.png") == PsstClass.SOLUTION
    assert classify_from_hints(text_hint="조직도 팀 역할") == PsstClass.TEAM


def test_unknown_is_unclassified():
    assert classify_from_hints(filename="random_photo.png") == PsstClass.UNCLASSIFIED


def test_classify_assets_view_keys(tmp_path: Path):
    assets = [
        VisualAsset(asset_id="a1", path_rel="a.png", parent_hint="1.문제인식", width=800, height=600),
        VisualAsset(asset_id="a2", path_rel="b.png", parent_hint="4.기업구성", width=800, height=600),
    ]
    result = classify_assets(assets)
    assert result.counts[PsstClass.PROBLEM.value] == 1
    assert result.counts[PsstClass.TEAM.value] == 1
    assert result.assets[0].visual_type


def test_holdout_macro_f1_at_least_0_90():
    # Acceptance gate uses holdout/ only — never calibration/.
    root = Path(__file__).resolve().parent / "fixtures" / "image_automation"
    fixture = root / "holdout" / "classification_labels.json"
    assert "calibration" not in fixture.parts
    data = json.loads(fixture.read_text(encoding="utf-8"))
    labels = data["labels"]
    y_true = []
    y_pred = []
    for row in labels:
        truth = row["psst"]
        pred = classify_from_hints(
            parent_hint=row.get("parent_hint", ""),
            filename=row.get("filename", ""),
            text_hint=row.get("text_hint", ""),
        ).value
        y_true.append(truth)
        y_pred.append(pred)
    classes = [
        PsstClass.PROBLEM.value,
        PsstClass.SOLUTION.value,
        PsstClass.SCALE_UP.value,
        PsstClass.TEAM.value,
    ]
    score = macro_f1(y_true, y_pred, classes)
    assert len(labels) >= 40
    assert score >= 0.90, f"macro F1={score:.3f} < 0.90"
