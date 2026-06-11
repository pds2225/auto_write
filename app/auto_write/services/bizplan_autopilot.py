"""bizplan_autopilot.py — '제출 가능 사업계획서' 생성·완성 통합 오케스트레이터.

초안/메모 DOCX 를 받아 **목표 점수에 도달할 때까지** 다음을 반복한다(ultraqa/ultragoal 정신):

  루프(최대 max_loops):
    1) AI 본문 작성/보강 — ``bizplan_ai_writer.ai_write_areas``
       (PSST 약점 영역을 근거 명시하며 작성, 무출처 수치는 [확인필요])
    2) 품질 오토파일럿 — ``autopilot_pipeline.run_autopilot``
       (백업 + 서식 수정 + 이미지 적용 + (AI가 안 쓴 영역은)PSST 가이드 + 점수/게이트)
    3) 공고 채점 — ``evaluation_service`` (공고 텍스트가 있을 때)
       목표 충족률(target_ratio) 도달 시 종료, 아니면 다음 루프

설계 원칙
---------
- **원본 절대 보존**: run_autopilot 1단계가 원본을 백업한다. 모든 출력은 새 경로.
- **근거 없는 날조 0**: AI 작성은 출처 병기/[확인필요] 규칙을 강제. AI 키 없으면 작성 생략.
- **점수 부풀리기 방지**: 채점은 별도 AI 패스(심사위원 프롬프트)로 독립 수행.
- 최종 산출은 '제출 직전본 DOCX + 점수 추이 + 확인필요 To-Do' 이며, 핵심 수치 검증 책임은 사용자.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from docx import Document

from ..config import ensure_directories, get_settings
from .autopilot_pipeline import run_autopilot
from .bizplan_ai_writer import ai_write_areas
from .evaluation_service import EvaluationService


@dataclass
class LoopScore:
    iteration: int
    total_score: int
    max_total: int
    pass_ratio: float
    summary: str = ""
    weak_sections: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "iteration": self.iteration,
            "total_score": self.total_score,
            "max_total": self.max_total,
            "pass_ratio": round(self.pass_ratio, 3),
            "summary": self.summary,
            "weak_sections": self.weak_sections,
        }


@dataclass
class BizplanReport:
    input_docx: str
    output_docx: str = ""
    backup_dir: str = ""
    report_md: str = ""
    loops_run: int = 0
    target_ratio: float = 0.85
    target_reached: bool = False
    ai_used: bool = False
    final_quality_score: float = 0.0
    final_gate_passed: bool = False
    prompts_inserted: int = 0
    ai_areas_written: int = 0
    # 수용검사 게이트(R8) — autopilot 의 판정을 최종 산출까지 전파
    acceptance_submittable: bool = False
    acceptance_verdict: str = ""
    acceptance_fail_defects: int = 0
    acceptance_failed_checks: list[str] = field(default_factory=list)
    draft_marked: bool = False
    score_history: list[LoopScore] = field(default_factory=list)
    needs_confirm: list[str] = field(default_factory=list)
    evidence_used: list[str] = field(default_factory=list)
    manual_todo: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "input_docx": self.input_docx,
            "output_docx": self.output_docx,
            "backup_dir": self.backup_dir,
            "report_md": self.report_md,
            "loops_run": self.loops_run,
            "target_ratio": round(self.target_ratio, 3),
            "target_reached": self.target_reached,
            "ai_used": self.ai_used,
            "final_quality_score": round(self.final_quality_score, 1),
            "final_gate_passed": self.final_gate_passed,
            "prompts_inserted": self.prompts_inserted,
            "ai_areas_written": self.ai_areas_written,
            "acceptance_submittable": self.acceptance_submittable,
            "acceptance_verdict": self.acceptance_verdict,
            "acceptance_fail_defects": self.acceptance_fail_defects,
            "acceptance_failed_checks": self.acceptance_failed_checks,
            "draft_marked": self.draft_marked,
            "score_history": [s.as_dict() for s in self.score_history],
            "needs_confirm": self.needs_confirm,
            "evidence_used": self.evidence_used,
            "manual_todo": self.manual_todo,
        }


def _make_openai(use_ai: bool) -> Optional[Any]:
    if not use_ai:
        return None
    try:
        from .openai_client import OpenAIService

        svc = OpenAIService(get_settings())
        return svc if getattr(svc, "available", False) else None
    except Exception:
        return None


def _doc_text(path: str, *, limit: int = 6000) -> str:
    try:
        doc = Document(path)
    except Exception:
        return ""
    parts: list[str] = []
    total = 0
    for p in doc.paragraphs:
        t = p.text.strip()
        if t:
            parts.append(t)
            total += len(t)
            if total >= limit:
                break
    return "\n".join(parts)


def _score_doc(
    openai_service: Any,
    docx_path: str,
    announcement_text: str,
    iteration: int,
) -> Optional[LoopScore]:
    """공고 기준으로 문서를 채점한다(AI 필요). 실패 시 None."""
    if not (openai_service and getattr(openai_service, "available", False)):
        return None
    eval_svc = EvaluationService(openai_service)
    criteria = eval_svc.parse_announcement(announcement_text)
    if not criteria:
        return None
    scores = eval_svc.score_document(_doc_text(docx_path), criteria, [])
    result = eval_svc.build_eval_result(iteration, scores, [])
    return LoopScore(
        iteration=iteration,
        total_score=result.total_score,
        max_total=result.max_total,
        pass_ratio=result.pass_ratio,
        summary=result.summary,
        weak_sections=list(result.weak_sections),
    )


def run_bizplan_autopilot(
    input_docx: str,
    output_docx: Optional[str] = None,
    *,
    brief: str = "",
    announcement_text: Optional[str] = None,
    target_ratio: float = 0.85,
    max_loops: int = 3,
    use_ai: bool = True,
    placeholder_only: bool = False,
    underline: bool = False,
    write_report: bool = True,
) -> BizplanReport:
    """초안 DOCX 를 목표 점수까지 생성·완성한다.

    Args:
        input_docx: 초안/메모 DOCX(원본, 자동 백업).
        output_docx: 최종 출력. 미지정 시 results/ 자동 명명.
        brief: 사업 브리프(아이디어·팀·수치 등 자유 텍스트). AI 작성에 사용.
        announcement_text: 공고 평가기준 텍스트. 있으면 채점·목표 반복 수행.
        target_ratio: 목표 충족률(기본 0.85 = 85%). 도달하면 조기 종료.
        max_loops: 최대 반복 횟수(기본 3).
        use_ai: AI 본문 작성·채점 사용 여부(키 없으면 자동 비활성).
        placeholder_only: 이미지를 차트 없이 자리표시만.

    Returns:
        BizplanReport — 점수 추이·확인필요·산출 경로 통합.
    """
    settings = get_settings()
    ensure_directories(settings)
    results_root = Path(settings.results_root)
    results_root.mkdir(parents=True, exist_ok=True)

    in_path = Path(input_docx)
    if not in_path.exists():
        raise FileNotFoundError(f"입력 DOCX 가 없습니다: {input_docx}")
    stem = in_path.stem
    final_path = Path(output_docx) if output_docx else results_root / f"{stem}_bizplan.docx"
    if in_path.resolve() == final_path.resolve():
        raise ValueError("출력이 입력과 같습니다. 원본 덮어쓰기는 금지입니다.")

    openai_service = _make_openai(use_ai)
    report = BizplanReport(
        input_docx=str(in_path),
        output_docx=str(final_path),
        target_ratio=target_ratio,
        ai_used=bool(openai_service),
    )

    cur = str(in_path)
    for i in range(1, max_loops + 1):
        report.loops_run = i

        # 1) AI 본문 작성/보강 (근거 명시)
        tmp_w = results_root / f"{stem}_bp{i}_w.docx"
        w = ai_write_areas(cur, str(tmp_w), brief=brief, openai_service=openai_service)
        report.ai_areas_written += w.areas_written
        for nc in w.needs_confirm:
            if nc not in report.needs_confirm:
                report.needs_confirm.append(nc)
        for ev in w.evidence_used:
            if ev not in report.evidence_used:
                report.evidence_used.append(ev)
        ai_wrote = w.areas_written > 0

        # 2) 품질 오토파일럿 (AI 가 영역을 썼으면 가이드 중복 방지로 psst_scaffold 끔)
        tmp_ap = results_root / f"{stem}_bp{i}_ap.docx"
        ap = run_autopilot(
            str(tmp_w), str(tmp_ap),
            underline=underline,
            placeholder_only=placeholder_only,
            psst_scaffold=not ai_wrote,
            write_report=False,
        )
        if i == 1:
            report.backup_dir = ap.backup_dir
        report.final_quality_score = ap.score_total
        report.final_gate_passed = ap.passed
        report.prompts_inserted = ap.prompts_inserted
        report.acceptance_submittable = ap.acceptance_submittable
        report.acceptance_verdict = ap.acceptance_verdict
        report.acceptance_fail_defects = ap.acceptance_fail_defects
        report.acceptance_failed_checks = list(ap.acceptance_failed_checks)
        cur = ap.output_docx

        # 3) 공고 채점 + 목표 판정
        if announcement_text:
            sc = _score_doc(openai_service, cur, announcement_text, i)
            if sc is not None:
                report.score_history.append(sc)
                if sc.pass_ratio >= target_ratio:
                    report.target_reached = True
                    break
            else:
                break  # 채점 불가(AI 없음/공고 파싱 실패) → 1회로 종료
        else:
            break  # 공고 없음 → 목표 반복 없이 1회 완성

    # 최종본 저장 — 수용검사 fail 이면 '제출' 이름으로 내보내지 않는다.
    # (중간본 _DRAFT 를 깨끗한 이름으로 복사하면 마킹이 소실되므로 최종 이름에도 강제)
    if (report.acceptance_verdict and not report.acceptance_submittable
            and not final_path.stem.endswith("_DRAFT")):
        final_path = final_path.with_name(f"{final_path.stem}_DRAFT{final_path.suffix}")
        report.draft_marked = True
    final_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(cur, str(final_path))
    report.output_docx = str(final_path)
    report.manual_todo = _build_todo(report)

    if write_report:
        report.report_md = _write_report(results_root, stem, report)
    return report


def _build_todo(report: BizplanReport) -> list[str]:
    todo: list[str] = []
    if not report.ai_used:
        todo.append("AI 키 미연결 — 본문 자동작성/채점이 생략됨. 키 설정 후 재실행하면 완성도 상승.")
    if report.score_history and not report.target_reached:
        last = report.score_history[-1]
        todo.append(
            f"공고 충족률 {last.pass_ratio*100:.0f}% (목표 {report.target_ratio*100:.0f}% 미달) — "
            f"약점 섹션 보완 후 재실행: {', '.join(last.weak_sections) or '심사 피드백 참고'}"
        )
    if report.acceptance_verdict and not report.acceptance_submittable:
        todo.append(
            f"수용검사 {report.acceptance_verdict} (fail {report.acceptance_fail_defects}건) — "
            f"결함 해결 전 제출 금지(출력명 _DRAFT)."
        )
        todo.extend(f"  · {c}" for c in report.acceptance_failed_checks)
    for nc in report.needs_confirm:
        todo.append(f"[확인필요] {nc}")
    if report.prompts_inserted:
        todo.append(
            f"NotebookLM 슬라이드 프롬프트 {report.prompts_inserted}곳 — "
            f"NotebookLM 에 붙여넣어 슬라이드 생성 후 안내 블록 삭제."
        )
    if not report.final_gate_passed:
        todo.append(f"서식 품질점수 {report.final_quality_score:.1f} (게이트 미달) — 보완 권장.")
    return todo


def _write_report(results_root: Path, stem: str, report: BizplanReport) -> str:
    md_path = results_root / f"{stem}_bizplan_report.md"
    L: list[str] = []
    L.append(f"# 사업계획서 생성·완성 리포트 — {stem}")
    L.append("")
    L.append(f"- 입력(초안): `{report.input_docx}`")
    L.append(f"- 최종 출력: `{report.output_docx}`")
    L.append(f"- 원본 백업: `{report.backup_dir}`")
    L.append(f"- AI 사용: {'예' if report.ai_used else '아니오(키 미연결)'}")
    L.append(f"- 반복 횟수: {report.loops_run} / 목표 충족률: {report.target_ratio*100:.0f}%")
    L.append("")
    L.append("## 공고 채점 추이")
    if report.score_history:
        for s in report.score_history:
            mark = "✅" if s.pass_ratio >= report.target_ratio else "·"
            L.append(f"- {mark} 루프 {s.iteration}: {s.total_score}/{s.max_total} ({s.pass_ratio*100:.0f}%)")
        L.append(f"- 목표 도달: {'예' if report.target_reached else '아니오'}")
    else:
        L.append("- (공고 미제공 또는 AI 미연결 — 채점 생략)")
    L.append("")
    L.append("## 품질/시각화")
    gate = "통과" if report.final_gate_passed else "미달"
    L.append(f"- 서식 품질점수: {report.final_quality_score:.1f}/100 (게이트 {gate})")
    if report.acceptance_verdict:
        L.append(
            f"- 실사용 수용검사: **{report.acceptance_verdict}** "
            f"(fail {report.acceptance_fail_defects}건"
            + (", 출력명 _DRAFT 표시" if report.draft_marked else "") + ")"
        )
    L.append(f"- NotebookLM 슬라이드 프롬프트: {report.prompts_inserted}건")
    L.append(f"- AI 작성 보강 영역: {report.ai_areas_written}개")
    L.append("")
    if report.evidence_used:
        L.append("## 인용된 근거 출처")
        for e in report.evidence_used:
            L.append(f"- {e}")
        L.append("")
    L.append("## 제출 전 수동 확인 To-Do")
    if report.manual_todo:
        for t in report.manual_todo:
            L.append(f"- [ ] {t}")
    else:
        L.append("- 없음 (제출 준비 완료 — 그래도 핵심 수치는 최종 확인 권장)")
    L.append("")
    md_path.write_text("\n".join(L), encoding="utf-8")
    return str(md_path)
