"""test_pure_document_type_classifier.py — 문서유형 규칙기반 분류 순수 회귀.

``classify_text`` 는 파일 I/O·AI 없이 키워드 가중 점수만으로 유형을 판정하는
순수 함수다. 점수 경계(_MIN_SCORE)·fallback·파일명 반영·as_dict 구조를 고정한다.
모든 기댓값은 _SIGNATURES 가중치를 손으로 계산해 확정했다.
"""

from __future__ import annotations

from auto_write.services.document_type_classifier import (
    DocTypeResult,
    classify_text,
)


def test_irrelevant_text_falls_back_to_generic():
    r = classify_text("오늘 점심은 무엇을 먹을까 고민이다")
    assert r.type_code == "generic_submission"
    assert r.type_label == "기타 제출문서"
    assert r.confidence == 0.3            # fallback 고정 신뢰도
    assert r.matched_keywords == []
    assert r.method == "rule"


def test_business_plan_dominant_signal():
    # 사업계획서(5)+문제인식(3)+성장전략(3)+PSST(5) = 16점, 타 유형 0점.
    r = classify_text("본 사업계획서는 PSST 구조로 문제인식과 성장전략을 담는다")
    assert r.type_code == "business_plan"
    assert r.type_label == "사업계획서"
    assert "사업계획서" in r.matched_keywords
    assert "PSST" in r.matched_keywords
    assert 0.4 < r.confidence <= 0.99


def test_filename_contributes_to_classification():
    # 본문은 비어도 파일명의 '정책자금'(5)이 policy_fund_report 로 이끈다.
    r = classify_text("내용 없음", filename="정책자금_검토보고서.docx")
    assert r.type_code == "policy_fund_report"
    assert r.scores["policy_fund_report"] >= 5


def test_min_score_boundary_is_inclusive():
    # 정확히 4점(_MIN_SCORE)이면 generic 이 아니라 해당 유형으로 분류된다.
    r = classify_text("연구개발 계획")          # rnd_plan '연구개발' = 4점
    assert r.type_code == "rnd_plan"
    assert r.scores["rnd_plan"] == 4


def test_case_insensitive_english_keyword():
    # 영문 키워드는 대소문자 무시(psst 소문자도 매칭).
    r = classify_text("this plan follows the psst framework: problem and solution")
    # PSST(5)+Problem(2)+Solution(2) = 9점 → business_plan
    assert r.type_code == "business_plan"


def test_as_dict_shape_and_keyword_cap():
    r = classify_text("사업계획서 문제인식 성장전략 PSST")
    d = r.as_dict()
    assert set(d.keys()) == {
        "type_code", "type_label", "confidence", "method",
        "scores", "matched_keywords",
    }
    assert isinstance(d["scores"], dict)
    assert len(d["matched_keywords"]) <= 20     # 상위 20개로 제한
    assert isinstance(r, DocTypeResult)
