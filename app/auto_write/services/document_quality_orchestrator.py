"""document_quality_orchestrator.py

auto_write 문서 품질 개선 하네스의 **오케스트레이터**.

입력 DOCX 를 받아 백업 → 유형분류 → 결정론적 후처리 → PSST/구조검사 →
이미지 제안 → 품질점수 → 품질게이트 → (미달 시)보완 루프 → 결과 저장 →
품질 리포트(md+json) 생성까지 한 번에 수행한다. 실패 시 원본 롤백을 지원한다.

원칙
----
- 원본을 절대 덮어쓰지 않는다(출력 경로가 입력과 같으면 거부).
- 후처리 전 원본을 results/backup/<timestamp>/ 에 백업한다.
- AI 를 호출하지 않는다(전 단계 결정론적). 분류 단계만 openai_service 주입 시 보조 사용.
- 모든 산출물 경로·카운트를 리포트에 그대로 기록(추상 표현 금지).
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from docx import Document

from . import doc_quality_ops as dq
from .document_type_classifier import classify_text, DocTypeResult
from .document_type_classifier import _extract_text as _classify_extract
from .psst_check import check_psst, PSSTReport
from .infographic_suggest import suggest_images, InfographicReport
from .doc_quality_score import score_document, QualityScore

# PSST 검사를 적용할 유형
_PSST_TYPES = {"business_plan", "pitch_deck"}
_PASS_THRESHOLD = 85.0
_MAX_ITERATIONS = 10


@dataclass
class HarnessResult:
    input_docx: str
    output_docx: str
    backup_dir: str
    doc_type: DocTypeResult
    ops: dq.QualityOpsReport
    psst: PSSTReport | None
    infographic: InfographicReport
    score: QualityScore
    iterations: int
    passed: bool
    manual_review: list[str] = field(default_factory=list)
    report_md: str = ""
    report_json: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "input_docx": self.input_docx,
            "output_docx": self.output_docx,
            "backup_dir": self.backup_dir,
            "doc_type": self.doc_type.as_dict(),
            "ops": self.ops.as_dict(),
            "psst": self.psst.as_dict() if self.psst else None,
            "infographic": self.infographic.as_dict(),
            "score": self.score.as_dict(),
            "iterations": self.iterations,
            "passed": self.passed,
            "manual_review": self.manual_review,
            "report_md": self.report_md,
            "report_json": self.report_json,
        }


class DocumentQualityOrchestrator:
    def __init__(self, results_root: Path | str, *, openai_service: Any | None = None):
        self.results_root = Path(results_root)
        self.backup_root = self.results_root / "backup"
        self.openai_service = openai_service
        self.results_root.mkdir(parents=True, exist_ok=True)
        self.backup_root.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 백업 / 롤백
    # ------------------------------------------------------------------

    def backup_original(self, input_path: Path) -> Path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = self.backup_root / ts
        backup_dir.mkdir(parents=True, exist_ok=True)
        dest = backup_dir / input_path.name
        shutil.copy2(input_path, dest)
        return backup_dir

    @staticmethod
    def rollback(backup_dir: Path | str, target_path: Path | str) -> bool:
        """백업 디렉토리의 원본을 target_path 로 복구한다."""
        backup_dir = Path(backup_dir)
        target_path = Path(target_path)
        candidates = list(backup_dir.glob("*.docx"))
        if not candidates:
            return False
        shutil.copy2(candidates[0], target_path)
        return True

    # ------------------------------------------------------------------
    # 메인 파이프라인
    # ------------------------------------------------------------------

    def run(
        self,
        input_docx: Path | str,
        output_docx: Path | str | None = None,
        *,
        emphasize: bool = True,
        underline: bool = False,
        remove_guides: bool = True,
        normalize_fonts: bool = False,
        write_report: bool = True,
    ) -> HarnessResult:
        input_path = Path(input_docx).resolve()
        if not input_path.exists():
            raise FileNotFoundError(f"입력 DOCX 없음: {input_path}")
        if input_path.suffix.lower() != ".docx":
            raise ValueError(f"DOCX 파일이 아님: {input_path}")

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        if output_docx is None:
            output_path = self.results_root / f"{input_path.stem}_품질개선_{ts}.docx"
        else:
            output_path = Path(output_docx).resolve()
        if output_path == input_path:
            raise ValueError("출력 경로가 입력과 동일합니다(원본 덮어쓰기 금지).")

        # 1) 백업
        backup_dir = self.backup_original(input_path)

        # 2) 로드 + 유형 분류
        doc = Document(str(input_path))
        text = _classify_extract(doc)
        doc_type = classify_text(text, filename=input_path.name)

        # 3) 후처리 + 품질 루프
        psst_report: PSSTReport | None = None
        info_report: InfographicReport
        score: QualityScore
        iterations = 0
        prev_total = -1.0
        ops_report = dq.QualityOpsReport()

        while iterations < _MAX_ITERATIONS:
            iterations += 1
            pass_ops = dq.run_all(
                doc,
                remove_guides=remove_guides,
                emphasize=emphasize,
                underline=underline or (iterations >= 2),  # 미달 재시도 시 밑줄 강조 보강
                normalize_fonts=normalize_fonts,
            )
            # 누적 집계
            ops_report.guide_paragraphs_removed += pass_ops.guide_paragraphs_removed
            ops_report.table_guide_rows_removed += pass_ops.table_guide_rows_removed
            ops_report.bullet_spacing_fixed += pass_ops.bullet_spacing_fixed
            ops_report.table_cells_cleaned += pass_ops.table_cells_cleaned
            ops_report.empty_paragraphs_removed += pass_ops.empty_paragraphs_removed
            ops_report.paragraphs_emphasized += pass_ops.paragraphs_emphasized
            ops_report.font_sizes_normalized += pass_ops.font_sizes_normalized

            # PSST (해당 유형만)
            if doc_type.type_code in _PSST_TYPES:
                psst_report = check_psst(doc)
                psst_ratio = psst_report.overall_ratio
            else:
                psst_report = None
                psst_ratio = None

            # 이미지 제안
            info_report = suggest_images(doc)

            # 점수
            score = score_document(
                doc,
                doc_type=doc_type.type_code,
                type_confidence=doc_type.confidence,
                psst_ratio=psst_ratio,
                image_suggestions=len(info_report.suggestions),
                existing_images=info_report.existing_images,
            )

            # 수렴 판정: 합격이거나 점수 개선이 없으면 종료
            if score.passed:
                break
            if abs(score.total - prev_total) < 0.5:
                break
            prev_total = score.total

        # 4) 출력 저장 (원본 덮어쓰기 아님 — 위에서 보장)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(output_path))

        # 5) 수동 확인 항목 도출
        manual_review = self._collect_manual_review(score, psst_report)

        result = HarnessResult(
            input_docx=str(input_path),
            output_docx=str(output_path),
            backup_dir=str(backup_dir),
            doc_type=doc_type,
            ops=ops_report,
            psst=psst_report,
            infographic=info_report,
            score=score,
            iterations=iterations,
            passed=score.passed,
            manual_review=manual_review,
        )

        # 6) 리포트
        if write_report:
            md_path = self.results_root / f"{input_path.stem}_quality_report_{ts}.md"
            json_path = self.results_root / f"{input_path.stem}_quality_report_{ts}.json"
            md = self._render_markdown(result)
            md_path.write_text(md, encoding="utf-8")
            json_path.write_text(
                json.dumps(result.as_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            result.report_md = str(md_path)
            result.report_json = str(json_path)

        return result

    # ------------------------------------------------------------------
    # 리포트 / 보조
    # ------------------------------------------------------------------

    @staticmethod
    def _collect_manual_review(score: QualityScore, psst: PSSTReport | None) -> list[str]:
        items: list[str] = []
        for it in score.items:
            if it.score < it.max_score * 0.6:
                items.append(f"[{it.label}] {it.detail} → 수동 확인 권장")
        if psst is not None:
            for area in psst.areas:
                if area.grade in ("누락", "미흡"):
                    miss = ", ".join(area.missing_items) or "-"
                    items.append(f"[PSST/{area.label}] {area.grade} (누락: {miss})")
        return items

    @staticmethod
    def _render_markdown(r: HarnessResult) -> str:
        lines: list[str] = []
        lines.append(f"# 문서 품질 개선 리포트")
        lines.append("")
        lines.append(f"- 생성 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"- 입력 문서: `{r.input_docx}`")
        lines.append(f"- 출력 문서: `{r.output_docx}`")
        lines.append(f"- 원본 백업: `{r.backup_dir}`")
        lines.append("")
        lines.append("## 1. 문서 유형")
        lines.append(f"- 유형: **{r.doc_type.type_label}** (`{r.doc_type.type_code}`)")
        lines.append(f"- 신뢰도: {r.doc_type.confidence:.0%} (판정: {r.doc_type.method})")
        if r.doc_type.matched_keywords:
            lines.append(f"- 매칭 키워드: {', '.join(r.doc_type.matched_keywords[:12])}")
        lines.append("")
        lines.append("## 2. 후처리 결과")
        o = r.ops
        lines.append(f"- 삭제한 안내문구 단락: {o.guide_paragraphs_removed}")
        lines.append(f"- 삭제한 표 안내 행: {o.table_guide_rows_removed}")
        lines.append(f"- 정리한 글머리표/공백 단락: {o.bullet_spacing_fixed}")
        lines.append(f"- 정리한 표 셀: {o.table_cells_cleaned}")
        lines.append(f"- 삭제한 빈 단락: {o.empty_paragraphs_removed}")
        lines.append(f"- 강조 처리 문장: {o.paragraphs_emphasized}")
        lines.append(f"- 글자크기 표준화: {o.font_sizes_normalized}")
        lines.append("")
        if r.psst is not None:
            lines.append("## 3. PSST 구조 검사")
            lines.append(f"- {r.psst.summary}")
            lines.append("")
            lines.append("| 영역 | 섹션 | 충족 | 등급 | 누락 항목 |")
            lines.append("|------|------|------|------|-----------|")
            for a in r.psst.areas:
                miss = ", ".join(a.missing_items) or "-"
                sec = "있음" if a.section_present else "없음"
                lines.append(f"| {a.label} | {sec} | {a.items_found}/{a.items_total} | {a.grade} | {miss} |")
            lines.append("")
        else:
            lines.append("## 3. PSST 구조 검사")
            lines.append("- 해당 없음(사업계획서/발표자료 유형이 아님)")
            lines.append("")
        lines.append("## 4. 이미지·도식 삽입 제안")
        lines.append(f"- 기존 이미지: {r.infographic.existing_images}장 / 제안: {len(r.infographic.suggestions)}건")
        for s in r.infographic.suggestions:
            lines.append(f"  - **{s.visual_type}** — {s.caption}  (앵커: {s.anchor_text[:40]})")
        lines.append("")
        lines.append("## 5. 문서 품질 점수")
        lines.append(f"- **총점: {r.score.total:.1f} / 100 — {r.score.grade}**")
        lines.append(f"- 품질 게이트(85점): {'통과 ✅' if r.passed else '미달 ❌'} (반복 {r.iterations}회)")
        lines.append("")
        lines.append("| 항목 | 점수 | 결함 | 비고 |")
        lines.append("|------|------|------|------|")
        for it in r.score.items:
            lines.append(f"| {it.label} | {it.score:.1f}/{it.max_score:.0f} | {it.defects} | {it.detail} |")
        lines.append("")
        lines.append("## 6. 수동 확인 필요 항목")
        if r.manual_review:
            for m in r.manual_review:
                lines.append(f"- {m}")
        else:
            lines.append("- 없음 (자동 검수 기준 통과)")
        lines.append("")
        return "\n".join(lines)
