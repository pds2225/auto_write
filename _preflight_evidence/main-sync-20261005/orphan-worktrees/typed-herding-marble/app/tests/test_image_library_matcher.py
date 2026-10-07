"""매칭 점수·margin·중복 방지·contact sheet."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from auto_write.image_automation.image_library_matcher import (
    MARGIN_MIN,
    MatchAction,
    anchors_from_text_blocks,
    match_assets_to_anchors,
    run_match_pipeline,
)
from auto_write.image_automation.models import AnchorCandidate, PsstClass, VisualAsset
from auto_write.image_automation.psst_image_classifier import classify_assets


def _asset(aid: str, psst: str, *, w=800, h=600, label="", vtype="") -> VisualAsset:
    return VisualAsset(
        asset_id=aid,
        source_kind="library",
        path_rel=f"{aid}.png",
        width=w,
        height=h,
        psst=psst,
        visual_type=vtype or ("조직도" if psst == PsstClass.TEAM.value else "막대/도넛 차트"),
        source_label=label or aid,
        parent_hint=psst,
        text_hint=label or aid,
    )


def test_high_score_auto_and_unique_asset():
    anchors = [
        AnchorCandidate(
            anchor_id="a1",
            psst=PsstClass.TEAM.value,
            needed_visual_type="조직도",
            keywords=["팀", "조직"],
            text_preview="팀 구성 조직도",
        ),
        AnchorCandidate(
            anchor_id="a2",
            psst=PsstClass.TEAM.value,
            needed_visual_type="조직도",
            keywords=["팀"],
            text_preview="인력구성",
        ),
    ]
    assets = [
        _asset("team1", PsstClass.TEAM.value, label="팀구성_조직도", vtype="조직도"),
        _asset("prob1", PsstClass.PROBLEM.value, label="시장규모", vtype="막대/도넛 차트"),
    ]
    decisions = match_assets_to_anchors(anchors, assets)
    assert decisions[0].action == MatchAction.AUTO
    assert decisions[0].asset_id == "team1"
    # 같은 이미지는 1회만
    assert decisions[1].asset_id != "team1" or decisions[1].action != MatchAction.AUTO


def test_low_margin_goes_to_review():
    anchor = AnchorCandidate(
        anchor_id="a1",
        psst=PsstClass.PROBLEM.value,
        needed_visual_type="막대/도넛 차트",
        keywords=["시장규모"],
        text_preview="시장규모 TAM",
    )
    assets = [
        _asset("p1", PsstClass.PROBLEM.value, label="시장규모_A", vtype="막대/도넛 차트"),
        _asset("p2", PsstClass.PROBLEM.value, label="시장규모_B", vtype="막대/도넛 차트"),
    ]
    decisions = match_assets_to_anchors([anchor], assets)
    d = decisions[0]
    assert d.runner_up_score is not None
    if (d.score - d.runner_up_score) < MARGIN_MIN:
        assert d.action == MatchAction.REVIEW


def test_contact_sheet_and_review_list(tmp_path: Path):
    img_root = tmp_path / "imgs"
    img_root.mkdir()
    for name, color in [("team1.png", (0, 0, 200)), ("prob1.png", (200, 0, 0))]:
        Image.new("RGB", (640, 480), color).save(img_root / name)

    assets = classify_assets(
        [
            VisualAsset(
                asset_id="team1",
                path_rel="team1.png",
                width=640,
                height=480,
                parent_hint="4.기업구성",
                source_label="팀구성",
                text_hint="팀구성 조직도",
            ),
            VisualAsset(
                asset_id="prob1",
                path_rel="prob1.png",
                width=640,
                height=480,
                parent_hint="1.문제인식",
                source_label="시장규모",
                text_hint="시장규모 TAM",
            ),
        ]
    ).assets
    anchors = anchors_from_text_blocks(
        ["팀 구성과 조직도", "시장규모 TAM SAM 성장률"]
    )
    report = run_match_pipeline(anchors, assets, image_root=img_root, out_dir=tmp_path / "match")
    assert report.report_path and report.report_path.is_file()
    assert (tmp_path / "match" / "review_list.md").is_file()
    data = json.loads(report.report_path.read_text(encoding="utf-8"))
    assert "summary" in data


def test_matching_holdout_top1():
    # Acceptance gate uses holdout/ only — never calibration/.
    # expected_action=review: low-margin/tie scored as correct review (not auto-insert).
    root = Path(__file__).resolve().parent / "fixtures" / "image_automation"
    fixture = root / "holdout" / "matching_labels.json"
    assert "calibration" not in fixture.parts
    data = json.loads(fixture.read_text(encoding="utf-8"))
    cases = data["cases"]
    correct = 0
    for case in cases:
        anchor = AnchorCandidate(**case["anchor"])
        assets = [VisualAsset(**a) for a in case["assets"]]
        decisions = match_assets_to_anchors([anchor], assets, unique_asset=True)
        d = decisions[0]
        expected = case["expected_asset_id"]
        expected_action = case.get("expected_action", "auto")
        if expected_action == "review":
            # margin/동점은 review 로 채점 (오답 자동삽입 아님)
            if d.action == MatchAction.REVIEW:
                correct += 1
            continue
        if d.action == MatchAction.AUTO and d.asset_id == expected:
            correct += 1
        elif d.action == MatchAction.REVIEW and d.asset_id == expected:
            # review 도 top-1 일치면 부분 인정하지 않음 — holdout 은 auto만 정답
            pass
    acc = correct / len(cases)
    assert len(cases) >= 40
    assert acc >= 0.90, f"top-1 accuracy={acc:.3f} < 0.90"
