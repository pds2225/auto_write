r"""quality_ratchet — 문서 품질 기준선(ratchet) 순수 로직.

mail 레포 ``scripts/accuracy_baseline.py`` 패턴 이식:
측정 요약(summary) → 기준선(baseline) ratchet 판정(나빠지면 게이트 실패,
좋아지면 기준선 전진) + trend 시계열 1행 생성.

지표 축 — 핵심목적("맞는 위치에, 원하는 서식으로, 글과 이미지 삽입",
위키 auto-write.md) 기준으로 doc_quality_score 9항목을 3축으로 묶는다:
  formatting(55) = bullet_spacing + paragraph_cleanup + font_consistency
                   + table_quality + emphasis
  placement(40)  = guide_removal + type_structure + psst_structure
  image(5)       = image_suggestion
  tests          = pytest passed/failed (회귀검증 축)

게이트(하드):
  tests_failed == 0
  tests_passed >= baseline (감소 금지)
  avg_total >= baseline (골든 문서셋이 동일할 때만 비교 — 셋이 바뀌면
  비교 불가이므로 게이트 없이 문서 기준선을 재설정하고 사유를 남긴다)

이 모듈은 파일 IO 를 하지 않는다(판정·집계 순수 함수만). IO 는
``app/quality_ratchet.py`` CLI 가 담당한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_EPS = 1e-9

# doc_quality_score.ScoreItem.key → 축 매핑 (9항목 전부, 빠짐없음)
DIMENSIONS: dict[str, tuple[str, ...]] = {
    "formatting": (
        "bullet_spacing", "paragraph_cleanup", "font_consistency",
        "table_quality", "emphasis",
    ),
    "placement": ("guide_removal", "type_structure", "psst_structure"),
    "image": ("image_suggestion",),
}

TREND_HEADER = [
    "run", "n_docs", "avg_total",
    "formatting_avg", "placement_avg", "image_avg",
    "tests_passed", "tests_failed",
]


def aggregate_dimensions(items: list[dict[str, Any]]) -> dict[str, float]:
    """QualityScore.as_dict()["items"] → 축별 점수 합.

    매핑에 없는 새 항목 key 가 생기면 조용히 누락되지 않도록 KeyError 를 낸다
    (채점 항목 추가 시 이 매핑도 갱신하라는 신호).
    """
    known = {k for keys in DIMENSIONS.values() for k in keys}
    result: dict[str, float] = {}
    for dim, keys in DIMENSIONS.items():
        result[dim] = round(sum(float(i["score"]) for i in items if i["key"] in keys), 1)
    unknown = [i["key"] for i in items if i["key"] not in known]
    if unknown:
        raise KeyError(f"DIMENSIONS 매핑에 없는 채점 항목: {unknown}")
    return result


def build_summary(
    doc_results: list[dict[str, Any]],
    tests: dict[str, int] | None,
    run_label: str,
) -> dict[str, Any]:
    """문서별 채점 결과 + pytest 결과 → summary dict."""
    n = len(doc_results)

    def _avg(key: str) -> float | None:
        if not n:
            return None
        return round(sum(float(d[key]) for d in doc_results) / n, 2)

    def _avg_dim(dim: str) -> float | None:
        if not n:
            return None
        return round(sum(float(d["dims"][dim]) for d in doc_results) / n, 2)

    return {
        "run": run_label,
        "n_docs": n,
        "doc_set": sorted(d["name"] for d in doc_results),
        "avg_total": _avg("total"),
        "dims_avg": {dim: _avg_dim(dim) for dim in DIMENSIONS},
        "docs": doc_results,
        "tests": tests,  # {"passed": int, "failed": int} | None(스킵)
    }


@dataclass
class GateResult:
    status: str
    exit_code: int              # 0 통과 / 2 게이트 위반
    baseline_out: dict[str, Any]  # 이번 실행 후 저장할 기준선
    failures: list[str] = field(default_factory=list)


def _baseline_from(summary: dict[str, Any], now_utc: str, prev: dict[str, Any] | None = None) -> dict[str, Any]:
    base = dict(prev or {})
    base.update({
        "updated_utc": now_utc,
        "source_run": summary["run"],
    })
    if summary["n_docs"] > 0:
        base.update({
            "n_docs": summary["n_docs"],
            "doc_set": summary["doc_set"],
            "avg_total": summary["avg_total"],
            "dims_avg": summary["dims_avg"],
        })
    if summary.get("tests") is not None:
        base["tests_passed"] = summary["tests"]["passed"]
        base["tests_failed"] = summary["tests"]["failed"]
    base.setdefault("gate", {
        "tests_failed": "==0 (하드)",
        "tests_passed": ">= baseline (하드)",
        "avg_total": ">= baseline, 동일 골든셋일 때 (하드)",
    })
    base.setdefault("note", "품질 게이트 ratchet 기준선. 테스트 무실패·비하락 + 골든 문서점수 비하락이 하드게이트.")
    return base


def gate(
    summary: dict[str, Any],
    baseline: dict[str, Any] | None,
    now_utc: str,
    *,
    seed: bool = False,
) -> GateResult:
    """ratchet 판정. baseline 없거나 --seed 면 시딩."""
    if baseline is None or seed:
        return GateResult("SEED (기준선 신규)", 0, _baseline_from(summary, now_utc))

    failures: list[str] = []
    tests = summary.get("tests")
    base_passed = baseline.get("tests_passed")

    if tests is not None:
        if tests["failed"] > 0:
            failures.append(f"tests_failed={tests['failed']}(>0)")
        if base_passed is not None and tests["passed"] < int(base_passed):
            failures.append(f"tests_passed {tests['passed']} < baseline {base_passed}")

    same_set = (
        summary["n_docs"] > 0
        and baseline.get("doc_set")
        and summary["doc_set"] == baseline.get("doc_set")
    )
    set_changed = summary["n_docs"] > 0 and baseline.get("doc_set") and not same_set
    base_avg = baseline.get("avg_total")
    if same_set and base_avg is not None and summary["avg_total"] < float(base_avg) - _EPS:
        failures.append(f"avg_total {summary['avg_total']} < baseline {base_avg}")

    if failures:
        return GateResult("FAIL " + " / ".join(failures), 2, dict(baseline), failures)

    # 통과 — 전진분만 기준선 갱신(이번 실행에서 스킵한 축은 기존값 유지)
    improved = bool(
        (tests is not None and (base_passed is None or tests["passed"] > int(base_passed)))
        or (same_set and base_avg is not None and summary["avg_total"] > float(base_avg) + _EPS)
        or (summary["n_docs"] > 0 and base_avg is None)
    )
    out = _baseline_from(summary, now_utc, prev=baseline)
    if set_changed:
        return GateResult("OK (골든셋 변경 → 문서 기준선 재설정)", 0, out)
    if improved:
        return GateResult("OK (baseline↑ 갱신)", 0, out)
    return GateResult("OK", 0, out)


def build_trend_row(summary: dict[str, Any]) -> list[Any]:
    dims = summary.get("dims_avg") or {}
    tests = summary.get("tests") or {}
    return [
        summary["run"], summary["n_docs"], summary["avg_total"],
        dims.get("formatting"), dims.get("placement"), dims.get("image"),
        tests.get("passed", ""), tests.get("failed", ""),
    ]
