"""test_required_documents_gate.py — 공고 필수 서식 누락 게이트(L040).

배경 (L040)
-----------
공고가 요구한 필수 서식(청렴서약서·개인정보동의서 등)을 하나라도 빠뜨리면 제출
탈락이다. 그런데 기존 수용검사 게이트는 required_format(파일 확장자)만 보고 '서식
존재 여부'는 아무도 검사하지 않았다(실제 지원서 초안에서 [서식3] 청렴서약서 통째
누락 = 탈락 결함 발생). 이 게이트가 그 갭을 막는다:

  ┌──────────────────────────────────────────────────────────────────┐
  │ config.required_documents 로 넘긴 필수 서식이 문서에 없으면 fail →   │
  │ 제출불가(_DRAFT). 미지정(기본)이면 검사 비활성(오탐 0, 현행 동작).     │
  └──────────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

from pathlib import Path

from docx import Document

from auto_write.services.usage_acceptance import (
    AcceptanceConfig,
    SEV_FAIL,
    check_missing_required_documents,
    run_acceptance,
)
from auto_write.services import acceptance_remediation as rem


def _doc_with(*paragraphs: str) -> Document:
    d = Document()
    for p in paragraphs:
        d.add_paragraph(p)
    return d


def test_disabled_by_default_no_false_positive() -> None:
    """required_documents 미지정(기본)이면 결함 0 — 현행 동작 불변(오탐 0)."""
    d = _doc_with("사업계획서 본문만 있는 문서")
    r = check_missing_required_documents(d, AcceptanceConfig())
    assert r.check_id == "missing_required_documents"
    assert r.severity == SEV_FAIL          # 심각도는 fail 급이지만
    assert r.defects == 0 and r.passed     # 미지정이라 통과(비활성)


def test_missing_required_form_is_fail() -> None:
    """공고가 요구한 서식이 문서에 없으면 fail(결함>0)로 잡는다."""
    d = _doc_with("Ⅰ. 사업 개요", "Ⅱ. 추진 계획")   # 청렴서약서 없음
    cfg = AcceptanceConfig(required_documents=("청렴서약서", "개인정보동의서"))
    r = check_missing_required_documents(d, cfg)
    assert r.defects == 2
    assert set(r.samples) == {"청렴서약서", "개인정보동의서"}


def test_present_form_passes_with_whitespace_variation() -> None:
    """서식명이 공백 표기 차이·상위 제목 안에 연속으로 있으면 '포함'으로 인정한다(과탐 억제).

    매칭은 공백만 무시한 '연속 부분일치'다 — '청렴 서약서'→'청렴서약서'(공백차)와
    '[서식3] 개인정보동의서 양식'(상위 제목 안 연속 포함)은 인정하되, 이름 사이에 다른
    글자가 끼면('개인정보 수집·이용 동의서') 인정하지 않는다(사용자가 공고의 정확한
    서식명을 넘기는 opt-in 이라 판정 경계가 분명하다 — test_partial_missing 이 그 경계 확인)."""
    d = _doc_with("[서식3] 청렴 서약서", "[서식4] 개인정보동의서 (필수 제출)")
    cfg = AcceptanceConfig(required_documents=("청렴서약서", "개인정보동의서"))
    r = check_missing_required_documents(d, cfg)
    assert r.defects == 0 and r.passed


def test_partial_missing_reports_only_missing() -> None:
    """일부만 누락되면 누락된 것만 보고한다."""
    d = _doc_with("청렴서약서", "본문")               # 개인정보동의서만 없음
    cfg = AcceptanceConfig(required_documents=("청렴서약서", "개인정보동의서"))
    r = check_missing_required_documents(d, cfg)
    assert r.defects == 1 and r.samples == ["개인정보동의서"]


def test_run_acceptance_forces_not_submittable(tmp_path: Path) -> None:
    """필수 서식 누락 시 run_acceptance 종합 판정이 제출불가(submittable False)로 간다."""
    d = _doc_with("사업 개요만 있는 문서")
    p = tmp_path / "필수서식누락.docx"
    d.save(str(p))
    report = run_acceptance(p, AcceptanceConfig(required_documents=("청렴서약서",)))
    assert report.submittable is False
    ids = {r.check_id for r in report.results if r.severity == SEV_FAIL and not r.passed}
    assert "missing_required_documents" in ids


def test_remedy_exists_for_check() -> None:
    """새 검사에 전용 안내(remediation)가 있어야 한다(고아 검사 금지)."""
    r = rem.remedy_for("missing_required_documents")
    assert r is not rem._DEFAULT
    assert r.kind == rem.KIND_HUMAN     # 사람이 서식 원문을 추가(자동 불가)
