"""문서 품질 개선 하네스 회귀 테스트.

사용자 정의 필수 테스트(Phase 13):
  1) 글머리표 공백 정리  2) 표 내부 공백 정리  3) 안내문구 삭제 규칙
  4) 문서 유형 분류      5) PSST 검사          6) 이미지 제안 리포트
  7) 품질점수 산정       8) 백업 생성          9) 기존 기능 비훼손(import)

실행: (app 디렉토리 기준)  python -m pytest tests/test_document_quality_harness.py -q
"""
from __future__ import annotations

from pathlib import Path

from docx import Document

from auto_write.services import doc_quality_ops as dq
from auto_write.services.document_type_classifier import classify_text
from auto_write.services.psst_check import check_psst
from auto_write.services.infographic_suggest import suggest_images
from auto_write.services.doc_quality_score import score_document
from auto_write.services.document_quality_orchestrator import DocumentQualityOrchestrator


# --------------------------------------------------------------------------- helpers
def _plan_doc() -> Document:
    d = Document()
    d.add_paragraph("1. 문제인식 (Problem)")
    d.add_paragraph("○   고객 시장 문제: 기존 대안의 한계와 심각성, 비용 30% 증가")
    d.add_paragraph("※ 작성요령: 여기에 기재하세요")
    d.add_paragraph("")
    d.add_paragraph("")
    d.add_paragraph("2. 실현가능성 (Solution)")
    d.add_paragraph("ㅇ 핵심기능과 차별성을 구현하여 고객사 적용 시나리오 검증")
    d.add_paragraph("3. 성장전략 (Scale-up)")
    d.add_paragraph("· 시장규모 TAM 5000억, 수익모델 구독, 판로 확대, 매출 100억 KPI")
    d.add_paragraph("4. 팀구성 (Team)")
    d.add_paragraph("- 대표 경력과 팀 구성, 외부 협력 파트너, 수행 경험 보유")
    t = d.add_table(rows=1, cols=2)
    t.cell(0, 0).text = "  구분  "
    t.cell(0, 1).text = "내용   많은    공백"
    return d


# --------------------------------------------------------------------------- 1
def test_bullet_spacing_normalization():
    d = Document()
    d.add_paragraph("○    항목 하나")
    d.add_paragraph("ㅇ  항목   둘")
    fixed = dq.normalize_bullet_spacing(d)
    assert fixed >= 2
    # 다중 공백이 사라졌는지
    assert "    " not in d.paragraphs[0].text


# --------------------------------------------------------------------------- 2
def test_table_whitespace_cleanup():
    d = Document()
    t = d.add_table(rows=1, cols=1)
    t.cell(0, 0).text = "  앞뒤  공백   많음  "
    cleaned = dq.cleanup_table_whitespace(d)
    assert cleaned == 1
    assert t.cell(0, 0).text == "앞뒤 공백 많음"


# --------------------------------------------------------------------------- 3
def test_guide_paragraph_removal():
    d = Document()
    d.add_paragraph("※ 작성요령: 여기에 기재")
    d.add_paragraph("실제 사업 내용입니다.")
    removed = dq.remove_guide_paragraphs(d)
    assert removed == 1
    remaining = [p.text for p in d.paragraphs if p.text.strip()]
    assert "실제 사업 내용입니다." in remaining


def test_empty_paragraph_removal():
    d = Document()
    d.add_paragraph("내용")
    d.add_paragraph("")
    d.add_paragraph("")
    d.add_paragraph("")
    d.add_paragraph("끝")
    removed = dq.remove_empty_paragraphs(d)
    assert removed >= 1


# --------------------------------------------------------------------------- 4
def test_document_type_classification():
    text = "사업계획서\n1. 문제인식 Problem\n창업아이템 PSST 성장전략 사업화"
    r = classify_text(text, filename="사업계획서.docx")
    assert r.type_code == "business_plan"
    assert r.confidence > 0.5

    rnd = classify_text("연구개발계획서 기술개발목표 TRL 성능지표 실험방법", filename="rnd.docx")
    assert rnd.type_code == "rnd_plan"

    generic = classify_text("안녕하세요 오늘 날씨가 좋습니다", filename="memo.docx")
    assert generic.type_code == "generic_submission"


# --------------------------------------------------------------------------- 5
def test_psst_check():
    report = check_psst(_plan_doc())
    assert report.applicable
    assert len(report.areas) == 4
    assert report.overall_ratio > 0.5
    # 모든 영역 섹션 헤더 인식
    assert all(a.section_present for a in report.areas)


# --------------------------------------------------------------------------- 6
def test_infographic_suggestion():
    report = suggest_images(_plan_doc())
    assert len(report.suggestions) >= 1
    # as_dict 의 suggestion_count 가 실제 제안 수와 일치하는지(직렬화 정합성)
    assert report.as_dict()["suggestion_count"] == len(report.suggestions)
    # 시각화 유형 중복 없음
    vtypes = [s.visual_type for s in report.suggestions]
    assert len(vtypes) == len(set(vtypes))


# --------------------------------------------------------------------------- 7
def test_quality_scoring():
    d = _plan_doc()
    dq.run_all(d)
    score = score_document(
        d, doc_type="business_plan", type_confidence=0.9,
        psst_ratio=1.0, image_suggestions=3, existing_images=0,
    )
    assert 0 <= score.total <= 100
    assert len(score.items) == 9
    assert sum(i.max_score for i in score.items) == 100


# --------------------------------------------------------------------------- 8
def test_backup_and_full_run(tmp_path: Path):
    src = tmp_path / "sample.docx"
    _plan_doc().save(str(src))
    orch = DocumentQualityOrchestrator(tmp_path / "results")
    res = orch.run(src)

    # 백업 생성
    assert Path(res.backup_dir).exists()
    assert list(Path(res.backup_dir).glob("*.docx"))
    # 원본 비훼손 + 출력 분리
    assert Path(res.output_docx).exists()
    assert Path(res.output_docx).resolve() != src.resolve()
    # 리포트 생성
    assert Path(res.report_md).exists()
    assert Path(res.report_json).exists()
    # 점수/유형
    assert res.doc_type.type_code == "business_plan"
    assert 0 <= res.score.total <= 100

    # 롤백
    target = tmp_path / "restored.docx"
    assert DocumentQualityOrchestrator.rollback(res.backup_dir, target)
    assert target.exists()


def test_output_never_overwrites_input(tmp_path: Path):
    src = tmp_path / "in.docx"
    _plan_doc().save(str(src))
    orch = DocumentQualityOrchestrator(tmp_path / "results")
    import pytest
    with pytest.raises(ValueError):
        orch.run(src, src)  # 동일 경로 → 거부


# --------------------------------------------------------------------------- 9
def test_existing_modules_still_import():
    # 기존 핵심 서비스가 여전히 import 되는지(하네스 추가로 깨지지 않았는지)
    from auto_write.services import docx_ops, qa_service, project_service, render_service  # noqa
    from auto_write.services import evaluation_service, submittable_filler  # noqa
    assert hasattr(qa_service.QAService, "build_report")
    assert hasattr(project_service.ProjectService, "PSST_PROBLEM_RE")
