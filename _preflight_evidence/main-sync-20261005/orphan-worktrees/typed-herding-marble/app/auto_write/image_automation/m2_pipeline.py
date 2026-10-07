"""M2 파이프라인: CLASSIFY + MATCH (라이브러리/슬라이드 PSST 분류·매칭)."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from auto_write.image_automation.image_library_index import index_image_library, write_library_index
from auto_write.image_automation.image_library_matcher import (
    anchors_from_text_blocks,
    run_match_pipeline,
)
from auto_write.image_automation.models import PipelineStage, RunManifest, StageStatus, VisualAsset
from auto_write.image_automation.paths import ensure_run_dirs
from auto_write.image_automation.psst_image_classifier import classify_assets, write_classify_view
from auto_write.image_automation.receipts import append_event, monotonic_ms
from auto_write.image_automation.slide_asset_extractor import extract_slides


@dataclass
class M2Result:
    run_id: str
    run_dir: Path
    manifest: RunManifest
    draft: bool
    report: dict[str, Any]


def new_run_id() -> str:
    return uuid.uuid4().hex[:12]


def _load_slide_assets_as_visual(slides_dir: Path) -> list[VisualAsset]:
    """M1 slides_manifest 또는 PNG 디렉터리에서 VisualAsset 목록 구성."""
    man = slides_dir / "slides_manifest.json"
    if man.is_file():
        data = json.loads(man.read_text(encoding="utf-8"))
        assets = [VisualAsset(**a) for a in data.get("assets", [])]
        for a in assets:
            if not a.parent_hint:
                a.parent_hint = "slides"
            if not a.text_hint:
                a.text_hint = a.path_rel
        return assets
    assets = []
    for png in sorted(slides_dir.glob("slide-*.png")):
        from auto_write.image_automation.paths import sha256_file

        digest = sha256_file(png)
        assets.append(
            VisualAsset(
                asset_id=f"slide-{digest[:12]}",
                source_kind="slide",
                path_rel=png.name,
                sha256=digest,
                parent_hint="slides",
                text_hint=png.stem,
            )
        )
    return assets


def run_m2(
    *,
    results_root: Path,
    library: Path | None = None,
    slides_dir: Path | None = None,
    document_text_blocks: list[str] | None = None,
    run_id: str | None = None,
    copy_library: bool = True,
) -> M2Result:
    """라이브러리(+옵션 슬라이드)를 PSST 분류하고 문서 앵커와 매칭한다.

    원본 라이브러리는 이동/삭제하지 않는다. 삽입은 M3 범위이므로 여기서 하지 않는다.
    """
    rid = run_id or new_run_id()
    dirs = ensure_run_dirs(rid, results_root)
    events = dirs["root"] / "events.jsonl"
    manifest = RunManifest(run_id=rid)
    report: dict[str, Any] = {"run_id": rid, "manual_actions": []}

    all_assets: list[VisualAsset] = []
    image_root = dirs["library_view"]

    # --- index library ---
    if library is not None:
        append_event(events, run_id=rid, stage=PipelineStage.CLASSIFY.value, attempt=1, event="START")
        copy_into = dirs["library_view"] / "copies" if copy_library else None
        if copy_into is not None:
            copy_into.mkdir(parents=True, exist_ok=True)
            image_root = copy_into
        indexed = index_image_library(Path(library), copy_into=copy_into)
        write_library_index(indexed.assets, dirs["library_view"] / "library_index.json")
        all_assets.extend(indexed.assets)
        report["library"] = {"count": indexed.count, "copied": bool(copy_into)}
    else:
        append_event(events, run_id=rid, stage=PipelineStage.CLASSIFY.value, attempt=1, event="START")
        report["library"] = {"count": 0, "copied": False}

    # --- optional M1 slides ---
    if slides_dir is not None and Path(slides_dir).is_dir():
        slide_assets = _load_slide_assets_as_visual(Path(slides_dir))
        # slides stay in slides_dir; for contact sheet use that root when no library copies
        if library is None:
            image_root = Path(slides_dir)
        all_assets.extend(slide_assets)
        report["slides_assets"] = len(slide_assets)

    if not all_assets:
        manifest.stages[PipelineStage.CLASSIFY.value] = StageStatus.FAIL
        manifest.draft = True
        report["error"] = "no_assets"
        append_event(
            events,
            run_id=rid,
            stage=PipelineStage.CLASSIFY.value,
            attempt=1,
            event="FAIL",
            code="no_assets",
        )
        man_path = dirs["root"] / "manifest.json"
        man_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
        (dirs["root"] / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return M2Result(run_id=rid, run_dir=dirs["root"], manifest=manifest, draft=True, report=report)

    # --- classify ---
    t_cls = monotonic_ms()
    classified = classify_assets(all_assets)
    write_classify_view(
        classified,
        dirs["classify"],
        copy_links_from=image_root if image_root.is_dir() else None,
    )
    manifest.assets = classified.assets
    manifest.stages[PipelineStage.CLASSIFY.value] = StageStatus.DONE
    append_event(
        events,
        run_id=rid,
        stage=PipelineStage.CLASSIFY.value,
        attempt=1,
        event="END",
        code="done",
        duration_ms=monotonic_ms() - t_cls,
        counters=classified.counts,
    )
    report["classify"] = {"counts": classified.counts}

    # --- match ---
    t_m = monotonic_ms()
    append_event(events, run_id=rid, stage=PipelineStage.MATCH.value, attempt=1, event="START")
    blocks = list(document_text_blocks or [])
    if not blocks:
        # 라이브러리만 있을 때 분류 view를 앵커 대신 review 대상으로 남긴다
        blocks = [
            "시장규모와 고객 문제를 보여주는 현황 분석",
            "핵심 기술 아키텍처와 실현가능성",
            "성장전략 로드맵과 매출 계획",
            "팀 구성과 조직도",
        ]
    anchors = anchors_from_text_blocks(blocks)
    match = run_match_pipeline(
        anchors,
        classified.assets,
        image_root=image_root,
        out_dir=dirs["match"],
    )
    manifest.anchors = anchors
    manifest.matches = match.decisions
    manifest.stages[PipelineStage.MATCH.value] = StageStatus.DONE
    append_event(
        events,
        run_id=rid,
        stage=PipelineStage.MATCH.value,
        attempt=1,
        event="END",
        code="done",
        duration_ms=monotonic_ms() - t_m,
        counters={
            "auto": match.auto_count,
            "review": match.review_count,
            "skip": match.skip_count,
        },
    )
    report["match"] = {
        "auto": match.auto_count,
        "review": match.review_count,
        "skip": match.skip_count,
        "report": str(match.report_path) if match.report_path else "",
        "contact_sheet": str(match.contact_sheet) if match.contact_sheet else "",
        "review_list": str(dirs["match"] / "review_list.md"),
    }
    # M2는 삽입 전 단계 — review/skip 이 있어도 성공으로 보되, auto 0이면 draft 힌트
    draft = match.auto_count == 0 and match.review_count > 0
    manifest.draft = draft
    report["draft"] = draft
    report["manual_actions"] = [
        "contact sheet와 review_list.md를 확인한 뒤 M3 삽입으로 진행하세요."
    ]

    man_path = dirs["root"] / "manifest.json"
    man_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    (dirs["root"] / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return M2Result(run_id=rid, run_dir=dirs["root"], manifest=manifest, draft=draft, report=report)


def extract_and_classify_slides(
    slides_input: Path,
    results_root: Path,
    *,
    run_id: str | None = None,
) -> M2Result:
    """PDF/PPTX를 분리한 뒤 분류·매칭까지 (라이브러리 없이 슬라이드만)."""
    rid = run_id or new_run_id()
    dirs = ensure_run_dirs(rid, results_root)
    extract_slides(Path(slides_input), dirs["slides"])
    return run_m2(results_root=results_root, slides_dir=dirs["slides"], run_id=rid)
