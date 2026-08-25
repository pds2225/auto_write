"""M4 GENERATE_MISSING mock: gpt-image-1 only, Gemini=0, budget cap."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from auto_write.services.image_providers import (
    GPT_IMAGE_MODEL,
    build_missing_gpt_writer,
    generate_missing_gpt_image,
)
from auto_write.image_automation.generate_missing import (
    generate_missing_assets,
    missing_anchors,
)
from auto_write.image_automation.models import (
    AnchorCandidate,
    MatchAction,
    MatchDecision,
    PsstClass,
)


def _anchors(n: int = 3) -> list[AnchorCandidate]:
    return [
        AnchorCandidate(
            anchor_id=f"a{i}",
            psst=PsstClass.PROBLEM.value,
            needed_visual_type="막대/도넛 차트",
            keywords=["시장규모"],
            text_preview=f"시장규모 앵커 {i}",
        )
        for i in range(1, n + 1)
    ]


def test_disabled_makes_zero_calls(tmp_path: Path):
    anchors = _anchors(2)
    decisions = [
        MatchDecision(anchor_id="a1", action=MatchAction.SKIP, reason="below_threshold"),
        MatchDecision(anchor_id="a2", action=MatchAction.REVIEW, reason="low_margin"),
    ]
    result = generate_missing_assets(
        anchors,
        decisions,
        out_dir=tmp_path,
        enabled=False,
        missing_only=True,
        max_paid_calls=5,
    )
    assert result.openai_calls == 0
    assert result.gemini_calls == 0
    assert result.generated == []
    assert set(result.skipped) == {"a1", "a2"}
    assert result.draft is True
    assert result.extras.get("reason") == "disabled"


def test_mock_gpt_image_only_and_budget(tmp_path: Path):
    anchors = _anchors(3)
    # one AUTO match → only 2 missing
    decisions = [
        MatchDecision(
            anchor_id="a1",
            asset_id="lib1",
            action=MatchAction.AUTO,
            score=0.9,
        ),
        MatchDecision(anchor_id="a2", action=MatchAction.SKIP, reason="below_threshold"),
        MatchDecision(anchor_id="a3", action=MatchAction.REVIEW, reason="low_margin"),
    ]
    assert [a.anchor_id for a in missing_anchors(anchors, decisions)] == ["a2", "a3"]

    result = generate_missing_assets(
        anchors,
        decisions,
        out_dir=tmp_path / "gen",
        enabled=True,
        missing_only=True,
        max_paid_calls=1,  # budget 1 < missing 2
        use_mock=True,
    )
    assert result.gemini_calls == 0
    assert result.openai_calls == 1
    assert len(result.generated) == 1
    assert result.skipped == ["a3"]
    assert result.draft is True  # mock path always draft
    assert all(c.provider == "mock" and c.model == GPT_IMAGE_MODEL for c in result.call_log)
    assert result.receipt_path and result.receipt_path.is_file()
    receipt = json.loads(result.receipt_path.read_text(encoding="utf-8"))
    assert receipt["gemini_calls"] == 0
    assert receipt["model"] == "gpt-image-1"
    assert receipt["openai_calls"] == 1
    assert receipt["openai_calls_real"] == 0
    assert receipt["mock_calls"] == 1
    assert receipt["use_mock"] is True
    assert (tmp_path / "gen" / result.generated[0].path_rel).is_file()


def test_calls_capped_by_missing_and_max(tmp_path: Path):
    anchors = _anchors(4)
    decisions = [MatchDecision(anchor_id=a.anchor_id, action=MatchAction.SKIP) for a in anchors]
    result = generate_missing_assets(
        anchors,
        decisions,
        out_dir=tmp_path,
        enabled=True,
        missing_only=True,
        max_paid_calls=10,
    )
    # missing=4, max=10 → calls = 4
    assert result.openai_calls == 4
    assert result.gemini_calls == 0
    assert len(result.skipped) == 0
    assert result.draft is True  # mock always draft
    assert result.extras.get("mock_calls") == 4
    assert result.extras.get("openai_calls_real") == 0


def test_budget_zero_writes_receipt_and_skips(tmp_path: Path):
    anchors = _anchors(2)
    decisions = [MatchDecision(anchor_id=a.anchor_id, action=MatchAction.SKIP) for a in anchors]
    result = generate_missing_assets(
        anchors,
        decisions,
        out_dir=tmp_path / "budget0",
        enabled=True,
        missing_only=True,
        max_paid_calls=0,
        use_mock=True,
    )
    assert result.openai_calls == 0
    assert result.generated == []
    assert set(result.skipped) == {"a1", "a2"}
    assert result.draft is True
    assert result.extras.get("reason") == "budget_zero"
    assert result.receipt_path and result.receipt_path.is_file()
    receipt = json.loads(result.receipt_path.read_text(encoding="utf-8"))
    assert receipt["reason"] == "budget_zero"
    assert receipt["use_mock"] is True
    assert receipt["openai_calls_real"] == 0
    assert receipt["mock_calls"] == 0


def test_paid_path_without_key_is_no_writer(tmp_path: Path):
    anchors = _anchors(1)
    decisions = [MatchDecision(anchor_id="a1", action=MatchAction.SKIP)]
    result = generate_missing_assets(
        anchors,
        decisions,
        out_dir=tmp_path,
        enabled=True,
        missing_only=True,
        max_paid_calls=1,
        use_mock=False,
        settings=SimpleNamespace(has_openai=False),
        openai_service=None,
    )
    assert result.generated == []
    assert result.extras.get("reason") == "no_writer"
    assert result.gemini_calls == 0
    assert result.openai_calls == 0


def test_writer_oserror_skips_anchor(tmp_path: Path):
    anchors = _anchors(1)
    decisions = [MatchDecision(anchor_id="a1", action=MatchAction.SKIP)]

    def boom(prompt: str, out_path: Path, *, model: str = GPT_IMAGE_MODEL) -> None:
        raise OSError("generation failed")

    result = generate_missing_assets(
        anchors,
        decisions,
        out_dir=tmp_path,
        enabled=True,
        missing_only=True,
        max_paid_calls=1,
        use_mock=False,
        writer=boom,
    )
    assert result.generated == []
    assert result.skipped == ["a1"]
    assert result.gemini_calls == 0


def test_generate_missing_gpt_image_requires_openai_key(tmp_path: Path):
    out = tmp_path / "x.png"
    assert generate_missing_gpt_image(None, None, "prompt", out) is False
    assert generate_missing_gpt_image(
        SimpleNamespace(has_openai=False), None, "prompt", out
    ) is False
    assert not out.exists()


def test_generate_missing_gpt_image_rejects_other_models(tmp_path: Path):
    settings = SimpleNamespace(has_openai=True, openai_image_model="gpt-image-1")
    assert (
        generate_missing_gpt_image(
            settings, SimpleNamespace(), "prompt", tmp_path / "x.png", model="dall-e-3"
        )
        is False
    )


def test_build_missing_gpt_writer_none_without_key():
    assert build_missing_gpt_writer(None, None) is None
    assert build_missing_gpt_writer(SimpleNamespace(has_openai=False), None) is None
