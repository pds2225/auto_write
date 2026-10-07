"""PSST 이미지 분류기 — 폴더명·파일명·텍스트 힌트 우선, OCR은 opt-in."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from auto_write.image_automation.models import PsstClass, VisualAsset

# 기존 라이브러리 폴더명 우선 힌트
_FOLDER_HINTS: list[tuple[re.Pattern[str], PsstClass]] = [
    (re.compile(r"1\s*[\.\-_ ]?\s*문제인식|문제\s*인식|problem", re.I), PsstClass.PROBLEM),
    (re.compile(r"2\s*[\.\-_ ]?\s*실현가능성|실현\s*가능|solution|feasib", re.I), PsstClass.SOLUTION),
    (re.compile(r"3\s*[\.\-_ ]?\s*성장전략|성장\s*전략|scale[\s_-]?up|성장", re.I), PsstClass.SCALE_UP),
    (re.compile(r"4\s*[\.\-_ ]?\s*기업구성|팀\s*구성|조직|team", re.I), PsstClass.TEAM),
]

_KEYWORD_HINTS: list[tuple[tuple[str, ...], PsstClass]] = [
    (("시장규모", "TAM", "문제", "pain", "니즈", "고객고충", "현황", "기회"), PsstClass.PROBLEM),
    (("실현", "기술", "아키텍처", "프로세스", "프로토타입", "솔루션", "구현"), PsstClass.SOLUTION),
    (("성장", "스케일", "매출", "확장", "로드맵", "시장진입", "BM", "수익"), PsstClass.SCALE_UP),
    (("팀", "조직", "인력", "대표", "구성원", "역할", "기업구성"), PsstClass.TEAM),
]

VIEW_DIRS = {
    PsstClass.PROBLEM: "01_problem",
    PsstClass.SOLUTION: "02_solution",
    PsstClass.SCALE_UP: "03_scale_up",
    PsstClass.TEAM: "04_team",
    PsstClass.UNCLASSIFIED: "99_unclassified",
}

_DEFAULT_VISUAL = {
    PsstClass.PROBLEM: "막대/도넛 차트",
    PsstClass.SOLUTION: "플로우차트/구성도",
    PsstClass.SCALE_UP: "타임라인/간트",
    PsstClass.TEAM: "조직도",
    PsstClass.UNCLASSIFIED: "",
}


@dataclass(frozen=True)
class ClassifyResult:
    assets: list[VisualAsset]
    view: dict[str, list[str]]  # psst -> asset_ids
    counts: dict[str, int]


def classify_from_hints(
    *,
    parent_hint: str = "",
    filename: str = "",
    text_hint: str = "",
) -> PsstClass:
    blob_folder = parent_hint or ""
    for pattern, cls in _FOLDER_HINTS:
        if pattern.search(blob_folder):
            return cls

    blob = f"{parent_hint} {filename} {text_hint}".lower()
    scores: dict[PsstClass, int] = defaultdict(int)
    for keywords, cls in _KEYWORD_HINTS:
        for kw in keywords:
            if kw.lower() in blob:
                scores[cls] += 1
    if not scores:
        return PsstClass.UNCLASSIFIED
    best = max(scores.items(), key=lambda kv: kv[1])
    # 동점이면 unclassified (오분류 방지)
    tied = [c for c, s in scores.items() if s == best[1]]
    if len(tied) > 1:
        return PsstClass.UNCLASSIFIED
    return best[0]


def classify_asset(asset: VisualAsset) -> VisualAsset:
    cls = classify_from_hints(
        parent_hint=asset.parent_hint,
        filename=asset.source_label or asset.path_rel,
        text_hint=asset.text_hint,
    )
    data = asset.model_dump()
    data["psst"] = cls.value
    if not data.get("visual_type"):
        data["visual_type"] = _DEFAULT_VISUAL.get(cls, "")
    return VisualAsset(**data)


def classify_assets(assets: list[VisualAsset]) -> ClassifyResult:
    classified = [classify_asset(a) for a in assets]
    view: dict[str, list[str]] = {v: [] for v in VIEW_DIRS.values()}
    for a in classified:
        view.setdefault(a.psst, []).append(a.asset_id)
    counts = {k: len(v) for k, v in view.items()}
    return ClassifyResult(assets=classified, view=view, counts=counts)


def write_classify_view(
    result: ClassifyResult,
    out_dir: Path,
    *,
    copy_links_from: Path | None = None,
) -> Path:
    """manifest view JSON + 선택적 분류 폴더(심볼릭 대신 메타만 기본)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in VIEW_DIRS.values():
        (out_dir / name).mkdir(parents=True, exist_ok=True)

    # 원본 불변: 파일을 이동하지 않고 view 목록만 기록.
    # copy_links_from 이 있으면 해당 디렉터리의 asset 파일을 view 하위에 복사.
    if copy_links_from is not None:
        by_id = {a.asset_id: a for a in result.assets}
        src_root = Path(copy_links_from)
        for psst, ids in result.view.items():
            for aid in ids:
                asset = by_id.get(aid)
                if asset is None:
                    continue
                src = src_root / asset.path_rel
                if src.is_file():
                    dest = out_dir / psst / Path(asset.path_rel).name
                    if not dest.exists():
                        dest.write_bytes(src.read_bytes())

    manifest = {
        "counts": result.counts,
        "view": result.view,
        "assets": [a.model_dump() for a in result.assets],
    }
    path = out_dir / "classify_manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def macro_f1(y_true: list[str], y_pred: list[str], labels: list[str]) -> float:
    """단순 macro-F1 (hold-out 평가용)."""
    if len(y_true) != len(y_pred) or not y_true:
        return 0.0
    f1s: list[float] = []
    for label in labels:
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == label and p == label)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t != label and p == label)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == label and p != label)
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1s.append(0.0 if (prec + rec) == 0 else 2 * prec * rec / (prec + rec))
    return sum(f1s) / len(f1s)
