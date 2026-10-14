"""검수 보고서 조립(10장): 구조 검증 + AI Visual QA + 값 출처 + 사용자 REVIEW 목록.

최종 판단은 사용자에게 있다. 이 모듈은 어떤 문구로도 제출 여부를 판단하지 않으며,
출력 직전 find_forbidden 으로 12장 금지 표현을 한 번 더 검사한다.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .final_check import should_block_submission_named_pdf, summarize
from .status import Finding, Status, assert_no_forbidden

_GROUP_TITLES = {
    "structural": "구조·기술 검증",
    "engine": "엔진 처리 결과(F1~F6)",
    "visual-ai": "AI Visual QA(자동 provider)",
    "manual-agent": "수동 에이전트 시각 확인(manual-agent visual check)",
}


def build_report(
    findings: list[Finding],
    *,
    title: str,
    visual_usage: dict[str, Any] | None = None,
    provenance: list[dict[str, Any]] | None = None,
    artifacts: dict[str, str] | None = None,
    real_environment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """보고서 dict 를 만든다. 구조/시각 결과를 source 로 구분해 담는다."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for f in findings:
        groups.setdefault(f.source, []).append(f.to_dict())
    summary = summarize(findings)
    report = {
        "title": title,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "groups": groups,
        "summary": summary,
        "named_pdf_generation_blocked": should_block_submission_named_pdf(findings),
        "visual_usage": visual_usage or {},
        "provenance": provenance or [],
        "artifacts": artifacts or {},
        "real_environment": real_environment or {},
        "notice": "최종 제출 여부는 사용자가 결정한다. 이 보고서는 생성·검사·오류 보고만 한다.",
    }
    assert_no_forbidden(json.dumps(report, ensure_ascii=False))
    return report


def render_markdown(report: dict[str, Any]) -> str:
    lines = [f"# {report['title']}", "", f"생성: {report['generated_at']}", "", report["notice"], ""]
    counts = report["summary"]["counts"]
    lines.append("## 요약")
    lines.append(" / ".join(f"{k} {v}" for k, v in counts.items()))
    if report["named_pdf_generation_blocked"]:
        lines.append("")
        lines.append("> 구조 검사 FAIL 이 있어 '(제출)' 명칭 PDF 자동 생성을 중단했다(엔진 산출물 생성 통제). 검토용 PDF 를 별도로 제공한다.")
    lines.append("")
    for source, items in report["groups"].items():
        lines.append(f"## {_GROUP_TITLES.get(source, source)}")
        for it in items:
            page = f" p.{it['page']}" if it.get("page") else ""
            img = f" [이미지: {it['image']}]" if it.get("image") else ""
            ev = f" — {it['evidence']}" if it.get("evidence") else ""
            lines.append(f"- [{it['status']}] {it['code']}{page}: {it['message']}{ev}{img}")
        lines.append("")
    lines.append("## 사용자 확인 목록 (REVIEW / UNVERIFIED)")
    review = report["summary"]["user_review_list"]
    lines += [f"- [{r['status']}] {r['code']}: {r['message']}" for r in review] or ["- 없음"]
    if report["provenance"]:
        lines += ["", "## 필드별 값 출처"]
        lines += [f"- {p.get('field', '?')}: {p.get('source', '?')} → {p.get('result', '?')}" for p in report["provenance"]]
    if report["visual_usage"]:
        lines += ["", "## Visual QA 사용량", f"`{json.dumps(report['visual_usage'], ensure_ascii=False)}`"]
    if report["real_environment"]:
        lines += ["", "## 실제 환경 검증 구분", f"`{json.dumps(report['real_environment'], ensure_ascii=False)}`"]
    text = "\n".join(lines) + "\n"
    assert_no_forbidden(text)
    return text


def write_report(report: dict[str, Any], out_dir: str | Path, stem: str = "검수보고서") -> tuple[Path, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    jp, mp = out / f"{stem}.json", out / f"{stem}.md"
    for p in (jp, mp):
        if p.exists():
            raise ValueError(f"기존 결과물 덮어쓰기 금지: {p}")
    jp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    mp.write_text(render_markdown(report), encoding="utf-8")
    return jp, mp
