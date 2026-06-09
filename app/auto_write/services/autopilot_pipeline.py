"""autopilot_pipeline.py — 문서 품질 '수정' 전 단계를 무인 연속 실행하는 통합 파이프라인.

진단만 하던 단계들을 **실제 수정**으로 잇고 한 번에 돌린다:

  1) 백업 + 서식 수정 + 점수/게이트  — 기존 ``DocumentQualityOrchestrator.run``
     (안내문구 삭제·글머리표/표 공백·빈 단락·핵심문장 강조 + 100점 채점 + 85점 게이트)
  2) 이미지 실제 적용             — ``image_apply.apply_images``
     (그림 위치에 NotebookLM 슬라이드 생성 프롬프트 블록 삽입; 제안은 Claude, 폴백 키워드)
  3) PSST 보강                   — ``psst_fill.apply_psst_scaffold``
     (누락/미흡 영역에 작성 뼈대+가이드)
  4) 잔존 빈칸 스캔 + 통합 리포트

설계 원칙
---------
- **원본 절대 보존**: 1단계에서 원본을 ``results/backup/<ts>/`` 에 백업한다.
  이후 단계는 항상 새 출력 경로로 저장(in==out 이면 ValueError).
- **점수/게이트는 1단계(서식 수정) 기준**으로 판정한다. 이미지/PSST 보강은
  사람이 채워야 할 '시각화 자리'와 '작성 To-Do' 라서 점수를 부풀리지 않는다(날조 0).
- 빈칸 채움(submittable_filler)은 외부 plan 데이터가 필요하므로 무인 파이프라인의
  필수 단계로 넣지 않고, 잔존 빈칸을 **스캔해 보고**만 한다(있으면 To-Do 로 안내).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from docx import Document

from ..config import ensure_directories, get_settings
from .document_quality_orchestrator import DocumentQualityOrchestrator
from .image_apply import ImageApplyReport, apply_images
from .psst_fill import PSSTFillReport, apply_psst_scaffold

# 잔존 빈칸(placeholder) 보수적 탐지 패턴
_RESIDUAL_RE = re.compile(
    r"(_{3,}|\[\s*\]|\(\s*작성\s*\)|※\s*작성|기재\s*바랍|예\s*:\s*\)|【\s*】)"
)


@dataclass
class AutopilotReport:
    input_docx: str
    output_docx: str = ""
    backup_dir: str = ""
    report_md: str = ""
    # 1단계(품질)
    doc_type: str = ""
    score_total: float = 0.0
    grade: str = ""
    passed: bool = False
    iterations: int = 0
    ops_summary: str = ""
    # 2단계(이미지)
    prompts_inserted: int = 0
    # 3단계(PSST)
    psst_overall_ratio: float = 0.0
    psst_areas_scaffolded: int = 0
    psst_items_added: int = 0
    psst_scaffolded_areas: list[str] = field(default_factory=list)
    # 4단계(잔존)
    residual_placeholders: list[str] = field(default_factory=list)
    manual_todo: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "input_docx": self.input_docx,
            "output_docx": self.output_docx,
            "backup_dir": self.backup_dir,
            "report_md": self.report_md,
            "doc_type": self.doc_type,
            "score_total": round(self.score_total, 1),
            "grade": self.grade,
            "passed": self.passed,
            "iterations": self.iterations,
            "ops_summary": self.ops_summary,
            "prompts_inserted": self.prompts_inserted,
            "psst_overall_ratio": round(self.psst_overall_ratio, 3),
            "psst_areas_scaffolded": self.psst_areas_scaffolded,
            "psst_items_added": self.psst_items_added,
            "psst_scaffolded_areas": self.psst_scaffolded_areas,
            "residual_placeholders": self.residual_placeholders,
            "manual_todo": self.manual_todo,
        }


def _scan_residual(docx_path: str, *, limit: int = 20) -> list[str]:
    """결과 DOCX 에서 잔존 빈칸 표식을 보수적으로 스캔한다(보고용)."""
    found: list[str] = []
    try:
        doc = Document(docx_path)
    except Exception:
        return found
    for p in doc.paragraphs:
        t = p.text.strip()
        if t and _RESIDUAL_RE.search(t):
            found.append(t[:60])
            if len(found) >= limit:
                return found
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                t = cell.text.strip()
                if t and _RESIDUAL_RE.search(t):
                    found.append(t[:60])
                    if len(found) >= limit:
                        return found
    return found


def _make_openai_service() -> Optional[Any]:
    """가용한 OpenAIService 를 만든다(키 없거나 실패하면 None)."""
    try:
        from .openai_client import OpenAIService

        settings = get_settings()
        svc = OpenAIService(settings)
        return svc if getattr(svc, "available", False) else None
    except Exception:
        return None


def _make_orchestrator(results_root: Path, *, use_ai: bool = False) -> DocumentQualityOrchestrator:
    openai_service = _make_openai_service() if use_ai else None
    return DocumentQualityOrchestrator(results_root, openai_service=openai_service)


def run_autopilot(
    input_docx: str,
    output_docx: Optional[str] = None,
    *,
    emphasize: bool = True,
    underline: bool = False,
    remove_guides: bool = True,
    normalize_fonts: bool = False,
    max_images: int = 8,
    placeholder_only: bool = False,
    psst_scaffold: bool = True,
    write_report: bool = True,
) -> AutopilotReport:
    """문서 품질 수정 전 단계를 무인 연속 실행한다.

    Args:
        input_docx: 입력 DOCX 경로(원본, 자동 백업됨).
        output_docx: 최종 출력 경로. 미지정 시 results/ 아래 자동 명명.
        emphasize/underline/remove_guides/normalize_fonts: 서식 수정 옵션(1단계).
        max_images: 이미지 적용 최대 개수(2단계).
        placeholder_only: True 면 차트 생성 없이 자리표시만 삽입(2단계, 가장 안전).
        psst_scaffold: True 면 PSST 누락/미흡 영역에 작성 가이드 삽입(3단계).
        write_report: True 면 통합 리포트(md/json) 생성.

    Returns:
        AutopilotReport — 전 단계 통합 결과.
    """
    settings = get_settings()
    ensure_directories(settings)
    results_root = Path(settings.results_root)
    results_root.mkdir(parents=True, exist_ok=True)

    in_path = Path(input_docx)
    if not in_path.exists():
        raise FileNotFoundError(f"입력 DOCX 가 없습니다: {input_docx}")

    stem = in_path.stem
    if output_docx:
        final_path = Path(output_docx)
    else:
        final_path = results_root / f"{stem}_autopilot.docx"
    if in_path.resolve() == final_path.resolve():
        raise ValueError("출력이 입력과 같습니다. 원본 덮어쓰기는 금지입니다.")

    report = AutopilotReport(input_docx=str(in_path), output_docx=str(final_path))

    # --- 1단계: 백업 + 서식 수정 + 점수/게이트 ---
    tmp_quality = results_root / f"{stem}_ap1_quality.docx"
    orch = _make_orchestrator(results_root)
    qresult = orch.run(
        str(in_path),
        str(tmp_quality),
        emphasize=emphasize,
        underline=underline,
        remove_guides=remove_guides,
        normalize_fonts=normalize_fonts,
        write_report=False,
    )
    report.backup_dir = str(qresult.backup_dir)
    report.doc_type = f"{qresult.doc_type.type_label} ({qresult.doc_type.confidence:.0%})"
    report.score_total = qresult.score.total
    report.grade = qresult.score.grade
    report.passed = qresult.passed
    report.iterations = qresult.iterations
    o = qresult.ops
    report.ops_summary = (
        f"안내문구-{o.guide_paragraphs_removed} 글머리표-{o.bullet_spacing_fixed} "
        f"표셀-{o.table_cells_cleaned} 빈단락-{o.empty_paragraphs_removed} "
        f"강조-{o.paragraphs_emphasized}"
    )
    stage_in = Path(qresult.output_docx)

    # --- 2단계: 이미지 실제 적용(NotebookLM 슬라이드 프롬프트 삽입) ---
    tmp_img = results_root / f"{stem}_ap2_img.docx"
    img: ImageApplyReport = apply_images(
        str(stage_in), str(tmp_img),
        max_items=max_images, placeholder_only=placeholder_only,
        openai_service=_make_openai_service(),
    )
    report.prompts_inserted = img.prompts_inserted
    stage_in = tmp_img

    # --- 3단계: PSST 보강 ---
    if psst_scaffold:
        psst: PSSTFillReport = apply_psst_scaffold(str(stage_in), str(final_path))
        report.psst_overall_ratio = psst.overall_ratio
        report.psst_areas_scaffolded = psst.areas_scaffolded
        report.psst_items_added = psst.items_added
        report.psst_scaffolded_areas = list(psst.scaffolded_areas)
    else:
        # PSST 보강 생략 시 2단계 결과를 최종으로 복사
        import shutil

        final_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(str(stage_in), str(final_path))

    # --- 4단계: 잔존 빈칸 스캔 + To-Do ---
    report.residual_placeholders = _scan_residual(str(final_path))
    report.manual_todo = _build_todo(report)

    if write_report:
        report.report_md = _write_report(results_root, stem, report)

    return report


def _build_todo(report: AutopilotReport) -> list[str]:
    todo: list[str] = []
    if not report.passed:
        todo.append(
            f"품질점수 {report.score_total:.1f}점(게이트 미달) — 보완 후 재실행 권장."
        )
    if report.prompts_inserted:
        todo.append(
            f"NotebookLM 슬라이드 프롬프트 {report.prompts_inserted}곳 — "
            f"각 프롬프트를 NotebookLM 에 붙여넣어 슬라이드를 만들고, 안내 블록은 삭제하세요."
        )
    for area in report.psst_scaffolded_areas:
        todo.append(f"PSST 작성 보강: {area}")
    if report.residual_placeholders:
        todo.append(
            f"잔존 빈칸 {len(report.residual_placeholders)}곳 — 직접 채우거나 submittable_filler 로 채움."
        )
    return todo


def _write_report(results_root: Path, stem: str, report: AutopilotReport) -> str:
    md_path = results_root / f"{stem}_autopilot_report.md"
    lines: list[str] = []
    lines.append(f"# 오토파일럿 최종 리포트 — {stem}")
    lines.append("")
    lines.append(f"- 입력: `{report.input_docx}`")
    lines.append(f"- 출력: `{report.output_docx}`")
    lines.append(f"- 백업: `{report.backup_dir}`")
    lines.append("")
    lines.append("## 1) 서식 수정 + 품질점수")
    lines.append(f"- 문서 유형: {report.doc_type}")
    gate = "통과" if report.passed else "미달"
    lines.append(
        f"- 품질점수: **{report.score_total:.1f}/100** ({report.grade}) | 게이트 {gate} "
        f"(반복 {report.iterations}회)"
    )
    lines.append(f"- 후처리: {report.ops_summary}")
    lines.append("")
    lines.append("## 2) 이미지 적용 (NotebookLM 슬라이드 프롬프트)")
    lines.append(f"- 슬라이드 프롬프트 삽입: {report.prompts_inserted}건")
    lines.append("- 각 프롬프트를 NotebookLM 슬라이드 생성에 붙여넣어 사용하세요.")
    lines.append("")
    lines.append("## 3) PSST 보강")
    lines.append(f"- 전체 충족률: {report.psst_overall_ratio*100:.0f}%")
    lines.append(
        f"- 보강 영역: {report.psst_areas_scaffolded}개 / 추가 항목: {report.psst_items_added}개"
    )
    if report.psst_scaffolded_areas:
        lines.append(f"- 대상: {', '.join(report.psst_scaffolded_areas)}")
    lines.append("")
    lines.append("## 4) 수동 보완 To-Do")
    if report.manual_todo:
        for t in report.manual_todo:
            lines.append(f"- [ ] {t}")
    else:
        lines.append("- 없음 (제출 준비 완료)")
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return str(md_path)
