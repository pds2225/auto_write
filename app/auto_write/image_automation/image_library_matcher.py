"""앵커↔이미지 매칭 + contact sheet / review 리포트."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from auto_write.image_automation.models import (
    AnchorCandidate,
    MatchAction,
    MatchDecision,
    PsstClass,
    VisualAsset,
)
from auto_write.services.infographic_suggest import ImageSuggestion, _SUGGESTION_RULES

AUTO_THRESHOLD = 0.78
REVIEW_THRESHOLD = 0.60
MARGIN_MIN = 0.08

# visual_type → 기본 PSST 힌트
_VISUAL_TO_PSST: dict[str, str] = {
    "막대/도넛 차트": PsstClass.PROBLEM.value,
    "타임라인/간트": PsstClass.SCALE_UP.value,
    "조직도": PsstClass.TEAM.value,
    "플로우/밸류체인 도식": PsstClass.SCALE_UP.value,
    "플로우차트/구성도": PsstClass.SOLUTION.value,
    "비교표/포지셔닝맵": PsstClass.PROBLEM.value,
    "추세 선/막대 그래프": PsstClass.SCALE_UP.value,
}


@dataclass(frozen=True)
class MatchReport:
    decisions: list[MatchDecision]
    auto_count: int
    review_count: int
    skip_count: int
    contact_sheet: Path | None
    report_path: Path | None


def _anchor_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def anchors_from_suggestions(suggestions: list[ImageSuggestion]) -> list[AnchorCandidate]:
    anchors: list[AnchorCandidate] = []
    for i, s in enumerate(suggestions, start=1):
        psst = _VISUAL_TO_PSST.get(s.visual_type, PsstClass.UNCLASSIFIED.value)
        text = s.anchor_text or s.caption or s.keyword
        anchors.append(
            AnchorCandidate(
                anchor_id=f"anchor-{i:03d}",
                section=s.caption,
                psst=psst,
                anchor_hash=_anchor_hash(text),
                location_id=f"para:{i}",
                needed_visual_type=s.visual_type,
                keywords=[s.keyword] if s.keyword else [],
                text_preview=text[:120],
            )
        )
    return anchors


def anchors_from_text_blocks(blocks: list[str], *, max_anchors: int = 8) -> list[AnchorCandidate]:
    """문서 텍스트 블록에서 기존 suggestion rules로 앵커 생성."""
    used_types: set[str] = set()
    suggestions: list[ImageSuggestion] = []
    for text in blocks:
        if len(suggestions) >= max_anchors:
            break
        for keywords, vtype, caption, prompt in _SUGGESTION_RULES:
            if vtype in used_types:
                continue
            hit = next((kw for kw in keywords if kw in text), None)
            if hit:
                suggestions.append(
                    ImageSuggestion(
                        anchor_text=text,
                        visual_type=vtype,
                        caption=caption,
                        prompt=prompt,
                        keyword=hit,
                    )
                )
                used_types.add(vtype)
                break
    return anchors_from_suggestions(suggestions)


def _score_pair(anchor: AnchorCandidate, asset: VisualAsset) -> tuple[float, dict[str, float]]:
    detail: dict[str, float] = {}

    # PSST 35%
    if asset.psst == PsstClass.UNCLASSIFIED.value or anchor.psst == PsstClass.UNCLASSIFIED.value:
        detail["psst"] = 0.15
    elif asset.psst == anchor.psst:
        detail["psst"] = 1.0
    else:
        detail["psst"] = 0.0

    # 핵심어 30%
    blob = f"{asset.source_label} {asset.parent_hint} {asset.text_hint} {asset.visual_type}".lower()
    kws = [k for k in anchor.keywords if k]
    if not kws and anchor.text_preview:
        # 텍스트 일부 토큰
        kws = [t for t in anchor.text_preview.replace("/", " ").split() if len(t) >= 2][:5]
    hits = sum(1 for k in kws if k.lower() in blob)
    detail["keyword"] = min(1.0, hits / max(1, min(3, len(kws) or 1)))

    # visual type 20%
    if anchor.needed_visual_type and asset.visual_type:
        detail["visual_type"] = 1.0 if anchor.needed_visual_type == asset.visual_type else 0.2
    elif anchor.needed_visual_type:
        # 자산 visual_type 미지정이면 키워드/PSST에 맡김
        detail["visual_type"] = 0.5
    else:
        detail["visual_type"] = 0.4

    # 출처/해상도 10%
    pixels = max(0, asset.width * asset.height)
    if pixels >= 800 * 600:
        detail["source_res"] = 1.0
    elif pixels >= 400 * 300:
        detail["source_res"] = 0.7
    elif pixels > 0:
        detail["source_res"] = 0.4
    else:
        detail["source_res"] = 0.3

    # 중복 방지 5% — 호출측에서 used 자산이면 0 처리
    detail["dup"] = 1.0

    score = (
        0.35 * detail["psst"]
        + 0.30 * detail["keyword"]
        + 0.20 * detail["visual_type"]
        + 0.10 * detail["source_res"]
        + 0.05 * detail["dup"]
    )
    return score, detail


def match_assets_to_anchors(
    anchors: list[AnchorCandidate],
    assets: list[VisualAsset],
    *,
    unique_asset: bool = True,
) -> list[MatchDecision]:
    used_assets: set[str] = set()
    used_anchors: set[str] = set()
    decisions: list[MatchDecision] = []

    # 앵커별 상위 점수 계산
    for anchor in anchors:
        if anchor.anchor_id in used_anchors:
            decisions.append(
                MatchDecision(
                    anchor_id=anchor.anchor_id,
                    action=MatchAction.SKIP,
                    reason="duplicate_anchor",
                )
            )
            continue

        scored: list[tuple[float, dict[str, float], VisualAsset]] = []
        for asset in assets:
            if unique_asset and asset.asset_id in used_assets:
                continue
            score, detail = _score_pair(anchor, asset)
            if unique_asset:
                # 이미 사용된 자산은 dup 항을 0으로 재계산하지 않고 후보에서 제외
                pass
            scored.append((score, detail, asset))

        scored.sort(key=lambda x: x[0], reverse=True)
        if not scored:
            decisions.append(
                MatchDecision(
                    anchor_id=anchor.anchor_id,
                    action=MatchAction.SKIP,
                    reason="no_candidates",
                )
            )
            continue

        best_score, best_detail, best_asset = scored[0]
        runner = scored[1][0] if len(scored) > 1 else None
        margin_ok = runner is None or (best_score - runner) >= MARGIN_MIN

        if best_score >= AUTO_THRESHOLD and margin_ok:
            action = MatchAction.AUTO
            reason = "auto"
            used_assets.add(best_asset.asset_id)
            used_anchors.add(anchor.anchor_id)
        elif best_score >= REVIEW_THRESHOLD:
            action = MatchAction.REVIEW
            reason = "low_margin" if not margin_ok else "review_band"
            # review 는 자동 사용 확정하지 않음 — unique 예약도 하지 않음
        else:
            action = MatchAction.SKIP
            reason = "below_threshold"

        decisions.append(
            MatchDecision(
                anchor_id=anchor.anchor_id,
                asset_id=best_asset.asset_id if action != MatchAction.SKIP else "",
                score=round(best_score, 4),
                score_detail={k: round(v, 4) for k, v in best_detail.items()},
                action=action,
                insert_status="pending" if action == MatchAction.AUTO else action.value,
                reason=reason,
                runner_up_score=None if runner is None else round(runner, 4),
            )
        )
    return decisions


def write_match_report(
    decisions: list[MatchDecision],
    out_dir: Path,
    *,
    anchors: list[AnchorCandidate] | None = None,
) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "match_report.json"
    payload = {
        "decisions": [d.model_dump() for d in decisions],
        "summary": {
            "auto": sum(1 for d in decisions if d.action == MatchAction.AUTO),
            "review": sum(1 for d in decisions if d.action == MatchAction.REVIEW),
            "skip": sum(1 for d in decisions if d.action == MatchAction.SKIP),
        },
        "anchors": [a.model_dump() for a in (anchors or [])],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # review 목록 (사람 확인용)
    review_lines = ["# Match review list", ""]
    for d in decisions:
        if d.action != MatchAction.REVIEW:
            continue
        review_lines.append(
            f"- anchor={d.anchor_id} asset={d.asset_id} score={d.score} "
            f"runner_up={d.runner_up_score} reason={d.reason}"
        )
    (out_dir / "review_list.md").write_text("\n".join(review_lines) + "\n", encoding="utf-8")
    return path


def build_contact_sheet(
    assets: list[VisualAsset],
    decisions: list[MatchDecision],
    image_root: Path,
    out_path: Path,
    *,
    thumb: int = 128,
    cols: int = 4,
) -> Path | None:
    """매칭 후보 썸네일 contact sheet. Pillow 사용. 이미지 없으면 None."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return None

    chosen_ids = [d.asset_id for d in decisions if d.asset_id]
    by_id = {a.asset_id: a for a in assets}
    tiles: list[tuple[str, Image.Image]] = []
    for aid in chosen_ids:
        asset = by_id.get(aid)
        if asset is None:
            continue
        src = Path(image_root) / asset.path_rel
        if not src.is_file():
            continue
        try:
            im = Image.open(src).convert("RGB")
            im.thumbnail((thumb, thumb))
            tiles.append((aid, im))
        except Exception:
            continue

    if not tiles:
        return None

    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * thumb, rows * thumb), (245, 245, 245))
    draw = ImageDraw.Draw(sheet)
    for i, (aid, im) in enumerate(tiles):
        r, c = divmod(i, cols)
        x, y = c * thumb, r * thumb
        sheet.paste(im, (x, y))
        draw.text((x + 2, y + 2), aid[:10], fill=(20, 20, 20))
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)
    return out_path


def run_match_pipeline(
    anchors: list[AnchorCandidate],
    assets: list[VisualAsset],
    *,
    image_root: Path,
    out_dir: Path,
) -> MatchReport:
    decisions = match_assets_to_anchors(anchors, assets)
    report_path = write_match_report(decisions, out_dir, anchors=anchors)
    contact = build_contact_sheet(
        assets,
        decisions,
        image_root,
        Path(out_dir) / "contact_sheet.png",
    )
    return MatchReport(
        decisions=decisions,
        auto_count=sum(1 for d in decisions if d.action == MatchAction.AUTO),
        review_count=sum(1 for d in decisions if d.action == MatchAction.REVIEW),
        skip_count=sum(1 for d in decisions if d.action == MatchAction.SKIP),
        contact_sheet=contact,
        report_path=report_path,
    )
